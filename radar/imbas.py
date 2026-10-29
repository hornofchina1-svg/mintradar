"""Imbas BSC: setiap mint NFT (ERC-721 Transfer dari 0x0) → kiraan per kontrak per minit → kontrak 'panas' diperiksa
(siapa hantar tx, berapa bayar) → jualan sekunder kontrak yang dijejak. BACA SAHAJA: tiada wallet, tiada transaksi."""
import sqlite3
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from . import db, nilai
from .laporan import harga_bnb_usd
from .rpc import RpcGagal

TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
SIFAR = "0x" + "0" * 64


def _alamat(topic):
    return "0x" + topic[-40:]


def _rentetan(hasil):
    """Nyahkod string ABI (name/symbol). Kontrak lama yang memulangkan bytes32 juga diterima."""
    try:
        b = bytes.fromhex(hasil[2:])
        if len(b) >= 64:
            n = int.from_bytes(b[32:64], "big")
            return b[64:64 + n].decode("utf-8", "replace")[:60]
        return b.rstrip(b"\0").decode("utf-8", "replace")[:60]
    except (ValueError, TypeError):
        return None


class Pengimbas:
    def __init__(self, cfg, rpc, con):
        self.cfg, self.rpc, self.con = cfg, rpc, con
        self.titik = None  # (blok, ts) terakhir untuk menganggar masa setiap blok
        self._gas_cache = None
        self._bnb_usd = None

    def _ts(self, blok_akhir):
        ts_akhir = self.rpc.masa_blok(blok_akhir)
        lama = self.titik
        self.titik = (blok_akhir, ts_akhir)
        if lama and blok_akhir > lama[0]:
            sela = (ts_akhir - lama[1]) / (blok_akhir - lama[0])
        else:
            sela = 0.45
        return lambda n: int(ts_akhir - (blok_akhir - n) * sela)

    def cebisan(self, dari, hingga):
        ts_blok = self._ts(hingga)
        logs = self.rpc.log(dari, hingga, [TRANSFER, SIFAR])
        sekarang = ts_blok(hingga)
        self.proses_mint(logs, ts_blok, sekarang)
        db.tetap(self.con, "blok", hingga)
        self.con.commit()
        return len(logs)

    def proses_mint(self, logs, ts_blok, sekarang):
        """Kiraan mint per kontrak per minit + sampel tx, kemudian periksa yang panas. Dikongsi pengimbas hidup + isi_belakang."""
        logs = [l for l in logs if len(l["topics"]) == 4]
        agregat = defaultdict(lambda: [0, set()])
        bil_tx = defaultdict(int)
        penerima_tx = {}
        pertama = {}
        for l in logs:
            a = l["address"].lower()
            n = int(l["blockNumber"], 16)
            minit = ts_blok(n) // 60 * 60
            ke = _alamat(l["topics"][2])
            agregat[(a, minit)][0] += 1
            agregat[(a, minit)][1].add(ke)
            bil_tx[(a, l["transactionHash"])] += 1
            penerima_tx.setdefault((a, l["transactionHash"]), ke)
            pertama.setdefault(a, n)
        c = self.con
        for a, n in pertama.items():
            c.execute("""INSERT INTO kontrak (alamat, blok_pertama, ts_pertama) VALUES (?,?,?) ON CONFLICT(alamat) DO UPDATE
                         SET blok_pertama=MIN(blok_pertama, excluded.blok_pertama), ts_pertama=MIN(ts_pertama, excluded.ts_pertama)""",
                      (a, n, ts_blok(n)))
        for (a, minit), (m, pen) in agregat.items():
            c.execute("""INSERT INTO minit VALUES (?,?,?,?) ON CONFLICT(alamat, minit_ts)
                         DO UPDATE SET mint=mint+excluded.mint, penerima=penerima+excluded.penerima""", (a, minit, m, len(pen)))
            c.execute("UPDATE kontrak SET jumlah_mint=jumlah_mint+? WHERE alamat=?", (m, a))
            c.executemany("""INSERT INTO penerima VALUES (?,?,?) ON CONFLICT(alamat, penerima)
                             DO UPDATE SET minit_ts=MAX(minit_ts, excluded.minit_ts)""", [(a, ke, minit) for ke in pen])
        had = self.cfg["panas"]["sampel_tx"]
        for (a, tx), bil in bil_tx.items():
            ada = c.execute("SELECT COUNT(*) FROM sampel WHERE alamat=?", (a,)).fetchone()[0]
            if ada < had:
                c.execute("INSERT OR IGNORE INTO sampel VALUES (?,?,?,?)", (a, tx, penerima_tx[(a, tx)], bil))
        c.commit()  # lepaskan kunci tulis SEBELUM rangkaian: proses lain (hidup / isi_belakang) kena "database is locked" (diukur 29 Okt)
        self.periksa_panas(sekarang)

    def periksa_panas(self, sekarang):
        p = self.cfg["panas"]
        calon = self.con.execute("""
            SELECT m.alamat, SUM(m.mint) FROM minit m JOIN kontrak k ON k.alamat=m.alamat
            WHERE (k.diperiksa=0 OR k.ts_panas > ?) AND m.minit_ts BETWEEN ? AND ? GROUP BY m.alamat
            HAVING SUM(m.mint) >= ?
               AND (SELECT COUNT(*) FROM penerima r WHERE r.alamat=m.alamat AND r.minit_ts BETWEEN ? AND ?) >= ?""",
            # penerima = KESATUAN (kontrak, penerima) dalam tetingkap, bukan jumlah set per minit: 2 wallet × 10 minit
            # dahulu dikira 20 penerima (dilaporkan @jpl di Boltbook, 29 Okt)
            (sekarang, sekarang - p["tetingkap_minit"] * 60, sekarang, p["mint_min"],
             sekarang - p["tetingkap_minit"] * 60, sekarang, p["penerima_min"])).fetchall()
        if not calon:
            return
        kerja = [(a, self.con.execute("SELECT tx, penerima, bil FROM sampel WHERE alamat=?", (a,)).fetchall()) for a, _ in calon]
        with ThreadPoolExecutor(self.cfg["panas"]["benang"]) as ex:
            hasil = list(ex.map(lambda k: self._ambil(*k), kerja))
        for alamat, data in hasil:
            if data is None:
                continue  # rangkaian gagal: cuba semula pada cebisan seterusnya
            kelas, harga, nama, simbol = data
            kos = nilai.kos_masuk(harga, self._gas(), self.cfg["kertas"]) if harga is not None else None
            jumlah = self.con.execute("SELECT jumlah_mint FROM kontrak WHERE alamat=?", (alamat,)).fetchone()[0]
            self.con.execute("""UPDATE kontrak SET diperiksa=1, kelas=?, harga_bnb=?, kos_bnb=?, ts_panas=?, nama=?, simbol=?,
                                mint_semasa_panas=? WHERE alamat=?""", (kelas, harga, kos, sekarang, nama, simbol, jumlah, alamat))

    def harga_jualan(self, tx, bil, penjual=None, pembeli=None):
        """BNB + USDT/USDC/WBNB dari pembeli (resit). Selamat dalam benang. Rangkaian gagal = 0 (dilangkau)."""
        try:
            t = self.rpc.tx(tx)
            resit = self.rpc.resit(tx) if t else None
        except RpcGagal:
            return 0.0
        if self._bnb_usd is None:
            self._bnb_usd = harga_bnb_usd(self.cfg)
        token = {k: v for k, v in self.cfg["token_bayaran"].items() if k.startswith("0x")}
        return nilai.harga_jualan_bnb(t, resit, bil, token, self._bnb_usd, penjual, pembeli)

    def _gas(self):
        """Harga gas disimpan 5 minit — satu panggilan, bukan satu setiap kontrak."""
        if not self._gas_cache or time.time() - self._gas_cache[0] > 300:
            self._gas_cache = (time.time(), self.rpc.harga_gas())
        return self._gas_cache[1]

    def _panggil_rentetan(self, alamat, pemilih):
        try:
            return _rentetan(self.rpc.call(alamat, pemilih))
        except RpcGagal:
            return None  # kontrak tanpa name()/symbol() = revert, bukan rangkaian gagal

    def _ambil(self, alamat, sampel_db):
        """Rangkaian sahaja (selamat dalam benang): tx sampel → kelas; nama/simbol bila bukan airdrop."""
        sampel = []
        try:
            if self._bnb_usd is None:
                self._bnb_usd = harga_bnb_usd(self.cfg)
            token = {k: v for k, v in self.cfg["token_bayaran"].items() if k.startswith("0x")}
            for tx, penerima, bil in sampel_db:
                t = self.rpc.tx(tx)
                if t:
                    # value 0 ≠ percuma: mint boleh menarik USDT/USDC/WBNB dari pemint (dilaporkan @jpl) → baca resit
                    resit = self.rpc.resit(tx)
                    token_bnb = nilai.bayaran_token_bnb(t["from"], resit, token, self._bnb_usd)
                    sampel.append({"dari": t["from"], "penerima": penerima, "nilai_wei": int(t["value"], 16), "bil": bil,
                                   "token_bnb": token_bnb})
        except RpcGagal:
            return alamat, None
        kelas, harga = nilai.kelaskan(sampel, self.cfg["kelas"])
        nama = simbol = None
        if kelas != nilai.KELAS_AIRDROP:
            nama = self._panggil_rentetan(alamat, "0x06fdde03")
            simbol = self._panggil_rentetan(alamat, "0x95d89b41")
        abai = self.cfg.get("abai", {})
        if alamat in abai.get("alamat", []) or any(k in (nama or "").lower() for k in abai.get("nama_mengandungi", [])):
            kelas = "abai"  # tidak dijejak jualan, tidak masuk laporan
        return alamat, (kelas, harga, nama, simbol)

    def jejak_jualan(self):
        """Sekali setiap larian (bukan setiap cebisan): log Transfer DENGAN alamat dari `blok_jualan` → blok terkini diimbas,
        julat besar melalui `log_alamat`. Dahulu setiap 25 blok × setiap 40 kontrak = pengimbas hidup ketinggalan (diukur 29 Okt)."""
        j = self.cfg["jualan"]
        hingga = int(db.dapat(self.con, "blok", 0))
        dari = int(db.dapat(self.con, "blok_jualan", 0)) or hingga - 1
        if hingga <= dari or not self.titik:
            return 0
        ts_akhir = self.titik[1]
        ts_blok = lambda n: int(ts_akhir - (hingga - n) * 0.45)
        dijejak = [r[0] for r in self.con.execute(
            "SELECT alamat FROM kontrak WHERE kelas IN (?,?) AND ts_panas >= ?",
            (nilai.KELAS_PERCUMA, nilai.KELAS_BERBAYAR, ts_akhir - j["jejak_jam"] * 3600))]
        per_tx = defaultdict(lambda: [0, 0, None, None])
        for i in range(0, len(dijejak), j["alamat_setiap_log_maks"]):
            try:
                logs = self.rpc.log(dari + 1, hingga, [TRANSFER], dijejak[i:i + j["alamat_setiap_log_maks"]], "log_alamat")
            except RpcGagal:
                return 0  # cuba julat yang sama pada larian seterusnya
            for l in logs:
                if len(l["topics"]) == 4 and l["topics"][1] != SIFAR:
                    k = (l["address"].lower(), l["transactionHash"])
                    per_tx[k][0] += 1
                    per_tx[k][1] = int(l["blockNumber"], 16)
                    per_tx[k][2], per_tx[k][3] = _alamat(l["topics"][1]), _alamat(l["topics"][2])
        dikira = defaultdict(int)
        pilih = []
        for (a, tx), (bil, blok, penjual, pembeli) in per_tx.items():
            if dikira[a] < j["sampel_tx_setiap_kontrak"]:
                dikira[a] += 1
                pilih.append((a, tx, bil, blok, penjual, pembeli))
        with ThreadPoolExecutor(self.cfg["panas"]["benang"]) as ex:
            harga = list(ex.map(lambda t: self.harga_jualan(t[1], t[2], t[4], t[5]), pilih))
        for (a, tx, bil, blok, _, _), h in zip(pilih, harga):
            if h > 0:  # pindahan percuma (ke escrow, antara wallet sendiri) bukan jualan
                self.con.execute("INSERT OR IGNORE INTO jualan VALUES (?,?,?,?)", (a, tx, ts_blok(blok), h))
        db.tetap(self.con, "blok_jualan", hingga)
        self.con.commit()
        return len(pilih)

    def kemas(self, sekarang):
        """Buang kiraan minit lama + kontrak sampah (tidak pernah panas) > 3 hari supaya DB kecil."""
        had = sekarang - 3 * 86400
        self.con.execute("DELETE FROM minit WHERE minit_ts < ?", (had,))
        self.con.execute("DELETE FROM penerima WHERE minit_ts < ?", (sekarang - 86400,))
        self.con.execute("DELETE FROM sampel WHERE alamat IN (SELECT alamat FROM kontrak WHERE diperiksa=0 AND ts_pertama < ?)", (had,))
        self.con.execute("DELETE FROM kontrak WHERE diperiksa=0 AND ts_pertama < ?", (had,))
        self.con.commit()

    def larian(self):
        im = self.cfg["imbas"]
        julat = self.cfg["rpc"]["julat_log_maks"]
        tamat = time.time() + im["saat_setiap_larian"]
        logs = cebis = 0
        while time.time() < tamat:
            terkini = self.rpc.blok_terkini()
            blok = int(db.dapat(self.con, "blok", 0))
            if not blok:
                blok = terkini - im["mula_dari_belakang_blok"]
                db.tetap(self.con, "blok_mula", blok + 1)  # isi_belakang berhenti di sini
            if terkini - blok > im["tertinggal_maks_blok"]:
                db.tetap(self.con, "jurang_blok", int(db.dapat(self.con, "jurang_blok", 0)) + terkini - blok)
                blok = terkini - im["mula_dari_belakang_blok"]
            if blok >= terkini:
                time.sleep(im["rehat_saat"])
                continue
            hingga = min(blok + julat, terkini)
            try:
                logs += self.cebisan(blok + 1, hingga)
            except (RpcGagal, sqlite3.OperationalError) as e:
                self.con.rollback()
                try:
                    db.tetap(self.con, "ralat_terakhir", f"{int(time.time())} {str(e)[:300]}")
                    self.con.commit()
                except sqlite3.OperationalError:
                    pass  # DB sibuk: ralat itu sendiri tidak boleh menumbangkan larian
                time.sleep(im["rehat_saat"] * 3)
                continue
            cebis += 1
        if self.titik:
            self.jejak_jualan()
            self.kemas(self.titik[1])
        return cebis, logs
