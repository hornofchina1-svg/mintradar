import json
import unittest
from pathlib import Path

from radar import pasaran

CFG = json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text())["pasaran"]
TOKEN = "0x1111111111111111111111111111111111111111"
PAIR = "0x2222222222222222222222222222222222222222"


def gp(**k):
    d = {"token_symbol": "X", "holder_count": "500", "is_open_source": "1", "buy_tax": "0", "sell_tax": "0",
         "creator_percent": "0", "owner_address": "0x0000000000000000000000000000000000000000", "holders": []}
    d.update(k)
    return d


DEX = {"dexId": "pancakeswap", "pairAddress": PAIR, "liquidity": {"usd": 20000}, "volume": {"h24": 10000}, "marketCap": 50000}


def kod(h):
    return {x["kod"] for x in h["temuan"]}


class TestPasaran(unittest.TestCase):
    def test_bukan_token(self):
        self.assertIsNone(pasaran.nilai({}, None, CFG))
        self.assertIsNone(pasaran.nilai(None, DEX, CFG))

    def test_bersih_hijau(self):
        self.assertEqual(pasaran.nilai(gp(), DEX, CFG, TOKEN)["label"], "hijau")

    def test_honeypot_merah(self):
        h = pasaran.nilai(gp(is_honeypot="1"), DEX, CFG, TOKEN)
        self.assertEqual((h["label"], "HONEYPOT" in kod(h)), ("merah", True))

    def test_cukai(self):
        self.assertIn("CUKAI_KUNING", kod(pasaran.nilai(gp(sell_tax="0.06"), DEX, CFG, TOKEN)))
        self.assertEqual(pasaran.nilai(gp(sell_tax="0.25"), DEX, CFG, TOKEN)["label"], "merah")

    def test_pemegang_kecuali_lp_kosong_terkunci_diri(self):
        holders = [{"address": PAIR, "percent": "0.5"}, {"address": "0x000000000000000000000000000000000000dEaD", "percent": "0.2"},
                   {"address": "0x3333333333333333333333333333333333333333", "percent": "0.3", "is_locked": 1},
                   {"address": TOKEN, "percent": "0.7"}, {"address": "0x4444444444444444444444444444444444444444", "percent": "0.01"}]
        self.assertNotIn("PEMEGANG_BESAR", kod(pasaran.nilai(gp(holders=holders), DEX, CFG, TOKEN)))
        holders.append({"address": "0x5555555555555555555555555555555555555555", "percent": "0.05"})
        self.assertIn("PEMEGANG_BESAR", kod(pasaran.nilai(gp(holders=holders), DEX, CFG, TOKEN)))

    def test_volume_bot(self):
        dex = dict(DEX, volume={"h24": 1_200_000}, marketCap=40_000)
        h = pasaran.nilai(gp(), dex, CFG, TOKEN)
        self.assertIn("VOLUME_BOT", kod(h))
        self.assertEqual(h["label"], "kuning")

    def test_cetak_hanya_bila_pemilik_aktif(self):
        self.assertNotIn("BOLEH_CETAK", kod(pasaran.nilai(gp(is_mintable="1"), DEX, CFG, TOKEN)))
        self.assertIn("BOLEH_CETAK", kod(pasaran.nilai(gp(is_mintable="1", owner_address=TOKEN.replace("1", "9")), DEX, CFG, TOKEN)))

    def test_teks_setiap_kod_dwibahasa(self):
        b = json.loads((Path(__file__).resolve().parent.parent / "laman" / "bahasa.json").read_text())
        for k in pasaran.MERAH | {"CUKAI_KUNING", "CUKAI_BOLEH_UBAH", "BOLEH_CETAK", "BOLEH_JEDA", "SENARAI_HITAM", "PEMEGANG_BESAR",
                                   "TUMPU_TOP10", "PENCIPTA_BESAR", "LIKUIDITI_RENDAH", "VOLUME_BOT", "TIADA_PASANGAN"}:
            self.assertIn("pasaran_" + k, b["ms"])
            self.assertIn("pasaran_" + k, b["en"])


if __name__ == "__main__":
    unittest.main()
