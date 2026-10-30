import json
import unittest
from pathlib import Path

from radar import bundle, pasaran

CFG = json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text())["pasaran"]
SIFAR = "0x" + "0" * 40
CURVE, ROUTER = "0x" + "c" * 40, "0x" + "e" * 40


def t(a):
    return "0x" + "0" * 24 + a[2:]


def log(tx, blok, dari, ke, n):
    return {"transactionHash": tx, "blockNumber": hex(blok), "logIndex": "0x0",
            "topics": [bundle.TRANSFER, t(dari), t(ke)], "data": hex(n)}


W = ["0x" + str(i) * 40 for i in range(1, 6)]


class TestBundle(unittest.TestCase):
    def test_router_dibuang_pencipta_dikira(self):
        ls = [log("0xa", 100, SIFAR, CURVE, 1000), log("0xa", 100, CURVE, W[0], 50),          # cetak + beli pencipta
              log("0xb", 105, CURVE, ROUTER, 30), log("0xb", 105, ROUTER, W[1], 30),          # beli melalui router
              log("0xc", 106, W[1], ROUTER, 10), log("0xc", 106, ROUTER, CURVE, 10)]          # jual: bukan pembeli
        b = bundle.pembeli(ls, {CURVE, SIFAR})
        self.assertEqual([(x[1], x[2], x[3]) for x in b], [(W[0], 50, "0xa"), (W[1], 30, "0xb")])

    def test_blok_sama(self):
        beli = [(110, W[0], 10), (110, W[1], 10), (110, W[2], 10), (111, W[3], 10), (112, W[4], 5)]
        a = bundle.analisis(beli, 100, CFG["bundle"])
        self.assertEqual((a["blok_bundle"], len(a["dompet"]), round(a["pct_dibeli"]), a["pembeli_awal"]), (1, 3, 30, 5))
        self.assertEqual(bundle.analisis(beli[:2], 100, CFG["bundle"])["blok_bundle"], 0)

    def test_kaitan(self):
        bb = [(110, W[0], 10, "0x1"), (110, W[1], 10, "0x1"), (110, W[2], 10, "0x2"), (110, W[3], 10, "0x3"), (110, W[4], 10, "0x4")]
        k = bundle.kaitan(bb, {"0x1": W[0], "0x2": W[2], "0x3": "0x" + "9" * 40, "0x4": "0x" + "9" * 40}, {W[0]: 0, W[1]: 50}, CFG["bundle"])
        self.assertEqual((k["terpaut"], k["baharu"]), (4, 1))  # tx 0x1 = W0+W1; penghantar 0x99.. = W3+W4; W2 beli sendiri
        self.assertEqual(bundle.kaitan(bb[2:3], {"0x2": W[2]}, {}, CFG["bundle"])["terpaut"], 0)

    def test_terpaut_menaikkan_label(self):
        gp = {"token_symbol": "X", "holders": [], "owner_address": SIFAR}
        dex = {"pairAddress": "0x" + "f" * 40, "liquidity": {"usd": 50000}, "volume": {"h24": 1000}, "marketCap": 90000}
        bun = {"dompet": 10, "pct_dibeli": 30, "pct_masih": 6, "kaitan": {"terpaut": 5, "baharu": 2, "disemak": 10}}
        self.assertEqual(pasaran.nilai(gp, dex, CFG, "", bun)["label"], "merah")
        bun["kaitan"]["terpaut"] = 0
        self.assertEqual(pasaran.nilai(gp, dex, CFG, "", bun)["label"], "kuning")

    def test_tahap_ikut_masih_dipegang(self):
        gp = {"token_symbol": "X", "holders": [], "owner_address": SIFAR}
        dex = {"pairAddress": "0x" + "f" * 40, "liquidity": {"usd": 50000}, "volume": {"h24": 1000}, "marketCap": 90000}
        kod = lambda h: {x["kod"] for x in h["temuan"]}  # noqa: E731
        bun = {"dompet": 20, "pct_dibeli": 40, "pct_masih": 0}
        h = pasaran.nilai(gp, dex, CFG, "", bun)
        self.assertEqual((h["label"], "BUNDLE_KELUAR" in kod(h)), ("hijau", True))
        h = pasaran.nilai(gp, dex, CFG, "", dict(bun, pct_masih=8))
        self.assertEqual((h["label"], "BUNDLE_MASIH" in kod(h)), ("kuning", True))
        self.assertEqual(pasaran.nilai(gp, dex, CFG, "", dict(bun, pct_masih=20))["label"], "merah")


if __name__ == "__main__":
    unittest.main()
