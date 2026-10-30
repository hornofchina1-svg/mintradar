"""Pengesan BUNDLE token BEP-20 (Scouts 1d, D32): beberapa wallet berbeza membeli dalam BLOK YANG SAMA sejurus selepas token
dicetak = kemungkinan seorang pelancar memegang banyak wallet (isyarat "bundle" senarai semak degen; GoPlus tidak memberinya).
Yang penting kepada pembeli: berapa % bekalan wallet itu MASIH pegang (risiko lambakan). Aliran: blok cetakan (Transfer dari 0x0)
→ pindahan dalam `tetingkap_blok` pertama → bersih setiap tx (router dibuang) → pembeli = baki bersih > 0 dalam tx yang sumber
(penerima cetakan / pasangan DEX) kehilangan token. Heuristik: blok yang sama juga boleh = pemburu awal yang tidak berkaitan."""
from collections import defaultdict

TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
SIFAR = "0x" + "0" * 64
POTONG = 40000  # eth_getLogs berpenapis alamat: had 50 000 blok (publicnode, diukur 30 Okt)


def _alamat(topik):
    return "0x" + topik[-40:].lower()


def blok_pada_masa(rpc, ts):
    """Blok pertama dengan timestamp >= ts (carian binari, ~18 panggilan)."""
    hi = rpc.blok_terkini()
    lo = max(1, hi - 2_000_000)
    while hi - lo > 1:
        m = (lo + hi) // 2
        if rpc.masa_blok(m) < ts:
            lo = m
        else:
            hi = m
    return hi


def cari_cetakan(rpc, token, sekitar, potongan=6):
    """(blok, penerima) Transfer pertama dari 0x0, mencari ke belakang dari `sekitar`. None bila tiada dalam julat."""
    hingga = sekitar + 200
    for _ in range(potongan):
        dari = max(1, hingga - POTONG + 1)
        ls = rpc.log(dari, hingga, [TRANSFER, SIFAR], token, peranan="log_alamat")
        if ls:
            l = min(ls, key=lambda x: (int(x["blockNumber"], 16), int(x["logIndex"], 16)))
            return int(l["blockNumber"], 16), _alamat(l["topics"][2])
        hingga = dari - 1
    return None


def pembeli(log_pindahan, sumber):
    """Tulen: [(blok, wallet, jumlah, tx)] — baki bersih positif setiap tx di mana sumber kehilangan token (router bersih 0)."""
    tx = defaultdict(lambda: defaultdict(int))
    blok = {}
    for l in log_pindahan:
        if len(l["topics"]) < 3:
            continue
        h = l["transactionHash"]
        n = int(l["data"], 16) if l["data"] not in ("0x", "") else 0
        tx[h][_alamat(l["topics"][1])] -= n
        tx[h][_alamat(l["topics"][2])] += n
        blok[h] = int(l["blockNumber"], 16)
    hasil = []
    for h, baki in tx.items():
        if not any(baki.get(s, 0) < 0 for s in sumber):
            continue
        for a, v in baki.items():
            if v > 0 and a not in sumber and a != "0x" + "0" * 40:
                hasil.append((blok[h], a, v, h))
    return sorted(hasil)


def analisis(beli, bekalan, cfg):
    """Tulen: blok dengan >= `pembeli_sama_blok` wallet berbeza = blok bundle."""
    per_blok = defaultdict(dict)
    for b, a, v, *_ in beli:
        per_blok[b][a] = per_blok[b].get(a, 0) + v
    blok_bundle = {b: w for b, w in per_blok.items() if len(w) >= cfg["pembeli_sama_blok"]}
    dompet = {}
    for w in blok_bundle.values():
        for a, v in w.items():
            dompet[a] = dompet.get(a, 0) + v
    terbesar = max(blok_bundle.items(), key=lambda kv: len(kv[1]), default=(None, {}))
    return {"dompet": dompet, "blok_bundle": len(blok_bundle), "wallet_satu_blok_maks": len(terbesar[1]),
            "pct_dibeli": 100 * sum(dompet.values()) / bekalan if bekalan else 0, "pembeli_awal": len({x[1] for x in beli})}


def kaitan(beli_bundle, penghantar, nonce, cfg):
    """Tulen. beli_bundle [(blok, wallet, jumlah, tx)]; penghantar {tx: from}; nonce {wallet: kiraan tx}. Bukti rantaian sahaja:
    satu tx mengisi >= 2 wallet, atau satu penghantar (bukan wallet itu sendiri) membeli untuk >= 2 wallet; + wallet hampir baharu."""
    per_tx, per_penghantar = defaultdict(set), defaultdict(set)
    for _, w, _, h in beli_bundle:
        per_tx[h].add(w)
        dari = (penghantar.get(h) or "").lower()
        if dari and dari != w:
            per_penghantar[dari].add(w)
    terpaut = set()
    for ws in list(per_tx.values()) + list(per_penghantar.values()):
        if len(ws) >= 2:
            terpaut |= ws
    baharu = sum(1 for v in nonce.values() if v is not None and v <= cfg["nonce_baharu"])
    return {"terpaut": len(terpaut), "baharu": baharu, "disemak": len(nonce)}


def semak_bundle(rpc, token, dex, cfg):
    """Rangkaian. None bila tiada data (tiada pasangan DEX / cetakan tidak dijumpai)."""
    token = token.lower()
    if not dex or not dex.get("pairCreatedAt"):
        return None
    sekitar = blok_pada_masa(rpc, int(dex["pairCreatedAt"]) // 1000)
    c = cari_cetakan(rpc, token, sekitar)
    if not c:
        return None
    b0, penerima = c
    sumber = {penerima, (dex.get("pairAddress") or "").lower(), "0x" + "0" * 40} - {""}  # 0x0: beli pencipta dalam tx cetakan
    ls = rpc.log(b0, b0 + cfg["tetingkap_blok"], [TRANSFER], token, peranan="log_alamat")
    bekalan = int(rpc.call(token, "0x18160ddd"), 16)
    beli = pembeli(ls, sumber)
    a = analisis(beli, bekalan, cfg)
    bb = [x for x in beli if x[1] in a["dompet"]]
    penghantar = {}
    for h in list({x[3] for x in bb})[: cfg["semak_tx_maks"]]:
        penghantar[h] = (rpc.tx(h) or {}).get("from")
    nonce = {}
    for w in list(a["dompet"])[: cfg["semak_baki_maks"]]:
        try:
            nonce[w] = int(rpc.panggil("eth_getTransactionCount", [w, "latest"]), 16)
        except Exception:  # noqa: BLE001
            nonce[w] = None
    a["kaitan"] = kaitan(bb, penghantar, nonce, cfg)
    masih = 0
    for w in list(a["dompet"])[: cfg["semak_baki_maks"]]:
        masih += int(rpc.call(token, "0x70a08231" + "0" * 24 + w[2:]), 16)
    a["pct_masih"] = 100 * masih / bekalan if bekalan else 0
    a["blok_cetakan"] = b0
    a["dompet"] = len(a["dompet"])
    return a
