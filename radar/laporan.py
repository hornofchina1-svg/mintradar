"""Laporan harian bahasa biasa: kalau bot mint setiap free/murah mint yang dikesan, untung atau rugi berapa?"""
import json
import urllib.request

from . import nilai


def harga_bnb_usd(cfg):
    try:
        with urllib.request.urlopen("https://api.binance.com/api/v3/ticker/price?symbol=BNBUSDT", timeout=10) as r:
            return float(json.load(r)["price"])
    except (OSError, ValueError, KeyError):
        return cfg["kertas"]["bnb_usd_lalai"]


def kedudukan(con, cfg, sekarang):
    """Setiap kontrak mint percuma/murah = satu kedudukan kertas. Tetingkap yang belum tamat ditanda None."""
    k = cfg["kertas"]
    hasil = []
    rows = con.execute("""SELECT alamat, nama, simbol, kelas, harga_bnb, kos_bnb, ts_panas, ts_pertama, mint_semasa_panas, jumlah_mint
                          FROM kontrak WHERE kelas IN (?,?) ORDER BY ts_panas""", (nilai.KELAS_PERCUMA, nilai.KELAS_BERBAYAR))
    abai = cfg.get("abai", {})
    for a, nama, simbol, kelas, harga, kos, ts_panas, ts_pertama, mint_panas, jumlah in rows.fetchall():
        if a in abai.get("alamat", []) or any(k in (nama or "").lower() for k in abai.get("nama_mengandungi", [])):
            continue
        jualan = con.execute("SELECT ts, harga_bnb FROM jualan WHERE alamat=?", (a,)).fetchall()
        pnl = {}
        for jam in k["tetingkap_jam"]:
            pnl[jam] = nilai.pnl_tetingkap(ts_panas, kos, jualan, jam, k["yuran_pasaran"]) if sekarang >= ts_panas + jam * 3600 else None
        hasil.append({"alamat": a, "nama": nama or simbol or a[:10], "kelas": kelas, "harga": harga, "kos": kos,
                      "ts_panas": ts_panas, "lewat_minit": (ts_panas - ts_pertama) // 60,
                      "mint_panas": mint_panas, "jumlah": jumlah, "jualan": len(jualan), "pnl": pnl})
    return hasil


def tulis(con, cfg, sekarang):
    k = cfg["kertas"]
    usd = harga_bnb_usd(cfg)
    rm = lambda bnb: bnb * usd * k["usd_myr"]
    semua = kedudukan(con, cfg, sekarang)
    baru = [x for x in semua if x["ts_panas"] >= sekarang - 86400]
    baris = [f"📡 MintRadar (KERTAS, tiada duit sebenar) — {len(baru)} mint percuma/murah dikesan 24 j lepas, {len(semua)} sejak mula."]
    for jam in k["tetingkap_jam"]:
        siap = [x for x in semua if x["pnl"][jam] is not None]
        if not siap:
            baris.append(f"• Jual selepas {jam} j: belum cukup data.")
            continue
        jum, menang, kalah, ada = nilai.ringkas_pnl([x for x in siap], jam)
        baris.append(f"• Jual selepas {jam} j: {len(siap)} mint → untung {menang}, rugi {kalah}, ada pembeli {ada}. "
                     f"Bersih {jum:+.4f} BNB ≈ RM{rm(jum):+.2f}.")
    siap24 = sorted((x for x in semua if x["pnl"][24] is not None), key=lambda x: -x["pnl"][24][0])
    if siap24:
        baris.append("Terbaik (24 j):")
        for x in siap24[:cfg["laporan"]["teratas"]]:
            p, m, bil = x["pnl"][24]
            baris.append(f"  {x['nama']}: {p:+.4f} BNB (RM{rm(p):+.2f}), {bil} jualan, dikesan {x['lewat_minit']} min selepas mint pertama")
    try:
        m = con.execute("SELECT COUNT(*), COALESCE(SUM(gas),0) FROM mint_sebenar WHERE status='dihantar'").fetchone()
        st = dict(con.execute("SELECT status, COUNT(*) FROM pegangan GROUP BY status").fetchall())
        hasil_jual = con.execute("SELECT COALESCE(SUM(harga_bnb),0) FROM pegangan WHERE status='terjual'").fetchone()[0]
        kos = m[1] * 0.05e9 / 1e18  # anggaran gas pada 0.05 gwei
        bersih = hasil_jual * (1 - cfg["jual"]["yuran_platform_mata"] / 10000) - kos
        baris.append(f"💰 SEBENAR: {m[0]} mint (gas ≈ {kos:.5f} BNB), disenarai {st.get('disenarai', 0)}, terjual {st.get('terjual', 0)}, "
                     f"dipegang {st.get('dipegang', 0) + st.get('tidak_diindeks', 0)}. Bersih ≈ {bersih:+.5f} BNB (RM{rm(bersih):+.2f}).")
    except Exception:  # noqa: BLE001 — jadual Fasa 2 belum wujud pada DB lama
        pass
    jumlah_panas = con.execute("SELECT COUNT(*), SUM(kelas='airdrop'), SUM(kelas='mint_mahal') FROM kontrak WHERE diperiksa=1 AND ts_panas >= ?",
                               (sekarang - 86400,)).fetchone()
    baris.append(f"Kontrak panas 24 j: {jumlah_panas[0] or 0} (airdrop/spam {jumlah_panas[1] or 0}, mahal {jumlah_panas[2] or 0}). "
                 f"BNB ${usd:.0f}. Andaian: mint 1 bila dikesan, jual pada median harga jualan; tiada pembeli = rugi kos.")
    return "\n".join(baris)
