import unittest
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.universe_data import get_universe_symbols, normalize_symbol, get_all_universes

class TestUniverseData(unittest.TestCase):
    def test_normalize_symbol(self):
        self.assertEqual(normalize_symbol("RELIANCE"), "RELIANCE.NS")
        self.assertEqual(normalize_symbol("TCS.NS"), "TCS.NS")
        self.assertEqual(normalize_symbol("infy"), "INFY.NS")
        self.assertEqual(normalize_symbol("^NSEI"), "^NSEI")

    def test_nifty50_constituents(self):
        symbols = get_universe_symbols("Nifty 50")
        self.assertGreaterEqual(len(symbols), 50)
        self.assertIn("RELIANCE.NS", symbols)
        self.assertIn("HDFCBANK.NS", symbols)
        self.assertIn("TCS.NS", symbols)

    def test_nifty_next50_constituents(self):
        symbols = get_universe_symbols("Nifty Next 50")
        self.assertGreaterEqual(len(symbols), 50)

    def test_nifty100_constituents(self):
        symbols = get_universe_symbols("Nifty 100")
        self.assertGreaterEqual(len(symbols), 100)
        self.assertIn("RELIANCE.NS", symbols)

    def test_nifty_fno_constituents(self):
        symbols = get_universe_symbols("Nifty F&O")
        self.assertGreaterEqual(len(symbols), 150)

    def test_all_universes_catalog(self):
        catalog = get_all_universes()
        self.assertIn("Nifty 50", catalog)
        self.assertIn("Nifty Next 50", catalog)
        self.assertIn("Nifty 100", catalog)
        self.assertIn("Nifty F&O", catalog)
        self.assertGreater(catalog["Nifty 50"], 40)

if __name__ == "__main__":
    unittest.main()
