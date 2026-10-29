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


def _nyahkod(jenis, hex_):
    b = bytes.fromhex(hex_[2:]) if hex_ and len(hex_) > 2 else b""
    if not b:
        return None
    if jenis.startswith("uint") or jenis.startswith("int"):
        return str(int.from_bytes(b[:32], "big"))
    if jenis == "bool":
        return bool(int.from_bytes(b[:32], "big"))
    if jenis == "address":
        return "0x" + b[12:32].hex()
    if jenis == "bytes32":
        return "0x" + b[:32].hex()
    if jenis == "string" and len(b) >= 64:
        n = int.from_bytes(b[32:64], "big")
        return b[64:64 + n].decode("utf-8", "replace")[:80]
    return None


def gambaran(rpc, alamat, abi, had=80):
    """Semakan MENDALAM: panggil setiap fungsi view/pure TANPA input dengan satu output ringkas (harga, had, suis, treasury,
    keeper…) dan pulangkan nilainya. Pemilih fungsi dikira dengan `keccak256` tulen di bawah (tiada pustaka)."""
    hasil = {}
    # nama berkaitan kuasa/dana dahulu: tanpa susunan ini `usdtKeeper` BJAGENT terkeluar dari had (diukur 29 Okt)
    utama = re.compile(r"owner|admin|keeper|treasury|signer|guardian|importer|minter|withdraw|fee|price|cost", re.I)
    abi = sorted(abi, key=lambda f: 0 if utama.search(f.get("name", "")) else 1)
    for f in abi:
        if len(hasil) >= had:
            break
        if (f.get("type") != "function" or f.get("inputs") or f.get("stateMutability") not in ("view", "pure")
                or len(f.get("outputs") or []) != 1):
            continue
        jenis = f["outputs"][0]["type"]
        if jenis not in ("bool", "address", "bytes32", "string") and not jenis.startswith(("uint", "int")):
            continue
        try:
            r = rpc.call(alamat, "0x" + keccak256(f"{f['name']}()".encode())[:8])
        except Exception:  # noqa: BLE001
            continue
        v = _nyahkod(jenis, r)
        if v is not None:
            hasil[f["name"]] = v
    return hasil


_RC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000, 0x000000000000808B, 0x0000000080000001,
       0x8000000080008081, 0x8000000000008009, 0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
       0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003, 0x8000000000008002, 0x8000000000000080,
       0x000000000000800A, 0x800000008000000A, 0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
_ROT = [1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 2, 14, 27, 41, 56, 8, 25, 43, 62, 18, 39, 61, 20, 44]
_PI = [10, 7, 11, 17, 18, 3, 5, 16, 8, 21, 24, 4, 15, 23, 19, 13, 12, 2, 20, 14, 22, 9, 6, 1]
_M = (1 << 64) - 1


def _keccakf(st):
    for r in range(24):
        bc = [st[i] ^ st[i + 5] ^ st[i + 10] ^ st[i + 15] ^ st[i + 20] for i in range(5)]
        for i in range(5):
            t = bc[(i + 4) % 5] ^ (((bc[(i + 1) % 5] << 1) | (bc[(i + 1) % 5] >> 63)) & _M)
            for j in range(0, 25, 5):
                st[j + i] ^= t
        t = st[1]
        for i in range(24):
            j = _PI[i]
            bc0 = st[j]
            st[j] = ((t << _ROT[i]) | (t >> (64 - _ROT[i]))) & _M
            t = bc0
        for j in range(0, 25, 5):
            row = st[j:j + 5]
            for i in range(5):
                st[j + i] = row[i] ^ ((~row[(i + 1) % 5]) & row[(i + 2) % 5] & _M)
        st[0] ^= _RC[r]


def keccak256(data):
    """Keccak-256 Ethereum (bukan SHA3) — tiada pustaka; disahkan dengan pemilih ERC-20 yang diketahui dalam ujian."""
    rate = 136
    m = bytearray(data) + b"\x01" + b"\x00" * ((rate - (len(data) + 1) % rate) % rate)
    m[-1] |= 0x80
    st = [0] * 25
    for off in range(0, len(m), rate):
        for i in range(rate // 8):
            st[i] ^= int.from_bytes(m[off + 8 * i: off + 8 * i + 8], "little")
        _keccakf(st)
    return b"".join(x.to_bytes(8, "little") for x in st[:4]).hex()
