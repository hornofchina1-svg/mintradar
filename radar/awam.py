"""Data AWAM untuk datt.my: apa yang radar nampak + keputusan kertas. TIADA wallet, tiada mint sebenar, tiada strategi
pemilihan/jual (enjin wang kekal peribadi — keputusan pemilik 29 Okt). Ditulis atomik ke awam/stats.json."""
import html
import json
import os
import re
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
    # Tumpuan (cadangan @orane di Boltbook): berapa peratus untung kertas 24 j datang dari 4 teratas
    positif = [x["pnl"][24][0] for x in siap24 if x["pnl"][24][0] > 0]
    jumlah_24 = sum(x["pnl"][24][0] for x in siap24)
    tumpuan = {"n_teratas": min(4, len(positif)), "untung_teratas_bnb": round(sum(positif[:4]), 6),
               "bersih_semua_bnb": round(jumlah_24, 6), "bil_kedudukan": len(siap24)}
    hari = con.execute("""SELECT COUNT(*), SUM(kelas='mint_percuma'), SUM(kelas='airdrop') FROM kontrak
                          WHERE diperiksa=1 AND ts_panas >= ?""", (sekarang - 86400,)).fetchone()
    amaran = []
    for a, label, temuan, nama in con.execute(
            """SELECT s.alamat, s.label, s.temuan, COALESCE(k.nama, s.nama_kontrak) FROM semakan s LEFT JOIN kontrak k ON k.alamat=s.alamat
               WHERE s.label='merah' AND s.temuan NOT LIKE '%TIDAK_DISAHKAN%' ORDER BY s.ts DESC LIMIT 8"""):
        amaran.append({"alamat": a, "nama": nama, "temuan": json.loads(temuan)})
    disemak = dict(con.execute("SELECT label, COUNT(*) FROM semakan WHERE ts >= ? GROUP BY label", (sekarang - 86400,)).fetchall())
    # Peta haba (D39): kontrak paling banyak dimint 60 min lepas × mint setiap minit — ladang ejen yang mint serentak kelihatan
    mula = sekarang // 60 * 60 - 3600
    peta = []
    for a, nama, jum in con.execute(
            """SELECT m.alamat, COALESCE(k.nama, k.simbol), SUM(m.mint) s FROM minit m JOIN kontrak k ON k.alamat=m.alamat
               WHERE m.minit_ts >= ? AND k.kelas IN ('mint_percuma','mint_berbayar') GROUP BY m.alamat ORDER BY s DESC LIMIT ?""",
            (mula, cfg.get("laman", {}).get("peta_baris", 8))):
        if a in abai.get("alamat", []):
            continue
        baris = [0] * 60
        for ts, m in con.execute("SELECT minit_ts, mint FROM minit WHERE alamat=? AND minit_ts >= ?", (a, mula)):
            i = (ts - mula) // 60
            if 0 <= i < 60:
                baris[i] += m
        sm = con.execute("SELECT label FROM semakan WHERE alamat=?", (a,)).fetchone()
        peta.append({"alamat": a, "nama": nama, "jumlah": jum, "minit": baris, "label": sm[0] if sm else None,
                     "jualan": con.execute("SELECT COUNT(*) FROM jualan WHERE alamat=? AND harga_bnb > 0", (a,)).fetchone()[0]})
    return {
        "dijana": sekarang,
        "semakan_24j": {"hijau": disemak.get("hijau", 0), "kuning": disemak.get("kuning", 0), "merah": disemak.get("merah", 0)},
        "amaran": amaran,
        "rantaian": "BNB Smart Chain",
        "blok": int(con.execute("SELECT nilai FROM keadaan WHERE kunci='blok'").fetchone()[0]),
        "hari": {"panas": hari[0] or 0, "percuma": hari[1] or 0, "airdrop": hari[2] or 0},
        "kertas": kertas,
        "teratas_24j": teratas,
        "tumpuan_24j": tumpuan,
        "terbaru": baru,
        "peta": {"mula": mula, "kontrak": peta},
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
    # D41: lejar perbelanjaan cukai = config `belanja` [{tarikh, perkara, bnb, tx}] — tambah satu baris setiap kali cukai dibelanja
    data["belanja"] = [x for x in cfg.get("belanja", []) if isinstance(x, dict) and not str(x.get("perkara", "")).startswith("_")]
    try:  # D41: rekod sebenar (bukan kertas), sebelum/selepas D30
        data["sebenar"] = laporan.sebenar(con, cfg)
    except Exception:  # noqa: BLE001
        data["sebenar"] = None
    if rpc is not None:  # D37: seksyen token $MRADAR (None = tersorok); D41: wallet ejen
        from . import token
        try:
            data["token"] = token.bina(rpc, cfg)
        except Exception:  # noqa: BLE001
            data["token"] = None
        data["dompet"] = token.dompet(rpc, cfg)
    from . import scouts  # D47: papan pendahulu Scouts (API EN untuk ejen + seksyen #scouts)
    sc = cfg.get("scouts") or {}
    data["scouts"] = dict(scouts.papan(con, sc.get("papan_had", 20)), daily_limit=sc.get("had_sehari"),
                           min_account_hours=sc.get("umur_akaun_jam_min"), paid_rewards=False, live=bool(sc.get("hidup")))
    sementara = folder / ".stats.json.tmp"
    sementara.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    os.replace(sementara, folder / "stats.json")  # nginx tidak pernah nampak fail separuh
    tulis_kontrak(con, folder / "kontrak", data["dijana"])
    render_laman(data, folder.parent / "laman")
    return data


# API datt.my dalam EN (ejen Boltbook); DB kekal BM
EN_RINGKAS = {"simbol": "symbol", "pemegang": "holders", "sumber_terbuka": "source_verified_bscscan", "cukai_beli": "buy_tax",
              "cukai_jual": "sell_tax", "likuiditi_usd": "liquidity_usd", "volume_24j_usd": "volume_24h_usd", "pencipta": "creator"}
EN_BUNDLE = {"dompet": "same_block_wallets", "blok_bundle": "same_block_blocks", "wallet_satu_blok_maks": "max_wallets_one_block",
             "pct_dibeli": "pct_supply_bought", "pembeli_awal": "early_buyers", "kaitan": "links", "terpaut": "linked_wallets",
             "baharu": "near_new_wallets", "disemak": "wallets_checked", "pct_masih": "pct_supply_still_held", "blok_cetakan": "launch_block"}


def tulis_kontrak(con, folder, sekarang):
    """Satu fail JSON setiap kontrak yang disemak (API baca-sahaja untuk ejen lain: datt.my/data/kontrak/<alamat>.json)
    + index.json. Teks temuan dalam EN (bahasa ejen di Boltbook); kod kekal untuk mesin."""
    folder.mkdir(parents=True, exist_ok=True)
    bahasa = json.loads((folder.parent.parent / "laman" / "bahasa.json").read_text()) if (folder.parent.parent / "laman" / "bahasa.json").exists() else {"en": {}}
    t = bahasa["en"]
    indeks = []
    for a, ts, label, temuan, admin, nama_k, nama in con.execute(
            """SELECT s.alamat, s.ts, s.label, s.temuan, s.admin, s.nama_kontrak, k.nama FROM semakan s
               LEFT JOIN kontrak k ON k.alamat=s.alamat"""):
        tm = json.loads(temuan)
        rekod = {
            "address": a, "chain": "bsc", "name": nama or nama_k, "label": label, "checked_at": ts,
            "findings": [{"code": x["kod"], "function": x["fungsi"],
                          "text": t.get("temuan_" + x["kod"], x["kod"]).replace("{fungsi}", (x["fungsi"] + "()") if x["fungsi"] else "")} for x in tm],
            "privileged_functions": json.loads(admin or "[]"),
            "source": f"https://sourcify.dev/server/v2/contract/56/{a}?fields=sources,abi",
            "note": "Automatic heuristic from verified source, not an audit. Red = unverified, upgradeable proxy, or a hard-coded address that can move funds.",
        }
        ps = con.execute("SELECT ts, label, temuan, ringkas, bundle FROM pasaran WHERE alamat=?", (a,)).fetchone()
        if ps:  # D34: semakan pasaran token BEP-20 (hanya bila pernah diminta melalui @sasaoff / radar.py semak)
            rk, bn = json.loads(ps[3]), json.loads(ps[4] or "null")
            rekod["name"] = rekod["name"] or rk.get("simbol")
            rekod["market"] = {
                "checked_at": ps[0], "label": ps[1], "summary": {EN_RINGKAS.get(k, k): v for k, v in rk.items()},
                "bundle": bn and {EN_BUNDLE.get(k, k): ({EN_BUNDLE.get(k2, k2): v2 for k2, v2 in v.items()} if isinstance(v, dict) else v)
                                  for k, v in bn.items()},
                "findings": [{"code": x["kod"], "value": x["nilai"], "text": t.get("pasaran_" + x["kod"], x["kod"]).replace("{nilai}", str(x["nilai"]))}
                             for x in json.loads(ps[2])],
                "note": "GoPlus token_security + DexScreener + on-chain early buyers. Heuristic, not an audit and not a buy signal.",
            }
            if rk.get("sumber_terbuka") and any(x["code"] == "TIDAK_DISAHKAN" for x in rekod["findings"]):
                # sama seperti balasan @sasaoff: disahkan BscScan ≠ tiada sumber (D31)
                label = "kuning"
                rekod["findings"] = [dict(x, code="SUMBER_BSCSCAN", text=t.get("temuan_SUMBER_BSCSCAN", x["text"]))
                                     if x["code"] == "TIDAK_DISAHKAN" else x for x in rekod["findings"]]
            rekod["label"] = max(label, ps[1], key=["hijau", "kuning", "merah"].index)
        sementara = folder / f".{a}.tmp"
        sementara.write_text(json.dumps(rekod, ensure_ascii=False, separators=(",", ":")))
        os.replace(sementara, folder / f"{a}.json")
        indeks.append({"address": a, "name": rekod["name"], "label": rekod["label"], "checked_at": ts})
    indeks.sort(key=lambda x: -x["checked_at"])
    sementara = folder / ".index.tmp"
    sementara.write_text(json.dumps({"generated_at": sekarang, "count": len(indeks), "contracts": indeks}, separators=(",", ":")))
    os.replace(sementara, folder / "index.json")


def _lalu(ts, sekarang):
    m = max(0, (sekarang - ts) // 60)
    return f"{m} min ago" if m < 90 else f"{round(m / 60)} h ago"


LAMAN_URL = {"en": "https://datt.my/", "ms": "https://datt.my/ms/"}
LOKAL = {"en": "en_GB", "ms": "ms_MY"}
DATA_T = re.compile(r'(<[a-z0-9]+\b[^>]*\bdata-t="([a-z0-9_]+)"[^>]*>)([^<]*)(<)')


def terjemah(out, t, lang):
    """D43: dwibahasa SEBENAR — setiap elemen data-t diisi di pelayan (Google mengindeks / dan /ms/ berasingan), serta lang,
    tajuk, meta, kanonik, og:* dan pautan tukar bahasa. Elemen data-t mesti mengandungi teks sahaja (tiada tag anak)."""
    e = html.escape
    out = DATA_T.sub(lambda m: m.group(1) + (e(t[m.group(2)]) if t.get(m.group(2)) else m.group(3)) + m.group(4), out)
    lain = "ms" if lang == "en" else "en"
    ganti = [
        ('<html lang="en">', f'<html lang="{lang}">'),
        ('<title>MintRadar</title>', f'<title>{e(t["tajuk_laman"])}</title>'),
        ('<link rel="canonical" href="https://datt.my/">', f'<link rel="canonical" href="{LAMAN_URL[lang]}">'),
        ('<meta property="og:url" content="https://datt.my/">', f'<meta property="og:url" content="{LAMAN_URL[lang]}">'),
        ('<meta property="og:locale" content="en_GB">', f'<meta property="og:locale" content="{LOKAL[lang]}">'),
        ('<meta property="og:locale:alternate" content="ms_MY">', f'<meta property="og:locale:alternate" content="{LOKAL[lain]}">'),
        ('id="tukar-bahasa" href="/ms/" hreflang="ms" lang="ms" data-pendek="BM"',
         f'id="tukar-bahasa" href="{"/ms/" if lang == "en" else "/"}" hreflang="{lain}" lang="{lain}" data-pendek="{lain.upper() if lain == "en" else "BM"}"'),
    ]
    for a, b in ganti:
        out = out.replace(a, b)
    out = re.sub(r'<meta name="description" content="[^"]*">', f'<meta name="description" content="{e(t["meta_desc"])}">', out)
    for k in ("og:title", "twitter:title"):
        out = re.sub(rf'<meta (property|name)="{k}" content="[^"]*">', lambda m: f'<meta {m.group(1)}="{k}" content="{e(t["og_tajuk"])}">', out)
    for k in ("og:description", "twitter:description"):
        out = re.sub(rf'<meta (property|name)="{k}" content="[^"]*">', lambda m: f'<meta {m.group(1)}="{k}" content="{e(t["meta_desc"])}">', out)
    return out


def render_html(data, templat, bahasa, lang="en"):
    """Isi jadual dalam HTML statik supaya pembaca tanpa JS (ejen yang curl laman) nampak data sebenar; apl.js
    menulis semula selepas dimuat. Diukur 29 Okt: pengulas Boltbook melaporkan 'tabel demo kosong'. D43: satu halaman setiap bahasa."""
    e = html.escape
    t = bahasa[lang]
    sekarang = data["dijana"]
    def teks_kod(kod):  # D48: teks temuan tanpa pemegang tempat (laporan Scouts menyimpan kod sahaja)
        teks = (t.get("temuan_" + kod) or t.get("pasaran_" + kod) or kod).replace("{fungsi}", t["scouts_fungsi"])
        return re.sub(r":?\s*\{nilai\}", "", teks).strip()

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
    tp = data.get("tumpuan_24j") or {}
    if tp.get("bil_kedudukan"):
        lain = tp["bersih_semua_bnb"] - tp["untung_teratas_bnb"]
        teks_tp = (t["tumpuan_baris"].replace("{n}", str(tp["n_teratas"])).replace("{teratas}", f"{tp['untung_teratas_bnb']:.4f}")
                   .replace("{semua}", f"{tp['bersih_semua_bnb']:.4f}").replace("{baki}", str(tp["bil_kedudukan"] - tp["n_teratas"]))
                   .replace("{lain}", ("+" if lain >= 0 else "\u2212") + f"{abs(lain):.4f}"))
        templat = templat.replace('<p id="tumpuan" class="ket"></p>', f'<p id="tumpuan" class="ket">{e(teks_tp)}</p>')
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
    sc = data.get("scouts")
    if sc:
        out = out.replace('<p id="scouts-ket" class="ket"></p>',
                          f'<p id="scouts-ket" class="ket">{e(t["scouts_ket"].replace("{had}", str(sc["daily_limit"])))}</p>')
        papan = "".join(
            f'<li><span class="nama-koleksi">{e(x["agent"])}</span><span class="bersih positif">{e(t["scouts_mata"].replace("{n}", str(x["points"])))}</span>'
            f'<span class="butir">{e(t["scouts_butir"].replace("{disahkan}", str(x["confirmed"])).replace("{laporan}", str(x["reports"])))}</span></li>'
            for x in sc["leaderboard"]) or f'<li class="kosong">{e(t["scouts_kosong"])}</li>'
        out = out.replace('<ol id="senarai-scouts" class="pemenang"></ol>', f'<ol id="senarai-scouts" class="pemenang">{papan}</ol>')
        out = out.replace('<p id="scouts-aturan" class="ket"></p>',
                          f'<p id="scouts-aturan" class="ket">{e(t["scouts_aturan"].replace("{jam}", str(sc.get("min_account_hours"))))}</p>')
        terkini = "".join(
            f'<li><span>{e(x["agent"])} \u00b7 {e(teks_kod(x["code"]))} \u00b7 +{x["points"]}</span>'
            f'<a class="alamat" href="/data/kontrak/{e(x["contract"])}.json">{e(x["contract"][:6])}\u2026{e(x["contract"][-4:])}</a></li>'
            for x in sc["recent"]) or f'<li class="kosong">{e(t["scouts_terkini_kosong"])}</li>'
        out = out.replace('<ul id="scouts-terkini" class="belanja"></ul>', f'<ul id="scouts-terkini" class="belanja">{terkini}</ul>')
        out = out.replace('<p id="scouts-baris" class="ket"></p>', f'<p id="scouts-baris" class="ket">{e(t["scouts_baris"].replace("{laporan}", str(sc["reports"])).replace("{disahkan}", str(sc["confirmed"])))}</p>')
    kaki = t["kaki_dijana"].replace("{masa}", masa).replace("{blok}", f"{data['blok']:,}")
    out = out.replace('<p id="kaki-data" aria-live="polite"></p>', f'<p id="kaki-data" aria-live="polite">{e(kaki)}</p>')
    return terjemah(out, t, lang)


def render_laman(data, folder_laman):
    """hidup/laman/index.html (EN) + hidup/laman/ms/index.html (BM) dijana semula daripada index.templat.html (salinan asal
    yang deploy.sh simpan). D43: dwibahasa sebenar, satu URL setiap bahasa."""
    folder_laman = Path(folder_laman)
    templat = folder_laman / "index.templat.html"
    if not templat.exists():
        return False
    bahasa = json.loads((folder_laman / "bahasa.json").read_text())
    for lang, sasaran in (("en", folder_laman / "index.html"), ("ms", folder_laman / "ms" / "index.html")):
        sasaran.parent.mkdir(exist_ok=True)
        sementara = sasaran.parent / ".index.html.tmp"
        sementara.write_text(render_html(data, templat.read_text(), bahasa, lang))
        os.replace(sementara, sasaran)
    return True
