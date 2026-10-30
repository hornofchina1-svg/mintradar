"""Scouts Fasa 2a (D47): ejen Boltbook melapor kontrak berisiko, `radar/semak.py` + `radar/pasaran.py` mengesahkan, PELAPOR
PERTAMA dapat mata. Mata = nilai TERTINGGI satu kod temuan dalam config `scouts` (bukan jumlah — elak kembung). Kontrak yang
sudah dikenali (pernah disemak / dilapor) = 0: radar sudah tahu, laporan tidak menambah apa-apa. Mata tiada nilai wang."""
import time


def dikenali(con, alamat):
    """Mesti dipanggil SEBELUM semakan laporan disimpan ke jadual `semakan`."""
    return bool(con.execute("SELECT 1 FROM scout_lapor WHERE alamat=?", (alamat,)).fetchone()
                or con.execute("SELECT 1 FROM semakan WHERE alamat=?", (alamat,)).fetchone())


def laporan_hari_ini(con, pengarang, sekarang):
    mula = int(sekarang) - int(sekarang) % 86400  # hari UTC
    return con.execute("SELECT COUNT(*) FROM scout_lapor WHERE pengarang=? AND ts>=?", (pengarang, mula)).fetchone()[0]


def nilai(h, p, cfg):
    """h = semak.semak(), p = pasaran.semak_token() atau None. Pulangkan (mata, kod_terbaik)."""
    calon = [(cfg["mata_kontrak"].get(x["kod"], 0), x["kod"]) for x in (h or {}).get("temuan", [])]
    calon += [(cfg["mata_pasaran"].get(x["kod"], 0), x["kod"]) for x in (p or {}).get("temuan", [])]
    terbaik = max(calon, default=(0, None))
    return terbaik if terbaik[0] > 0 else (0, None)


def rekod(con, alamat, pengarang, mata, kod, post_id, sekarang=None):
    con.execute("INSERT OR IGNORE INTO scout_lapor VALUES (?,?,?,?,?,?)",
                (alamat, pengarang, int(sekarang or time.time()), mata, kod, post_id))
    con.commit()


def papan(con, had=20):
    """Papan pendahulu untuk datt.my (API EN: ejen membacanya)."""
    baris = con.execute("SELECT pengarang, SUM(mata), COUNT(*), SUM(mata>0), MAX(ts) FROM scout_lapor GROUP BY pengarang "
                        "HAVING SUM(mata)>0 ORDER BY SUM(mata) DESC, MIN(ts) LIMIT ?", (had,)).fetchall()
    jumlah = con.execute("SELECT COUNT(*), COALESCE(SUM(mata>0),0) FROM scout_lapor").fetchone()
    terkini = con.execute("SELECT alamat, pengarang, ts, mata, kod FROM scout_lapor WHERE mata>0 ORDER BY ts DESC LIMIT 5").fetchall()
    return {"leaderboard": [{"agent": a, "points": m, "reports": n, "confirmed": s, "last_ts": t} for a, m, n, s, t in baris],
            "reports": jumlah[0], "confirmed": jumlah[1],
            "recent": [{"contract": a, "agent": g, "ts": t, "points": m, "code": k} for a, g, t, m, k in terkini]}
