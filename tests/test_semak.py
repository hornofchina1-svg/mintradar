import unittest

from radar import semak

ABI = [{"type": "function", "name": n, "stateMutability": "nonpayable"} for n in ("withdrawUsdt", "setPrice", "withdraw", "mint", "approve")]
PINTU_BELAKANG = """
contract T {
    address public constant usdtKeeper = 0xE00fFD8082694D241Ff733845AbF523E5D57E41d;
    address public admin;
    function withdrawUsdt() external {
        if (msg.sender == admin) { revert(); } else if (msg.sender != usdtKeeper) { revert(); }
        _usdtTransfer(msg.sender, 1);
    }
    function setPrice(uint256 p) external onlyOwner { price = p; }
    function withdraw() external onlyOwner { payable(owner()).transfer(address(this).balance); }
    function mint() external {}
}
"""


class Semak(unittest.TestCase):
    def test_kuasa_kekal_ke_atas_dana_merah(self):
        h = semak.analisis({"T.sol": PINTU_BELAKANG}, ABI, owner="0x" + "0" * 40)
        self.assertEqual(h["label"], "merah")
        self.assertIn({"kod": "KEKAL_DANA", "fungsi": "withdrawUsdt"}, h["temuan"])
        self.assertIn({"kod": "DILEPASKAN", "fungsi": None}, h["temuan"])

    def test_owner_hidup_kuning(self):
        sumber = PINTU_BELAKANG.replace("withdrawUsdt", "x_tiada")
        h = semak.analisis({"T.sol": sumber}, ABI[1:], owner="0x" + "1" * 40)
        self.assertEqual(h["label"], "kuning")
        kod = {(t["kod"], t["fungsi"]) for t in h["temuan"]}
        self.assertIn(("OWNER_DANA", "withdraw"), kod)
        self.assertIn(("OWNER_UBAH", "setPrice"), kod)

    def test_dilepaskan_tanpa_kuasa_kekal_hijau(self):
        sumber = PINTU_BELAKANG.replace("withdrawUsdt", "x_tiada")
        self.assertEqual(semak.analisis({"T.sol": sumber}, ABI[1:], owner="0x" + "0" * 40)["label"], "hijau")

    def test_proksi_merah(self):
        self.assertEqual(semak.analisis({"T.sol": "contract T {}"}, [], impl="0x" + "0" * 24 + "ab" * 20)["label"], "merah")

    def test_pustaka_diabaikan(self):
        h = semak.analisis({"@openzeppelin/Ownable.sol": "function setX() external onlyOwner {}", "T.sol": "contract T {}"},
                           [{"type": "function", "name": "setX", "stateMutability": "nonpayable"}], owner="0x" + "1" * 40)
        self.assertEqual(h["admin"], [])

    def test_pengawal_dalaman_immutable(self):
        sumber = """
        contract V {
            address public immutable treasury;
            function _onlyTreasury() private view { if (msg.sender != treasury) revert(); }
            function setPaused(bool x) external { _onlyTreasury(); paused = x; }
            function seed() external { _onlyTreasury(); usdt.transfer(treasury, 1); }
        }"""
        abi = [{"type": "function", "name": n, "stateMutability": "nonpayable"} for n in ("setPaused", "seed")]
        h = semak.analisis({"V.sol": sumber}, abi)
        kod = {(t["kod"], t["fungsi"]) for t in h["temuan"]}
        self.assertIn(("KEKAL_KUASA", "setPaused"), kod)
        self.assertIn(("KEKAL_DANA", "seed"), kod)
        self.assertEqual(h["label"], "merah")


if __name__ == "__main__":
    unittest.main()
