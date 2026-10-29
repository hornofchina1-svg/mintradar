"""Klien JSON-RPC BSC: senarai titik hujung ikut peranan (log / baca), cuba yang seterusnya bila gagal."""
import json
import threading
import time
import urllib.error
import urllib.request


class RpcGagal(Exception):
    pass


class Rpc:
    def __init__(self, cfg, tambahan=None):
        """tambahan = URL RPC peribadi (cth QuickNode) dari fail di state/ — rahsia, tidak dikomit. Ditambah SEBAGAI SANDARAN
        (hujung senarai) bila `peribadi_dahulu` false: QuickNode percuma 0.5–1 s sepanggil vs dataseed 0.1 s (diukur 29 Okt)."""
        self.cfg = dict(cfg)
        for item in tambahan or []:
            url, senarai = item if isinstance(item, tuple) else (item, None)
            for peranan in senarai or cfg.get("peribadi_peranan", ["baca"]):
                if peranan in self.cfg and url not in self.cfg[peranan]:
                    lain = list(self.cfg[peranan])
                    self.cfg[peranan] = [url] + lain if cfg.get("peribadi_dahulu") else lain + [url]
        self._id = 0
        self._kunci = threading.Lock()
        self._akhir = {}

    def _tunggu_giliran(self, url):
        """Had kadar ringkas per URL (`sela_min` dalam config): RPC percuma menjawab 429 bila diasak serentak (diukur 29 Okt)."""
        sela = next((v for k, v in self.cfg.get("sela_min", {}).items() if k in url), 0)
        if not sela:
            return
        with self._kunci:
            tunggu = self._akhir.get(url, 0) + sela - time.time()
            self._akhir[url] = time.time() + max(0, tunggu)
        if tunggu > 0:
            time.sleep(tunggu)

    def _satu(self, url, method, params):
        self._tunggu_giliran(url)
        self._id += 1
        badan = json.dumps({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}).encode()
        req = urllib.request.Request(url, badan, {"Content-Type": "application/json", "User-Agent": self.cfg["ua"]})
        with urllib.request.urlopen(req, timeout=self.cfg["tamat_saat"]) as r:
            d = json.load(r)
        if "error" in d:
            raise RpcGagal(f"{url} {method}: {d['error']}")
        return d["result"]

    def panggil(self, method, params, peranan="baca"):
        ralat = []
        senarai = list(self.cfg[peranan])
        if peranan in self.cfg.get("putar", []) and senarai:  # agih beban antara hos berkuota sendiri
            with self._kunci:
                self._putaran = getattr(self, "_putaran", 0) + 1
                k = self._putaran % len(senarai)
            senarai = senarai[k:] + senarai[:k]
        for cubaan in range(2):
            for url in senarai:
                try:
                    return self._satu(url, method, params)
                except RpcGagal as e:
                    if "revert" in str(e).lower():
                        raise  # kontrak menolak panggilan: jawapan muktamad, RPC lain akan jawab sama
                    ralat.append(str(e)[:160])
                except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                    ralat.append(str(e)[:160])
            time.sleep(1.5 * (cubaan + 1))
        raise RpcGagal("; ".join(ralat[-3:]))

    def blok_terkini(self):
        return int(self.panggil("eth_blockNumber", []), 16)

    def masa_blok(self, n):
        return int(self.panggil("eth_getBlockByNumber", [hex(n), False])["timestamp"], 16)

    def log(self, dari, hingga, topics, alamat=None, peranan="log"):
        f = {"fromBlock": hex(dari), "toBlock": hex(hingga), "topics": topics}
        if alamat:
            f["address"] = alamat
        return self.panggil("eth_getLogs", [f], peranan)

    def tx(self, h):
        return self.panggil("eth_getTransactionByHash", [h])

    def resit(self, h):
        return self.panggil("eth_getTransactionReceipt", [h])

    def call(self, ke, data):
        return self.panggil("eth_call", [{"to": ke, "data": data}, "latest"])

    def harga_gas(self):
        return int(self.panggil("eth_gasPrice", []), 16)
