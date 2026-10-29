#!/usr/bin/env python3
"""MintRadar — read-only radar of BNB Chain free mints. Commands: imbas (scan, run every minute) · isi-belakang [--jam N] (backfill) ·
isi-jualan [--padam] · laporan [--hantar] · awam (writes hidup/data/stats.json) · status."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from radar import awam, db, isi_belakang, laporan
from radar.imbas import Pengimbas
from radar.rpc import Rpc

AKAR = Path(__file__).resolve().parent


def cfg():
    return json.loads((AKAR / "config.json").read_text())


def rpc_peribadi():
    f = db.folder_state() / "rpc-peribadi.txt"
    if not f.exists():
        return []
    # satu baris = "<url> [peranan,peranan]"; tanpa peranan = rpc.peribadi_peranan
    hasil = []
    for l in f.read_text().splitlines():
        bahagian = l.split()
        if bahagian and bahagian[0].startswith("http"):
            hasil.append((bahagian[0], bahagian[1].split(",") if len(bahagian) > 1 else None))
    return hasil


def main(argv):
    c = cfg()
    con = db.buka()
    rpc = Rpc(c["rpc"], rpc_peribadi())
    arahan = argv[1] if len(argv) > 1 else "status"
    if arahan == "imbas":
        cebis, logs = Pengimbas(c, rpc, con).larian()
        print(f"cebisan {cebis}, log mint {logs}, blok {db.dapat(con, 'blok')}")
    elif arahan == "isi-belakang":
        jam = float(argv[argv.index("--jam") + 1]) if "--jam" in argv else c["isi_belakang"]["jam_lalai"]
        isi_belakang.jalan(c, rpc, con, jam, lambda m: print(m, flush=True))
        print(laporan.tulis(con, c, int(time.time())))
    elif arahan == "isi-jualan":  # ulang laluan 2 sahaja (selepas membaiki logik harga), atas julat isi-belakang terakhir
        mula, hujung = int(db.dapat(con, "isi_belakang_mula")), int(db.dapat(con, "blok_mula"))
        if "--padam" in argv:
            con.execute("DELETE FROM jualan"); con.commit()
        isi_belakang.laluan_jualan(c, rpc, con, mula, hujung, isi_belakang._jam_ke_ts(rpc, mula, hujung), lambda m: print(m, flush=True))
        print(laporan.tulis(con, c, int(time.time())))
    elif arahan == "awam":  # stats.json untuk datt.my (data radar sahaja, tiada wallet/enjin)
        d = awam.tulis(con, c, AKAR / "hidup" / "data", rpc)
        print(f"stats.json: {len(d['terbaru'])} sentuhan, kertas {[x['bersih_bnb'] for x in d['kertas']]}")
    elif arahan == "laporan":
        teks = laporan.tulis(con, c, int(time.time()))
        print(teks)
        if "--hantar" in argv and os.environ.get("MINTRADAR_NOTIFY"):  # e.g. a script that forwards text to Telegram
            subprocess.run([os.environ["MINTRADAR_NOTIFY"], teks, c["laporan"]["tahap_notify"]], check=False)
    elif arahan == "status":
        r = con.execute("SELECT COUNT(*), SUM(diperiksa), SUM(kelas IN ('mint_percuma','mint_berbayar')) FROM kontrak").fetchone()
        j = con.execute("SELECT COUNT(*) FROM jualan").fetchone()[0]
        print(f"blok {db.dapat(con, 'blok')} · kontrak {r[0]} · panas {r[1] or 0} · dijejak {r[2] or 0} · jualan {j} · "
              f"jurang {db.dapat(con, 'jurang_blok', 0)} · ralat {db.dapat(con, 'ralat_terakhir', '-')}")
        for row in con.execute("""SELECT alamat, nama, kelas, harga_bnb, jumlah_mint, datetime(ts_panas,'unixepoch')
                                  FROM kontrak WHERE diperiksa=1 ORDER BY ts_panas DESC LIMIT 15"""):
            print(" ", row)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
