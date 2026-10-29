"""Semakan keselamatan automatik setiap kontrak yang radar kesan (Scouts Fasa 0, D24). Sumber DISAHKAN Sourcify → senarai fungsi
tulis bukan-standard, siapa boleh memanggilnya, dan sama ada kuasa itu KEKAL walaupun owner dilepaskan (alamat constant/
immutable/literal — corak pintu belakang BJAGENT `usdtKeeper`, D23). Heuristik: ia menunjuk tempat untuk dibaca manusia,
bukan audit. Kod temuan sahaja di sini; teks BM/EN dalam laman/bahasa.json (`temuan_<KOD>`)."""
import json
import re
import urllib.error
import urllib.request

STANDARD = {"approve", "transfer", "transferFrom", "safeTransferFrom", "setApprovalForAll", "permit", "increaseAllowance",
            "decreaseAllowance", "renounceOwnership", "transferOwnership", "acceptOwnership", "mint", "multicall",
            "rawFulfillRandomWords"}
PUSTAKA = ("@openzeppelin", "node_modules", "/lib/", "lib/forge-std", "@chainlink", "solady", "erc721a/")
IMPL_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"  # EIP-1967

GERAK_DANA = re.compile(r"\.(transfer|send)\s*\(|\.call\s*\{\s*value|safeTransfer(From)?\s*\(|_\w*[Tt]ransfer\w*\s*\(|\bpayable\s*\(")
UBAH_PERATURAN = re.compile(r"^(set|update|change|toggle|pause|unpause|enable|disable|blacklist|whitelist|add|remove)", re.I)
MODIFIER_KUASA = re.compile(r"\b(only\w+|auth|requiresAuth|whenNotPaused)\b")
PENGIRIM = re.compile(r"msg\.sender\s*(?:==|!=)\s*([A-Za-z_]\w*(?:\(\))?|0x[0-9a-fA-F]{40})|([A-Za-z_]\w*(?:\(\))?)\s*(?:==|!=)\s*msg\.sender")
KEKAL_DEKLARASI = re.compile(r"address\s+(?:payable\s+)?(?:(?:public|private|internal)\s+)*(?:constant|immutable)\s+(?:(?:public|private|internal)\s+)*(\w+)")


def _badan(sumber, mula):
    """Teks dari `{` pertama selepas `mula` hingga `}` sepadan."""
    i = sumber.find("{", mula)
    if i < 0:
        return ""
    d = 0
    for j in range(i, len(sumber)):
        if sumber[j] == "{":
            d += 1
        elif sumber[j] == "}":
            d -= 1
            if d == 0:
                return sumber[i:j + 1]
    return sumber[i:]


def analisis(sumber_fail, abi, owner=None, impl=None):
    """sumber_fail = {laluan: teks}. Pulangkan {"label": merah|kuning|hijau, "temuan": [{"kod", "fungsi"}], "admin": [nama]}."""
    projek = {p: t for p, t in sumber_fail.items() if not any(x in p.lower() for x in PUSTAKA)} or sumber_fail
    semua = "\n".join(projek.values())
    kekal = set(KEKAL_DEKLARASI.findall(semua))
    owner_hidup = owner is not None and int(owner, 16) != 0
    tulis = sorted({f["name"] for f in abi if f.get("type") == "function"
                    and f.get("stateMutability") in ("nonpayable", "payable") and f["name"] not in STANDARD})
    # Fungsi PENGAWAL dalaman (cth `_onlyTreasury()` dalam VeltrionMint) — fungsi tulis yang memanggilnya mewarisi siapa
    # boleh memanggil. Tanpa ini, kawalan tidak langsung terlepas dan kontrak berkuasa dilabel hijau (diukur 29 Okt, $VARC).
    pengawal = {}
    for m in re.finditer(r"function\s+(_\w+)\s*\([^)]*\)[^{;]*\{", semua):
        p = [a or b for a, b in PENGIRIM.findall(_badan(semua, m.start()))]
        if p:
            pengawal[m.group(1)] = p
    temuan, admin = [], []
    if impl and int(impl, 16) != 0:
        temuan.append({"kod": "PROKSI", "fungsi": None})
    for nama in tulis:
        m = re.search(r"function\s+" + re.escape(nama) + r"\s*\(([^)]*)\)([^{;]*)\{", semua)
        if not m:
            continue
        kepala, badan = m.group(2), _badan(semua, m.start())
        pengirim = [a or b for a, b in PENGIRIM.findall(badan)]
        for g in re.findall(r"\b(_\w+)\s*\(", badan + kepala):
            pengirim += pengawal.get(g, [])
        berkuasa = bool(MODIFIER_KUASA.search(kepala)) or bool(pengirim) or "_checkOwner" in badan
        if not berkuasa:
            continue
        admin.append(nama)
        tetap = [p for p in pengirim if p in kekal or p.startswith("0x")]
        dana = bool(GERAK_DANA.search(badan))
        if tetap and dana:
            temuan.append({"kod": "KEKAL_DANA", "fungsi": nama})
        elif tetap:
            temuan.append({"kod": "KEKAL_KUASA", "fungsi": nama})
        elif dana and owner_hidup:
            temuan.append({"kod": "OWNER_DANA", "fungsi": nama})
        elif UBAH_PERATURAN.match(nama) and owner_hidup:
            temuan.append({"kod": "OWNER_UBAH", "fungsi": nama})
    if owner is not None and not owner_hidup:
        temuan.append({"kod": "DILEPASKAN", "fungsi": None})
    merah = {"PROKSI", "KEKAL_DANA", "TIDAK_DISAHKAN"}
    kuning = {"KEKAL_KUASA", "OWNER_DANA", "OWNER_UBAH"}
    kod = {t["kod"] for t in temuan}
    label = "merah" if kod & merah else "kuning" if kod & kuning else "hijau"
    return {"label": label, "temuan": temuan, "admin": admin}


def ambil_sourcify(alamat, timeout=30):
    url = f"https://sourcify.dev/server/v2/contract/56/{alamat}?fields=sources,abi,compilation"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "mintradar/0.1"}), timeout=timeout) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # tidak disahkan di Sourcify
        raise
    if not (d.get("match") or d.get("runtimeMatch") or d.get("creationMatch")):
        return None
    return {"sumber": {p: v.get("content", "") for p, v in (d.get("sources") or {}).items()}, "abi": d.get("abi") or [],
            "nama": (d.get("compilation") or {}).get("name"), "padanan": d.get("match") or d.get("runtimeMatch")}


def semak(rpc, alamat):
    """Rangkaian: Sourcify + owner() + slot impl EIP-1967. Tiada sumber = merah TIDAK_DISAHKAN (peraturan D23)."""
    try:
        impl = rpc.panggil("eth_getStorageAt", [alamat, IMPL_SLOT, "latest"])
    except Exception:  # noqa: BLE001
        impl = None
    s = ambil_sourcify(alamat)
    if not s:
        t = [{"kod": "TIDAK_DISAHKAN", "fungsi": None}]
        if impl and int(impl, 16):
            t.append({"kod": "PROKSI", "fungsi": None})
        return {"label": "merah", "temuan": t, "admin": [], "nama_kontrak": None, "padanan": None}
    try:
        r = rpc.call(alamat, "0x8da5cb5b")  # owner()
        owner = "0x" + r[-40:] if r and len(r) >= 42 else None
    except Exception:  # noqa: BLE001 — tiada owner() = bukan Ownable
        owner = None
    hasil = analisis(s["sumber"], s["abi"], owner, impl)
    hasil.update({"nama_kontrak": s["nama"], "padanan": s["padanan"]})
    return hasil
