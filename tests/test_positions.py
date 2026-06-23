"""Signal Hub positions API tests."""
from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["PROVIDER_KEYS"] = "provider-secret"
os.environ["CONSUMER_KEY"] = "consumer-secret"
os.environ["QUANTUM_BRIDGE_URL"] = "http://quantum.test:8090"

from app.config import get_settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()
init_db()

client = TestClient(app)
PROVIDER = {"X-Provider-Key": "provider-secret"}


class TestPositionsAPI(unittest.TestCase):
    def test_positions_requires_bridge(self):
        with patch.dict(os.environ, {"QUANTUM_BRIDGE_URL": ""}, clear=False):
            get_settings.cache_clear()
            r = client.get("/v1/positions?sendername=alice", headers=PROVIDER)
            self.assertEqual(r.status_code, 503)
            get_settings.cache_clear()

    @patch("app.routers.positions.list_positions")
    def test_list_positions(self, mock_list):
        mock_list.return_value = {
            "sendername": "alice",
            "count": 1,
            "items": [{"ticket": 99, "symbol": "XAUUSD", "comment": "QTE alice"}],
        }
        r = client.get("/v1/positions?sendername=alice", headers=PROVIDER)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 1)

    @patch("app.routers.positions.close_position")
    def test_close_one(self, mock_close):
        mock_close.return_value = {
            "ok": True, "ticket": 99, "symbol": "XAUUSD", "profit": 5.0, "sendername": "alice",
        }
        r = client.post("/v1/positions/99/close?sendername=alice", headers=PROVIDER)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])


if __name__ == "__main__":
    unittest.main()
