"""Data AWAM untuk datt.my: apa yang radar nampak + keputusan kertas. TIADA wallet, tiada mint sebenar, tiada strategi
pemilihan/jual (enjin wang kekal peribadi — keputusan pemilik 29 Okt). Ditulis atomik ke awam/stats.json."""
import json
import os
import time
from pathlib import Path

from . import laporan, nilai


def bina(con, cfg, sekarang):
    k = cfg["kertas"]
    semua = laporan.kedudukan(con, cfg, sekarang)
    kertas = []
    for jam in k["tetingkap_jam"]:
        siap = [x for x in semua if x["pnl"][jam] is not None]
        jum, menang, kalah, ada = nilai.ringkas_pnl(siap, jam) if siap else (0, 0, 0, 0)
        kertas.append({"jam": jam, "mint": len(siap), "untung": menang, "rugi": kalah, "ada_pembeli": ada, "bersih_bnb": round(jum, 6)})
    abai = cfg.get("abai", {})
    baru = []
    for a, nama, simbol, kelas, ts_panas, ts_pertama, jumlah in con.execute(
            """SELECT alamat, nama, simbol, kelas, ts_panas, ts_pertama, jumlah_mint FROM kontrak
               WHERE diperiksa=1 AND kelas IN ('mint_percuma','mint_berbayar','airdrop') ORDER BY ts_panas DESC LIMIT 60"""):
        if a in abai.get("alamat", []) or any(x in (nama or "").lower() for x in abai.get("nama_mengandungi", [])):
            continue
        baru.append({"alamat": a, "nama": nama or simbol or None, "kelas": kelas, "ts_panas": ts_panas,
                     "ts_pertama": ts_pertama, "mint": jumlah})
        if len(baru) >= 15:
            break
    siap24 = sorted((x for x in semua if x["pnl"][24] is not None), key=lambda x: -x["pnl"][24][0])
    teratas = [{"nama": x["nama"], "alamat": x["alamat"], "bersih_bnb": round(x["pnl"][24][0], 6), "jualan": x["pnl"][24][2]}
               for x in siap24[:5] if x["pnl"][24][0] > 0]
    hari = con.execute("""SELECT COUNT(*), SUM(kelas='mint_percuma'), SUM(kelas='airdrop') FROM kontrak
                          WHERE diperiksa=1 AND ts_panas >= ?""", (sekarang - 86400,)).fetchone()
    return {
        "dijana": sekarang,
        "rantaian": "BNB Smart Chain",
        "blok": int(con.execute("SELECT nilai FROM keadaan WHERE kunci='blok'").fetchone()[0]),
        "hari": {"panas": hari[0] or 0, "percuma": hari[1] or 0, "airdrop": hari[2] or 0},
        "kertas": kertas,
        "teratas_24j": teratas,
        "terbaru": baru,
        "andaian": {"yuran": k["yuran_pasaran"], "gas_mint": k["gas_mint"]},
    }


def tulis(con, cfg, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    data = bina(con, cfg, int(time.time()))
    sementara = folder / ".stats.json.tmp"
    sementara.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    os.replace(sementara, folder / "stats.json")  # nginx tidak pernah nampak fail separuh
    return data
