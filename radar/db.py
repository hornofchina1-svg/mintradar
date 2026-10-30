"""SQLite di state/ (atau $MINTRADAR_STATE untuk ujian)."""
import json
import os
import sqlite3
from pathlib import Path

SKEMA = """
CREATE TABLE IF NOT EXISTS keadaan (kunci TEXT PRIMARY KEY, nilai TEXT);
CREATE TABLE IF NOT EXISTS kontrak (
  alamat TEXT PRIMARY KEY, nama TEXT, simbol TEXT,
  blok_pertama INTEGER, ts_pertama INTEGER, jumlah_mint INTEGER DEFAULT 0,
  diperiksa INTEGER DEFAULT 0, kelas TEXT, harga_bnb REAL, kos_bnb REAL, ts_panas INTEGER, mint_semasa_panas INTEGER
);
CREATE TABLE IF NOT EXISTS minit (alamat TEXT, minit_ts INTEGER, mint INTEGER, penerima INTEGER, PRIMARY KEY (alamat, minit_ts));
CREATE TABLE IF NOT EXISTS sampel (alamat TEXT, tx TEXT, penerima TEXT, bil INTEGER, PRIMARY KEY (alamat, tx));
CREATE TABLE IF NOT EXISTS jualan (alamat TEXT, tx TEXT, ts INTEGER, harga_bnb REAL, PRIMARY KEY (alamat, tx));
CREATE TABLE IF NOT EXISTS penerima (alamat TEXT, penerima TEXT, minit_ts INTEGER, PRIMARY KEY (alamat, penerima));
CREATE INDEX IF NOT EXISTS penerima_ts ON penerima (alamat, minit_ts);
CREATE TABLE IF NOT EXISTS semakan (alamat TEXT PRIMARY KEY, ts INTEGER, label TEXT, temuan TEXT, admin TEXT, nama_kontrak TEXT);
CREATE TABLE IF NOT EXISTS pasaran (alamat TEXT PRIMARY KEY, ts INTEGER, label TEXT, temuan TEXT, ringkas TEXT, bundle TEXT);
CREATE INDEX IF NOT EXISTS minit_ts ON minit (minit_ts);
CREATE INDEX IF NOT EXISTS kontrak_panas ON kontrak (ts_panas);
"""


def simpan_pasaran(con, alamat, p, ts):
    """D34: hasil radar/pasaran.semak_token → API datt.my (bahagian "market")."""
    con.execute("INSERT OR REPLACE INTO pasaran VALUES (?,?,?,?,?,?)",
                (alamat, ts, p["label"], json.dumps(p["temuan"]), json.dumps(p["ringkas"]), json.dumps(p.get("bundle"))))
    con.commit()


def folder_state():
    return Path(os.environ.get("MINTRADAR_STATE") or Path(__file__).resolve().parent.parent / "state")


def buka():
    f = folder_state()
    f.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f / "radar.db", timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")  # 4 penulis (imbas, mint, jual, isi-belakang) — diukur "database is locked" 29 Okt
    con.executescript(SKEMA)
    return con


def dapat(con, kunci, lalai=None):
    r = con.execute("SELECT nilai FROM keadaan WHERE kunci=?", (kunci,)).fetchone()
    return r[0] if r else lalai


def tetap(con, kunci, nilai):
    con.execute("INSERT INTO keadaan VALUES (?,?) ON CONFLICT(kunci) DO UPDATE SET nilai=excluded.nilai", (kunci, str(nilai)))
