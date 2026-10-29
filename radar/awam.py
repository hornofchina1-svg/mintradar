"""Data AWAM untuk datt.my: apa yang radar nampak + keputusan kertas. TIADA wallet, tiada mint sebenar, tiada strategi
pemilihan/jual (enjin wang kekal peribadi — keputusan pemilik 29 Okt). Ditulis atomik ke awam/stats.json."""
import html
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
    render_laman(data, folder.parent / "laman")
    return data


def _lalu(ts, sekarang):
    m = max(0, (sekarang - ts) // 60)
    return f"{m} min ago" if m < 90 else f"{round(m / 60)} h ago"


def render_html(data, templat, bahasa):
    """Isi jadual dalam HTML statik (EN) supaya pembaca tanpa JS (ejen yang curl laman) nampak data sebenar; apl.js
    menulis semula selepas dimuat. Diukur 29 Okt: pengulas Boltbook melaporkan 'tabel demo kosong'."""
    e = html.escape
    t = bahasa["en"]
    sekarang = data["dijana"]
    baris = "".join(
        f'<tr><td><span class="nama-koleksi">{e(x["nama"] or t["tanpa_nama"])}</span><span class="alamat">{e(x["alamat"][:6])}\u2026{e(x["alamat"][-4:])}</span></td>'
        f'<td><span class="jenis jenis-{e(x["kelas"])}">{e(t["jenis_" + x["kelas"]])}</span></td>'
        f'<td class="nombor">{x["mint"]:,}</td><td class="nombor">{_lalu(x["ts_panas"], sekarang)}</td></tr>'
        for x in data["terbaru"])
    def bnb(v):
        return ("+" if v >= 0 else "\u2212") + f"{abs(v):.4f} BNB"
    kertas = "".join(
        f'<div><dt>{e(t["kertas_jual"].replace("{jam}", str(k["jam"])))}</dt>'
        f'<dd class="bersih {"positif" if k["bersih_bnb"] >= 0 else "negatif"}">{bnb(k["bersih_bnb"])}</dd>'
        f'<dd class="butir">{e(t["kertas_baris"].replace("{mint}", str(k["mint"])).replace("{untung}", str(k["untung"])).replace("{pembeli}", str(k["ada_pembeli"])))}</dd></div>'
        for k in data["kertas"] if k["mint"])
    teratas = "".join(
        f'<li><span class="nama-koleksi">{e(w["nama"] or w["alamat"])}</span><span class="bersih positif">{bnb(w["bersih_bnb"])}</span>'
        f'<span class="butir">{e(t["teratas_jualan"].replace("{n}", str(w["jualan"])))}</span></li>' for w in data["teratas_24j"])
    masa = time.strftime("%d %b %Y %H:%M UTC", time.gmtime(sekarang))
    out = templat.replace('<tbody id="senarai-sentuhan"></tbody>', f'<tbody id="senarai-sentuhan">{baris}</tbody>')
    out = out.replace('<dl id="senarai-kertas" class="tetingkap"></dl>', f'<dl id="senarai-kertas" class="tetingkap">{kertas}</dl>')
    out = out.replace('<ol id="senarai-teratas" class="pemenang"></ol>', f'<ol id="senarai-teratas" class="pemenang">{teratas}</ol>')
    kaki = t["kaki_dijana"].replace("{masa}", masa).replace("{blok}", f"{data['blok']:,}")
    out = out.replace('<p id="kaki-data" aria-live="polite"></p>', f'<p id="kaki-data" aria-live="polite">{e(kaki)}</p>')
    return out


def render_laman(data, folder_laman):
    """hidup/laman/index.html dijana semula daripada index.templat.html (salinan asal yang deploy.sh simpan)."""
    folder_laman = Path(folder_laman)
    templat = folder_laman / "index.templat.html"
    if not templat.exists():
        return False
    bahasa = json.loads((folder_laman / "bahasa.json").read_text())
    sementara = folder_laman / ".index.html.tmp"
    sementara.write_text(render_html(data, templat.read_text(), bahasa))
    os.replace(sementara, folder_laman / "index.html")
    return True
