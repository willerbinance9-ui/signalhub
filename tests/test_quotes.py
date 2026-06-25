"""Quote API tests."""
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


class TestQuoteAPI(unittest.TestCase):
    @patch("app.routers.quotes.get_quote")
    def test_get_quote(self, mock_quote):
        mock_quote.return_value = {
            "symbol": "XAUUSD",
            "resolved_symbol": "XAUUSD",
            "bid": 2650.1,
            "ask": 2650.3,
            "price": 2650.2,
            "mid": 2650.2,
            "spread": 0.2,
            "digits": 2,
            "point": 0.01,
            "time": "2026-06-25T12:00:00Z",
            "source": "mt5",
        }
        r = client.get("/v1/quote?symbol=XAUUSD", headers=PROVIDER)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["price"], 2650.2)

    @patch("app.routers.quotes.post_quote")
    def test_post_quote(self, mock_post):
        mock_post.return_value = {
            "symbol": "GOLD",
            "resolved_symbol": "XAUUSD",
            "bid": 2650.0,
            "ask": 2650.2,
            "price": 2650.1,
            "mid": 2650.1,
            "spread": 0.2,
            "digits": 2,
            "point": 0.01,
            "time": "2026-06-25T12:00:00Z",
            "source": "mt5",
        }
        r = client.post("/v1/quote", json={"symbol": "GOLD"}, headers=PROVIDER)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["resolved_symbol"], "XAUUSD")


if __name__ == "__main__":
    unittest.main()
