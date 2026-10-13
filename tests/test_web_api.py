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

if __name__ == "__main__":
    unittest.main()
