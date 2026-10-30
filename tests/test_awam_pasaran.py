import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path


class TestAwamPasaran(unittest.TestCase):
    """D34: API datt.my membawa 'market' dalam EN; disahkan BscScan = kuning SUMBER_BSCSCAN, bukan merah TIDAK_DISAHKAN."""

    def test_market_dalam_json(self):
        tmp = Path(tempfile.mkdtemp())
        os.environ["MINTRADAR_STATE"] = str(tmp / "st")
        try:
            from radar import awam, db
            con = db.buka()
            a = "0x" + "a" * 40
            con.execute("INSERT INTO semakan VALUES (?,?,?,?,?,?)", (a, 1, "merah", json.dumps([{"kod": "TIDAK_DISAHKAN", "fungsi": None}]), "[]", None))
            db.simpan_pasaran(con, a, {"label": "kuning", "temuan": [{"kod": "VOLUME_BOT", "nilai": "20x"}],
                                       "ringkas": {"simbol": "TKN", "sumber_terbuka": True, "pemegang": 9},
                                       "bundle": {"dompet": 4, "pct_masih": 1.0, "kaitan": {"terpaut": 0}}}, 2)
            (tmp / "repo" / "laman").mkdir(parents=True)
            shutil.copy(Path(__file__).resolve().parent.parent / "laman" / "bahasa.json", tmp / "repo" / "laman" / "bahasa.json")
            awam.tulis_kontrak(con, tmp / "repo" / "data" / "kontrak", int(time.time()))
            d = json.loads((tmp / "repo" / "data" / "kontrak" / f"{a}.json").read_text())
            self.assertEqual((d["name"], d["label"], d["findings"][0]["code"]), ("TKN", "kuning", "SUMBER_BSCSCAN"))
            self.assertEqual(d["market"]["summary"]["holders"], 9)
            self.assertEqual(d["market"]["bundle"]["links"]["linked_wallets"], 0)
            self.assertIn("20x", d["market"]["findings"][0]["text"])
            ix = json.loads((tmp / "repo" / "data" / "kontrak" / "index.json").read_text())
            self.assertEqual(ix["contracts"][0]["label"], "kuning")
        finally:
            os.environ.pop("MINTRADAR_STATE", None)


if __name__ == "__main__":
    unittest.main()
