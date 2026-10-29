"""Isi belakang: jawab soalan "untung atau tidak" dari SEJARAH rantaian, bukan menunggu 7 hari.

Laluan 1 — cebisan mint (tanpa alamat, had 25 blok) dari N jam lepas hingga `blok_mula` pengimbas hidup, diambil serentak
           beberapa benang, diproses mengikut urutan (logik panas/kelas sama dengan pengimbas hidup).
Laluan 2 — untuk setiap kontrak mint percuma/murah: log Transfer DENGAN alamat (julat besar, `rpc.log_alamat`) → tx sampel →
           jualan BNB. Masa blok dianggar secara linear antara dua titik sauh (BSC ~0.45 s/blok, stabil).
"""
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from . import db, nilai
from .imbas import SIFAR, TRANSFER, Pengimbas
from .rpc import RpcGagal


def _jam_ke_ts(rpc, dari, hingga):
    t0, t1 = rpc.masa_blok(dari), rpc.masa_blok(hingga)
    sela = (t1 - t0) / max(1, hingga - dari)
    return lambda n: int(t0 + (n - dari) * sela)


def _log_cuba(rpc, dari, hingga, topics, alamat=None, peranan="log"):
    for cubaan in range(4):
        try:
            return rpc.log(dari, hingga, topics, alamat, peranan)
        except RpcGagal:
            time.sleep(2 * (cubaan + 1))
    raise RpcGagal(f"log {dari}-{hingga} gagal 4×")


def laluan_mint(cfg, rpc, con, jam, cetak=print):
    ib = cfg["isi_belakang"]
    hujung = int(db.dapat(con, "blok_mula", 0)) or rpc.blok_terkini()
    mula = int(db.dapat(con, "isi_belakang_blok", 0)) or hujung - int(jam * 3600 / 0.45)
    ts_blok = _jam_ke_ts(rpc, mula, hujung)
    julat = cfg["rpc"]["julat_log_maks"]
    p = Pengimbas(cfg, rpc, con)
    # sejarah memakai kuota SENDIRI (URL peribadi) supaya pengimbas hidup tidak kebuluran 429 (diukur 29 Okt: +100 blok / 3 min)
    peranan = "log_sejarah" if rpc.cfg.get("log_sejarah") else "log"
    benang = ib["benang"]
    if rpc.cfg.get("log_besar"):  # RPC yang membenarkan julat besar tanpa alamat (NodeReal): ratusan kali kurang panggilan
        peranan, julat, benang = "log_besar", ib["julat_besar"], ib["benang_besar"]
    cetak(f"  peranan log: {peranan}, julat {julat}")
    cebis = [(b, min(b + julat - 1, hujung - 1)) for b in range(mula, hujung, julat)]
    cetak(f"laluan 1: {len(cebis)} cebisan, blok {mula}–{hujung}")
    kelompok_saiz = ib["kelompok"] if julat <= 100 else benang
    with ThreadPoolExecutor(benang) as ex:
        for i in range(0, len(cebis), kelompok_saiz):
            kelompok = cebis[i:i + kelompok_saiz]
            hasil = list(ex.map(lambda c: _log_cuba(rpc, c[0], c[1], [TRANSFER, SIFAR], None, peranan), kelompok))
            for (dari, hingga), logs in zip(kelompok, hasil):
                p.proses_mint(logs, ts_blok, ts_blok(hingga))
            db.tetap(con, "isi_belakang_blok", kelompok[-1][1] + 1)
            con.commit()
            if i // kelompok_saiz % 10 == 0:
                cetak(f"  {i + len(kelompok)}/{len(cebis)}")
    return mula, hujung, ts_blok


def laluan_jualan(cfg, rpc, con, mula, hujung, ts_blok, cetak=print):
    ib = cfg["isi_belakang"]
    dijejak = [r[0] for r in con.execute("SELECT alamat FROM kontrak WHERE kelas IN (?,?) AND ts_panas <= ?",
                                         (nilai.KELAS_PERCUMA, nilai.KELAS_BERBAYAR, ts_blok(hujung)))]
    cetak(f"laluan 2: {len(dijejak)} kontrak dijejak")
    per_tx = defaultdict(lambda: [0, 0, None, None])
    span = ib["julat_alamat"]
    tugas = [(dijejak[i:i + ib["alamat_setiap_log"]], b, min(b + span - 1, hujung - 1))
             for i in range(0, len(dijejak), ib["alamat_setiap_log"]) for b in range(mula, hujung, span)]
    with ThreadPoolExecutor(ib["benang"]) as ex:
        for logs in ex.map(lambda t: _log_cuba(rpc, t[1], t[2], [TRANSFER], t[0], "log_alamat"), tugas):
            for l in logs:
                if len(l["topics"]) == 4 and l["topics"][1] != SIFAR:
                    k = (l["address"].lower(), l["transactionHash"])
                    per_tx[k][0] += 1
                    per_tx[k][1] = int(l["blockNumber"], 16)
                    per_tx[k][2], per_tx[k][3] = "0x" + l["topics"][1][-40:], "0x" + l["topics"][2][-40:]
    # sampel tx tersebar sama rata ikut masa untuk setiap kontrak
    ikut = defaultdict(list)
    for (a, tx), (bil, blok, penjual, pembeli) in per_tx.items():
        ikut[a].append((blok, tx, bil, penjual, pembeli))
    pilih = []
    for a, senarai in ikut.items():
        senarai.sort()
        langkah = max(1, len(senarai) // ib["tx_setiap_kontrak"])
        pilih += [(a, tx, bil, blok, pj, pb) for blok, tx, bil, pj, pb in senarai[::langkah]]
    cetak(f"  {len(per_tx)} pindahan, {len(pilih)} tx disemak")

    p = Pengimbas(cfg, rpc, con)
    with ThreadPoolExecutor(ib["benang"]) as ex:
        for (a, tx, bil, blok, _, _), harga in zip(pilih, ex.map(lambda t: p.harga_jualan(t[1], t[2], t[4], t[5]), pilih)):
            if harga > 0:
                con.execute("INSERT OR IGNORE INTO jualan VALUES (?,?,?,?)", (a, tx, ts_blok(blok), harga))
    con.commit()


def jalan(cfg, rpc, con, jam, cetak=print):
    mula_asal = int(db.dapat(con, "isi_belakang_blok", 0))
    mula, hujung, ts_blok = laluan_mint(cfg, rpc, con, jam, cetak)
    if mula_asal:  # sambung larian yang terputus: laluan 2 mesti meliputi dari mula sebenar
        mula = int(db.dapat(con, "isi_belakang_mula", mula))
    db.tetap(con, "isi_belakang_mula", mula)
    con.commit()
    laluan_jualan(cfg, rpc, con, int(db.dapat(con, "isi_belakang_mula")), hujung, _jam_ke_ts(rpc, int(db.dapat(con, "isi_belakang_mula")), hujung), cetak)
