import json
import os
import tempfile
import unittest
from pathlib import Path


class TestToken(unittest.TestCase):
    """D37: seksyen token datt.my — tiada fail/entri = None (tersorok); sebelum lancar = status + masa, tanpa panggilan rangkaian."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        os.environ["MINTRADAR_STATE"] = str(self.d)
        (self.d / "boltbook").mkdir()
        self.cfg = {"token": {"simbol": "MRADAR"}, "mint": {"wallet": "0x" + "1" * 40}}

    def tearDown(self):
        os.environ.pop("MINTRADAR_STATE", None)

    def test_tiada_data(self):
        from radar import token
        self.assertIsNone(token.bina(None, self.cfg))
        (self.d / "boltbook" / "lancar.json").write_text(json.dumps({"LAIN": {}}))
        self.assertIsNone(token.bina(None, self.cfg))

    def test_menunggu(self):
        from radar import token
        (self.d / "boltbook" / "lancar.json").write_text(json.dumps(
            {"MRADAR": {"status": "notice", "token": None, "launches_at": "2026-10-30T01:17:32.256Z"}}))
        h = token.bina(None, self.cfg)
        self.assertEqual((h["status"], h["alamat"], h["lancar_pada"], h["cukai_bnb"]), ("notice", None, "2026-10-30T01:17:32.256Z", None))

    def test_pemilih(self):
        from radar import token
        self.assertEqual(token.sel("transfer(address,uint256)"), "0xa9059cbb")


if __name__ == "__main__":
    unittest.main()
