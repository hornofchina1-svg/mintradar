"""Data AWAM untuk datt.my: apa yang radar nampak + keputusan kertas. TIADA wallet, tiada mint sebenar, tiada strategi
pemilihan/jual (enjin wang kekal peribadi — keputusan pemilik 29 Okt). Ditulis atomik ke awam/stats.json."""
import html
import json
import os
import time
from pathlib import Path

from . import laporan, nilai, semak


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
        sm = con.execute("SELECT label, temuan FROM semakan WHERE alamat=?", (a,)).fetchone()
        baru.append({"alamat": a, "nama": nama or simbol or None, "kelas": kelas, "ts_panas": ts_panas,
                     "ts_pertama": ts_pertama, "mint": jumlah,
                     "keselamatan": {"label": sm[0], "temuan": json.loads(sm[1])} if sm else None})
        if len(baru) >= 15:
            break
    siap24 = sorted((x for x in semua if x["pnl"][24] is not None), key=lambda x: -x["pnl"][24][0])
    teratas = [{"nama": x["nama"], "alamat": x["alamat"], "bersih_bnb": round(x["pnl"][24][0], 6), "jualan": x["pnl"][24][2]}
               for x in siap24[:5] if x["pnl"][24][0] > 0]
    hari = con.execute("""SELECT COUNT(*), SUM(kelas='mint_percuma'), SUM(kelas='airdrop') FROM kontrak
                          WHERE diperiksa=1 AND ts_panas >= ?""", (sekarang - 86400,)).fetchone()
    amaran = []
    for a, label, temuan, nama in con.execute(
            """SELECT s.alamat, s.label, s.temuan, COALESCE(k.nama, s.nama_kontrak) FROM semakan s LEFT JOIN kontrak k ON k.alamat=s.alamat
               WHERE s.label='merah' AND s.temuan NOT LIKE '%TIDAK_DISAHKAN%' ORDER BY s.ts DESC LIMIT 8"""):
        amaran.append({"alamat": a, "nama": nama, "temuan": json.loads(temuan)})
    disemak = dict(con.execute("SELECT label, COUNT(*) FROM semakan WHERE ts >= ? GROUP BY label", (sekarang - 86400,)).fetchall())
    return {
        "dijana": sekarang,
        "semakan_24j": {"hijau": disemak.get("hijau", 0), "kuning": disemak.get("kuning", 0), "merah": disemak.get("merah", 0)},
        "amaran": amaran,
        "rantaian": "BNB Smart Chain",
        "blok": int(con.execute("SELECT nilai FROM keadaan WHERE kunci='blok'").fetchone()[0]),
        "hari": {"panas": hari[0] or 0, "percuma": hari[1] or 0, "airdrop": hari[2] or 0},
        "kertas": kertas,
        "teratas_24j": teratas,
        "terbaru": baru,
        "andaian": {"yuran": k["yuran_pasaran"], "gas_mint": k["gas_mint"]},
    }


def semak_baharu(con, cfg, rpc):
    """Semak kontrak sentuhan terkini yang belum disemak (atau semakan lama). Had setiap larian: config `semak`."""
    k = cfg["semak"]
    sekarang = int(time.time())
    calon = [a for (a,) in con.execute(
        """SELECT k.alamat FROM kontrak k LEFT JOIN semakan s ON s.alamat=k.alamat
           WHERE k.diperiksa=1 AND k.kelas IN ('mint_percuma','mint_berbayar') AND k.ts_panas >= ?
             AND (s.alamat IS NULL OR s.ts < ?) ORDER BY k.ts_panas DESC LIMIT ?""",
        (sekarang - k["umur_kontrak_jam"] * 3600, sekarang - k["semak_semula_jam"] * 3600, k["setiap_larian"]))]
    for a in calon:
        try:
            h = semak.semak(rpc, a)
        except Exception:  # noqa: BLE001 — Sourcify/RPC sibuk: cuba larian seterusnya
            continue
        con.execute("INSERT OR REPLACE INTO semakan VALUES (?,?,?,?,?,?)",
                    (a, sekarang, h["label"], json.dumps(h["temuan"]), json.dumps(h["admin"]), h.get("nama_kontrak")))
    con.commit()
    return len(calon)


def tulis(con, cfg, folder, rpc=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if rpc is not None:
        semak_baharu(con, cfg, rpc)
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
    def teks_temuan(x):
        return t["temuan_" + x["kod"]].replace("{fungsi}", (x["fungsi"] + "()") if x["fungsi"] else "")

    def sel(k):
        label = k["label"] if k else "belum"
        out = f'<td class="selamat"><span class="lencana lencana-{e(label)}">{e(t["label_" + label])}</span>'
        if k and k["temuan"]:
            unik = list({x["kod"]: x for x in k["temuan"]}.values())[:2]
            out += f'<span class="temuan">{e(" ".join(teks_temuan(x) for x in unik))}</span>'
        return out + "</td>"
    baris = "".join(
        f'<tr><td><span class="nama-koleksi">{e(x["nama"] or t["tanpa_nama"])}</span><span class="alamat">{e(x["alamat"][:6])}\u2026{e(x["alamat"][-4:])}</span></td>'
        f'<td><span class="jenis jenis-{e(x["kelas"])}">{e(t["jenis_" + x["kelas"]])}</span></td>{sel(x.get("keselamatan"))}'
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
    amaran = "".join(
        f'<li><span class="nama-koleksi">{e(a["nama"] or a["alamat"])}</span><span class="alamat">{e(a["alamat"])}</span>'
        + "".join(f'<span class="temuan">{e(teks_temuan(x))}</span>' for x in a["temuan"] if x["kod"] in ("KEKAL_DANA", "PROKSI"))
        + "</li>" for a in data.get("amaran", [])) or f'<li class="kosong">{e(t["amaran_kosong"])}</li>'
    out = out.replace('<ul id="senarai-amaran" class="senarai-amaran"></ul>', f'<ul id="senarai-amaran" class="senarai-amaran">{amaran}</ul>')
    if data.get("semakan_24j"):
        sb = t["semakan_baris"]
        for k, v in data["semakan_24j"].items():
            sb = sb.replace("{" + k + "}", str(v))
        out = out.replace('<p id="semakan-baris" class="ket"></p>', f'<p id="semakan-baris" class="ket">{e(sb)}</p>')
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
