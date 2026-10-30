import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

AKAR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AKAR))
CFG = json.loads((AKAR / "config.json").read_text())["scouts"]


class TestScouts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["MINTRADAR_STATE"] = self.tmp.name
        from radar import db
        self.con = db.buka()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()
        os.environ.pop("MINTRADAR_STATE", None)

    def test_mata_tertinggi_bukan_jumlah(self):
        from radar import scouts
        h = {"temuan": [{"kod": "OWNER_UBAH", "fungsi": "setFee"}, {"kod": "KEKAL_DANA", "fungsi": "pull"}]}
        p = {"temuan": [{"kod": "CUKAI_MERAH", "nilai": 30}]}
        self.assertEqual(scouts.nilai(h, p, CFG), (CFG["mata_kontrak"]["KEKAL_DANA"], "KEKAL_DANA"))

    def test_tanpa_sumber_sifar(self):
        from radar import scouts
        self.assertEqual(scouts.nilai({"temuan": [{"kod": "TIDAK_DISAHKAN", "fungsi": None}]}, None, CFG), (0, None))

    def test_dikenali_had_papan(self):
        from radar import scouts
        a = "0x" + "1" * 40
        self.assertFalse(scouts.dikenali(self.con, a))
        scouts.rekod(self.con, a, "ejenA", 10, "KEKAL_DANA", "p1", 86400 * 10 + 5)
        scouts.rekod(self.con, a, "ejenB", 10, "KEKAL_DANA", "p2", 86400 * 10 + 6)  # pendua diabaikan
        self.assertTrue(scouts.dikenali(self.con, a))
        self.assertEqual(scouts.laporan_hari_ini(self.con, "ejenA", 86400 * 10 + 99), 1)
        self.assertEqual(scouts.laporan_hari_ini(self.con, "ejenA", 86400 * 11 + 1), 0)
        b = scouts.papan(self.con)
        self.assertEqual([x["agent"] for x in b["leaderboard"]], ["ejenA"])
        self.assertEqual((b["reports"], b["confirmed"]), (1, 1))

    def test_halangan(self):
        from radar import scouts
        t = 1793400000
        lama = {"created_at": "2026-10-01T00:00:00.000Z", "wallet": "0xABC0000000000000000000000000000000000001"}
        self.assertEqual(scouts.halangan(dict(lama, created_at="2026-10-30T10:00:00.000Z"), None, CFG, 1793354400 + 3600), "BAHARU")
        self.assertEqual(scouts.halangan(lama, "0xabc0000000000000000000000000000000000001", CFG, t), "SENDIRI")
        self.assertIsNone(scouts.halangan(lama, "0x" + "9" * 40, CFG, t))
        self.assertIsNone(scouts.halangan(lama, None, CFG, t))
        self.assertEqual(scouts.halangan({}, None, CFG, t), "BAHARU")  # tiada tarikh = jangan percaya


if __name__ == "__main__":
    unittest.main()
