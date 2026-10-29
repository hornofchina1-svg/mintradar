"""Fungsi tulen (tiada rangkaian, tiada DB): kelaskan kontrak dan kira untung/rugi kertas. Diuji dalam tests/."""
from statistics import median

TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

KELAS_PERCUMA = "mint_percuma"
KELAS_BERBAYAR = "mint_berbayar"
KELAS_MAHAL = "mint_mahal"
KELAS_AIRDROP = "airdrop"


def kelaskan(sampel, cfg_kelas):
    """sampel = [{"dari": alamat penghantar tx, "penerima": alamat yang menerima NFT, "nilai_wei": int, "bil": NFT dalam tx}].

    Mint sebenar = orang menghantar tx sendiri dan NFT jatuh ke wallet mereka. Airdrop/spam = satu penghantar,
    NFT jatuh ke orang lain. Harga = nilai tx ÷ bilangan NFT dalam tx itu (median).
    """
    if not sampel:
        return None, None
    sendiri = sum(1 for s in sampel if s["dari"].lower() == s["penerima"].lower()) / len(sampel)
    if sendiri < cfg_kelas["nisbah_mint_sendiri_min"]:
        return KELAS_AIRDROP, None
    harga = median((s["nilai_wei"] / 1e18 + s.get("token_bnb", 0.0)) / max(1, s["bil"]) for s in sampel)
    if harga == 0:
        return KELAS_PERCUMA, 0.0
    if harga <= cfg_kelas["harga_mint_maks_bnb"]:
        return KELAS_BERBAYAR, harga
    return KELAS_MAHAL, harga


def bayaran_token_bnb(pemint, resit, token_bayaran, bnb_usd):
    """Jumlah USDT/USDC/WBNB yang KELUAR dari pemint dalam resit mint, dalam BNB. 0 = tiada bayaran token."""
    pemint = pemint.lower()
    jumlah = 0.0
    for l in (resit or {}).get("logs", []):
        t = token_bayaran.get(l["address"].lower())
        if t and len(l["topics"]) == 3 and l["topics"][0] == TRANSFER and "0x" + l["topics"][1][-40:] == pemint:
            amaun = int(l["data"], 16) / 1e18
            jumlah += amaun / bnb_usd if t.get("usd") else amaun
    return jumlah


def kos_masuk(harga_bnb, harga_gas_wei, cfg_kertas):
    return (harga_bnb or 0.0) + harga_gas_wei * cfg_kertas["gas_mint"] / 1e18


def pnl_tetingkap(masuk_ts, kos_bnb, jualan, jam, yuran):
    """jualan = [(ts, harga_bnb)]. Pulangkan (pnl_bnb, median_harga, bil_jualan) untuk jualan dalam (masuk, masuk+jam].

    Tiada jualan dalam tetingkap = NFT tidak boleh dijual = rugi kos penuh (andaian konservatif, bukan 0).
    """
    hujung = masuk_ts + jam * 3600
    harga = [h for ts, h in jualan if masuk_ts < ts <= hujung and h > 0]
    if not harga:
        return -kos_bnb, None, 0
    m = median(harga)
    return m * (1 - yuran) - kos_bnb, m, len(harga)


def ringkas_pnl(kedudukan, jam):
    """kedudukan = [{"pnl": {jam: (pnl, median, bil)}}] → (jumlah, menang, kalah, ada_jualan)."""
    jumlah = menang = kalah = ada = 0
    for k in kedudukan:
        p, m, bil = k["pnl"][jam]
        jumlah += p
        if bil:
            ada += 1
        if p > 0:
            menang += 1
        else:
            kalah += 1
    return jumlah, menang, kalah, ada


def harga_jualan_bnb(tx, resit, bil_nft, token_bayaran, bnb_usd, penjual=None, pembeli=None):
    """Harga SATU NFT dalam BNB untuk satu tx jualan. 0 = bukan jualan (pindah biasa / ke escrow / wash).

    Dua bentuk jualan (laporan penyelidikan 29 Okt membetulkan D8):
    - pembeli beli listing: tx.from = pembeli → BNB asli (tx.value) + ERC-20 bayaran yang KELUAR dari pembeli;
    - penjual terima tawaran: tx.from = penjual, tx.value = 0 → ERC-20 bayaran yang MASUK ke penjual (bersih yuran).
    penjual/pembeli = from/to log Transfer NFT; tiada = andaian lama (tx.from = pembeli).
    """
    if not tx:
        return 0.0
    pembeli = (pembeli or tx["from"]).lower()
    penjual = (penjual or "").lower()
    if penjual and penjual == pembeli:
        return 0.0  # pindah ke diri sendiri
    usd = lambda t, amaun: amaun / bnb_usd if t.get("usd") else amaun
    keluar_pembeli = masuk_penjual = 0.0
    for l in (resit or {}).get("logs", []):
        t = token_bayaran.get(l["address"].lower())
        if not t or len(l["topics"]) != 3 or l["topics"][0] != TRANSFER:
            continue
        dari, ke = "0x" + l["topics"][1][-40:], "0x" + l["topics"][2][-40:]
        amaun = usd(t, int(l["data"], 16) / 1e18)
        if dari == pembeli:
            keluar_pembeli += amaun
        if penjual and ke == penjual:
            masuk_penjual += amaun
    asli = int(tx["value"], 16) / 1e18 if tx["from"].lower() == pembeli else 0.0
    jumlah = asli + keluar_pembeli or masuk_penjual
    return jumlah / max(1, bil_nft)
