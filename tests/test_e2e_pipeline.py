import unittest
from pathlib import Path
import sys
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.app import app

class TestE2EPipeline(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_serve_homepage(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Darvas Bearish + Bullish Combo", resp.text)
        self.assertIn("Vanilla + Magic", resp.text)
        self.assertIn("Download Excel (.xlsx)", resp.text)

    def test_backtest_api_stock_mode(self):
        # Run test with synthetic or cached symbol
        payload = {
            "mode": "stock",
            "variant": "magic",
            "symbol": "RELIANCE",
            "total_capital": 100000.0,
            "max_active_stocks": 5,
            "num_parts": 5,
            "start_date": "2023-01-01",
            "end_date": "2023-06-30",
            "target_pct": 5.0
        }
        resp = self.client.post("/api/backtest", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("run_id", data)
        self.assertEqual(data["mode"], "stock")
        self.assertIn("summary", data)
        self.assertIn("xirr_pct", data["summary"])
        self.assertIn("deployed_xirr_pct", data["summary"])

        # Test Excel download endpoint with this run_id
        run_id = data["run_id"]
        excel_resp = self.client.get(f"/api/export-excel?run_id={run_id}")
        self.assertEqual(excel_resp.status_code, 200)
        self.assertIn("application/vnd.openxmlformats", excel_resp.headers["content-type"])

if __name__ == "__main__":
    unittest.main()
