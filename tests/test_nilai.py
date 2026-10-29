import json
import unittest
from pathlib import Path

from radar import nilai

CFG = json.loads((Path(__file__).resolve().parent.parent / "config.json").read_text())


def s(dari, penerima, wei=0, bil=1):
    return {"dari": dari, "penerima": penerima, "nilai_wei": wei, "bil": bil}


class Kelas(unittest.TestCase):
    def test_mint_sendiri_percuma(self):
        self.assertEqual(nilai.kelaskan([s("0xA", "0xa"), s("0xb", "0xb")], CFG["kelas"]), (nilai.KELAS_PERCUMA, 0.0))

    def test_airdrop_satu_penghantar(self):
        self.assertEqual(nilai.kelaskan([s("0xs", "0x1"), s("0xs", "0x2"), s("0xs", "0x3")], CFG["kelas"])[0], nilai.KELAS_AIRDROP)

    def test_harga_dibahagi_bilangan(self):
        k, h = nilai.kelaskan([s("0xa", "0xa", int(0.002e18), 2)], CFG["kelas"])
        self.assertEqual((k, h), (nilai.KELAS_BERBAYAR, 0.001))

    def test_bayaran_usdt_dalam_resit_bukan_percuma(self):
        sampel = [dict(s("0xa", "0xa"), token_bnb=0.0013), dict(s("0xb", "0xb"), token_bnb=0.0013)]
        self.assertEqual(nilai.kelaskan(sampel, CFG["kelas"])[0], nilai.KELAS_BERBAYAR)

    def test_mahal(self):
        self.assertEqual(nilai.kelaskan([s("0xa", "0xa", int(0.05e18))], CFG["kelas"])[0], nilai.KELAS_MAHAL)


class Pnl(unittest.TestCase):
    def test_tiada_pembeli_rugi_kos(self):
        self.assertEqual(nilai.pnl_tetingkap(1000, 0.0001, [], 6, 0.025), (-0.0001, None, 0))

    def test_median_dalam_tetingkap_sahaja(self):
        jualan = [(500, 9.0), (1500, 0.002), (2000, 0.004), (1000 + 7 * 3600, 9.0)]
        p, m, bil = nilai.pnl_tetingkap(1000, 0.0, jualan, 6, 0.025)
        self.assertEqual((m, bil), (0.003, 2))
        self.assertAlmostEqual(p, 0.003 * 0.975)


class HargaJualan(unittest.TestCase):
    TOKEN = {k: v for k, v in CFG["token_bayaran"].items() if k.startswith("0x")}
    USDT = "0x55d398326f99059ff775485246999027b3197955"

    def log(self, token, dari, amaun):
        return {"address": token, "topics": [nilai.TRANSFER, "0x" + "0" * 24 + dari[2:], "0x" + "0" * 64], "data": hex(int(amaun * 1e18))}

    def test_usdt_dari_pembeli_dikira(self):
        tx = {"from": "0x" + "a" * 40, "value": "0x0"}
        resit = {"logs": [self.log(self.USDT, "0x" + "a" * 40, 1.5), self.log(self.USDT, "0x" + "b" * 40, 99)]}
        self.assertAlmostEqual(nilai.harga_jualan_bnb(tx, resit, 1, self.TOKEN, 750), 1.5 / 750)

    def test_bnb_asli_dibahagi_nft(self):
        tx = {"from": "0x" + "a" * 40, "value": hex(int(0.004e18))}
        self.assertAlmostEqual(nilai.harga_jualan_bnb(tx, {"logs": []}, 2, self.TOKEN, 750), 0.002)

    def test_terima_tawaran_kira_yang_masuk_ke_penjual(self):
        penjual, pembeli = "0x" + "c" * 40, "0x" + "d" * 40
        tx = {"from": penjual, "value": "0x0"}
        l = self.log(self.USDT, pembeli, 3.0)
        l["topics"][2] = "0x" + "0" * 24 + penjual[2:]
        self.assertAlmostEqual(nilai.harga_jualan_bnb(tx, {"logs": [l]}, 1, self.TOKEN, 750, penjual, pembeli), 3.0 / 750)

    def test_pindah_ke_diri_sendiri_sifar(self):
        a = "0x" + "e" * 40
        self.assertEqual(nilai.harga_jualan_bnb({"from": a, "value": hex(10**18)}, {"logs": []}, 1, self.TOKEN, 750, a, a), 0)

    def test_pindah_biasa_sifar(self):
        self.assertEqual(nilai.harga_jualan_bnb({"from": "0x" + "a" * 40, "value": "0x0"}, {"logs": []}, 1, self.TOKEN, 750), 0)


if __name__ == "__main__":
    unittest.main()
