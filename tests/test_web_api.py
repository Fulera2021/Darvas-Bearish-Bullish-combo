import unittest
from pathlib import Path
import sys
from fastapi.testclient import TestClient

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.app import app

class TestWebApi(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")

    def test_get_universes(self):
        response = self.client.get("/api/universes")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("universes", data)
        self.assertIn("Nifty 50", data["universes"])

    def test_max_active_stocks_validation_limits(self):
        # 75 and 100 should be accepted (not return 422 validation error)
        for valid_limit in [50, 75, 100, 200]:
            payload = {
                "mode": "universe",
                "variant": "vanilla",
                "universe": "Nifty F&O",
                "total_capital": 3000000.0,
                "max_active_stocks": valid_limit,
                "num_parts": 4,
                "start_date": "2024-01-01",
                "end_date": "2024-03-01",
                "target_pct": 5.0
            }
            # We test validation by checking that status code is not 422
            response = self.client.post("/api/backtest", json=payload)
            self.assertNotEqual(
                response.status_code, 422,
                f"max_active_stocks={valid_limit} should not fail Pydantic validation (got 422)"
            )

        # > 250 should be rejected by Pydantic validation (422)
        invalid_payload = {
            "mode": "universe",
            "variant": "vanilla",
            "universe": "Nifty F&O",
            "total_capital": 3000000.0,
            "max_active_stocks": 251,
            "num_parts": 4,
            "start_date": "2024-01-01",
            "end_date": "2024-03-01",
            "target_pct": 5.0
        }
        resp_invalid = self.client.post("/api/backtest", json=invalid_payload)
        self.assertEqual(resp_invalid.status_code, 422)

if __name__ == "__main__":
    unittest.main()
