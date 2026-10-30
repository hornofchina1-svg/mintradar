"""Semakan PASARAN token BEP-20 (Scouts 1c, D31): honeypot, cukai, kuasa pemilik, pemegang teratas, pencipta, volume tak wajar,
likuiditi. Pelengkap radar/semak.py (yang membaca KOD); di sini data pasaran GoPlus token_security + DexScreener. Ambang dari
config `pasaran` (senarai semak "degen" — pemegang > 3.8 %, volume bot), kod temuan sahaja; teks dalam laman/bahasa.json
(`pasaran_<KOD>`). Heuristik, bukan audit dan bukan nasihat beli."""
import json
import urllib.request

KOSONG = {"0x0000000000000000000000000000000000000000", "0x000000000000000000000000000000000000dead"}
MAKLUMAT = {"TIADA_PASANGAN", "BUNDLE_KELUAR", "BUNDLE_TIADA_PAUT"}  # fakta, tidak menaikkan label
MERAH = {"HONEYPOT", "TIDAK_BOLEH_BELI", "PEMILIK_TERSEMBUNYI", "AMBIL_BALIK", "UBAH_BAKI", "PENCIPTA_HONEYPOT", "CUKAI_MERAH"}


def _get(url, timeout=20):
    q = urllib.request.Request(url, headers={"User-Agent": "mintradar/0.1"})
    with urllib.request.urlopen(q, timeout=timeout) as r:
        return json.load(r)


def ambil(alamat):
    """(goplus, dex) — None bila sumber gagal. GoPlus tanpa token_symbol = bukan token BEP-20."""
    try:
        gp = (_get(f"https://api.gopluslabs.io/api/v1/token_security/56?contract_addresses={alamat}").get("result") or {})
        gp = next(iter(gp.values()), None)
    except (OSError, ValueError):
        gp = None
    try:
        ps = [p for p in _get(f"https://api.dexscreener.com/latest/dex/tokens/{alamat}").get("pairs") or [] if p.get("chainId") == "bsc"]
        dex = max(ps, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0) if ps else None
    except (OSError, ValueError):
        dex = None
    return gp, dex


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def nilai(gp, dex, cfg, alamat="", bun=None):
    """Tulen (tiada rangkaian): {'label', 'temuan': [{'kod', 'nilai'}], 'ringkas': {...}} atau None bila bukan token."""
    if not gp or not gp.get("token_symbol"):
        return None
    t = []

    def tanda(kod, v=None):
        t.append({"kod": kod, "nilai": v})

    satu = lambda k: str(gp.get(k)) == "1"  # noqa: E731
    if satu("is_honeypot"):
        tanda("HONEYPOT")
    if satu("cannot_buy"):
        tanda("TIDAK_BOLEH_BELI")
    if satu("honeypot_with_same_creator"):
        tanda("PENCIPTA_HONEYPOT")
    if satu("hidden_owner"):
        tanda("PEMILIK_TERSEMBUNYI")
    if satu("can_take_back_ownership"):
        tanda("AMBIL_BALIK")
    if satu("owner_change_balance"):
        tanda("UBAH_BAKI")
    cukai = max(_f(gp.get("buy_tax")) or 0, _f(gp.get("sell_tax")) or 0)
    if cukai >= cfg["cukai_merah"]:
        tanda("CUKAI_MERAH", f"{cukai * 100:g}%")
    elif cukai >= cfg["cukai_kuning"]:
        tanda("CUKAI_KUNING", f"{cukai * 100:g}%")
    if satu("slippage_modifiable") or satu("personal_slippage_modifiable"):
        tanda("CUKAI_BOLEH_UBAH")
    pemilik_aktif = (gp.get("owner_address") or "").lower() not in KOSONG | {""}
    if satu("is_mintable") and pemilik_aktif:
        tanda("BOLEH_CETAK")
    if satu("transfer_pausable"):
        tanda("BOLEH_JEDA")
    if satu("is_blacklisted"):
        tanda("SENARAI_HITAM")

    pasangan = (dex or {}).get("pairAddress", "").lower()
    biasa = [h for h in gp.get("holders") or []
             if (h.get("address") or "").lower() not in KOSONG | {pasangan, alamat.lower()}
             and str(h.get("is_locked")) != "1" and not h.get("tag")]
    pct = [(_f(h.get("percent")) or 0) * 100 for h in biasa]
    besar = [p for p in pct if p > cfg["pemegang_maks_pct"]]
    if besar:
        tanda("PEMEGANG_BESAR", f"{len(besar)} > {cfg['pemegang_maks_pct']:g}% (max {max(besar):.1f}%)")
    if sum(pct[:10]) > cfg["top10_maks_pct"]:
        tanda("TUMPU_TOP10", f"{sum(pct[:10]):.0f}%")
    pencipta = (_f(gp.get("creator_percent")) or 0) * 100
    if pencipta > cfg["pencipta_maks_pct"]:
        tanda("PENCIPTA_BESAR", f"{pencipta:.1f}%")

    liq = ((dex or {}).get("liquidity") or {}).get("usd")
    vol = ((dex or {}).get("volume") or {}).get("h24")
    mcap = (dex or {}).get("marketCap") or (dex or {}).get("fdv")
    if not dex:
        tanda("TIADA_PASANGAN")
    else:
        if liq is not None and liq < cfg["likuiditi_min_usd"]:
            tanda("LIKUIDITI_RENDAH", f"${liq:,.0f}")
        if vol and mcap and vol / mcap > cfg["volume_mcap_maks"]:
            tanda("VOLUME_BOT", f"{vol / mcap:.0f}x")

    merah_bundle = False
    if bun and bun["dompet"]:  # D32: tahap ikut % yang MASIH dipegang (risiko lambakan), bukan tuduhan seorang pelancar
        fakta = f"{bun['dompet']} wallets, {bun['pct_dibeli']:.0f}%, {bun['pct_masih']:.1f}%"
        b = cfg["bundle"]
        k = bun.get("kaitan") or {}
        if bun["pct_masih"] >= b["kuning_pct"]:
            tanda("BUNDLE_MASIH", fakta)
            merah_bundle = bun["pct_masih"] >= b["merah_pct"]
        elif bun["pct_dibeli"] >= b["kuning_pct"]:
            tanda("BUNDLE_KELUAR", fakta)
        if k.get("terpaut", 0) >= 2:  # bukti rantaian: satu tx / satu penghantar untuk beberapa wallet
            tanda("BUNDLE_TERPAUT", f"{k['terpaut']}/{bun['dompet']}")
            merah_bundle = merah_bundle or bun["pct_masih"] >= b["kuning_pct"]
        elif k.get("disemak") and bun["pct_dibeli"] >= b["kuning_pct"]:
            tanda("BUNDLE_TIADA_PAUT", f"{k['baharu']}/{k['disemak']}")

    kod = {x["kod"] for x in t}
    label = "merah" if kod & MERAH or merah_bundle else "kuning" if kod - {"TIADA_PASANGAN", "BUNDLE_KELUAR", "BUNDLE_TIADA_PAUT"} else "hijau"
    return {"label": label, "temuan": t, "ringkas": {
        "simbol": gp.get("token_symbol"), "pemegang": int(_f(gp.get("holder_count")) or 0) or None,
        "sumber_terbuka": satu("is_open_source"), "cukai_beli": gp.get("buy_tax"),
        "cukai_jual": gp.get("sell_tax"), "dex": (dex or {}).get("dexId"), "likuiditi_usd": liq, "volume_24j_usd": vol,
        "mcap_usd": mcap, "pencipta": (gp.get("creator_address") or "").lower() or None}}


def semak_token(alamat, cfg, rpc=None):
    gp, dex = ambil(alamat)
    bun = None
    if rpc is not None and gp and gp.get("token_symbol") and dex:
        from . import bundle
        try:
            bun = bundle.semak_bundle(rpc, alamat, dex, cfg["bundle"])
        except Exception:  # noqa: BLE001 — RPC gagal = semakan lain tetap dijawab
            bun = None
    h = nilai(gp, dex, cfg, alamat, bun)
    if h:
        h["bundle"] = bun
    return h
