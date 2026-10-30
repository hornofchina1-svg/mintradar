"""Token $MRADAR untuk laman datt.my (D37): status pelancaran Boltbook (state/boltbook/lancar.json, ditulis cron MINTRADAR-LANCAR),
harga/mcap/likuiditi DexScreener, pemegang GoPlus, dan cukai yang sudah sampai ke wallet ejen (Split Vault flap, D35). Simbol dari
config `token.simbol`. Sumber luar gagal = medan itu None; laman tetap memapar yang ada."""
import json

from . import db, pasaran
from .semak import keccak256


def sel(s):
    return "0x" + keccak256(s.encode())[:8]


def wallet(cfg):
    """Wallet ejen: config `token.wallet` (repo awam tiada bahagian `mint`), sandaran `mint.wallet`."""
    return (cfg.get("token") or {}).get("wallet") or (cfg.get("mint") or {}).get("wallet")


def cukai(rpc, token, wallet):
    """(vault, terkumpul BNB, dihantar BNB): token → taxProcessor() → marketAddress() = Split Vault → userBalances(wallet)."""
    tp = "0x" + rpc.call(token, sel("taxProcessor()"))[-40:]
    vault = "0x" + rpc.call(tp, sel("marketAddress()"))[-40:]
    v = rpc.call(vault, sel("userBalances(address)") + "0" * 24 + wallet[2:].lower())
    return vault, int(v[2:66], 16) / 1e18, int(v[66:130], 16) / 1e18


def bina(rpc, cfg):
    simbol = cfg.get("token", {}).get("simbol")
    f = db.folder_state() / "boltbook" / "lancar.json"
    if not simbol or not f.exists():
        return None
    k = json.loads(f.read_text()).get(simbol)
    if not k:
        return None
    hasil = {"simbol": simbol, "status": k.get("status"), "alamat": k.get("token"), "flap_url": k.get("flap_url"),
             "lancar_pada": k.get("launches_at"), "harga_usd": None, "mcap_usd": None, "likuiditi_usd": None,
             "volume_24j_usd": None, "pemegang": None, "cukai_bnb": None}
    if not hasil["alamat"]:
        return hasil
    gp, dex = pasaran.ambil(hasil["alamat"])
    if dex:
        hasil.update({"harga_usd": _f(dex.get("priceUsd")), "mcap_usd": dex.get("marketCap") or dex.get("fdv"),
                      "likuiditi_usd": (dex.get("liquidity") or {}).get("usd"), "volume_24j_usd": (dex.get("volume") or {}).get("h24")})
    if gp and gp.get("holder_count"):
        hasil["pemegang"] = int(_f(gp["holder_count"]) or 0) or None
    try:
        hasil["cukai_bnb"] = round(cukai(rpc, hasil["alamat"], wallet(cfg))[1], 6)
    except Exception:  # noqa: BLE001 — RPC gagal = kosong, bukan 0
        pass
    return hasil


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


USDT = "0x55d398326f99059fF775485246999027B3197955"


def dompet(rpc, cfg):
    """Wallet ejen untuk seksyen "ke mana cukai pergi" (D41): baki BNB + USDT, nonce (bilangan tx), terus dari rantaian."""
    w = wallet(cfg)
    if not w:
        return None
    h = {"alamat": w, "bnb": None, "usdt": None, "nonce": None}
    try:
        h["bnb"] = round(int(rpc.panggil("eth_getBalance", [w, "latest"]), 16) / 1e18, 6)
        h["nonce"] = int(rpc.panggil("eth_getTransactionCount", [w, "latest"]), 16)
        h["usdt"] = round(int(rpc.call(USDT, sel("balanceOf(address)") + "0" * 24 + w[2:].lower()), 16) / 1e18, 4)
    except Exception:  # noqa: BLE001
        pass
    return h
