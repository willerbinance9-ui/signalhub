"""Signal Hub API tests."""
from __future__ import annotations

import os
import tempfile
import unittest

from fastapi.testclient import TestClient

# Configure before app import
_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"
os.environ["PROVIDER_KEYS"] = "provider-secret"
os.environ["CONSUMER_KEY"] = "consumer-secret"

from app.config import get_settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

get_settings.cache_clear()
init_db()

client = TestClient(app)
PROVIDER = {"X-Provider-Key": "provider-secret"}
CONSUMER = {"X-Consumer-Key": "consumer-secret"}


class TestSignalHub(unittest.TestCase):
    def test_health(self):
        r = client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])

    def test_create_requires_auth(self):
        r = client.post("/v1/signals", json={"action": "open", "symbol": "XAUUSD", "direction": "buy"})
        self.assertEqual(r.status_code, 401)

    def test_create_and_idempotency(self):
        body = {
            "external_id": "ext-001",
            "action": "open",
            "symbol": "XAUUSD",
            "direction": "buy",
            "order_type": "market",
            "sl": 2640,
            "tp": 2680,
        }
        r1 = client.post("/v1/signals", json=body, headers=PROVIDER)
        self.assertEqual(r1.status_code, 201)
        d1 = r1.json()
        self.assertEqual(d1["status"], "pending")
        self.assertFalse(d1["duplicate"])

        r2 = client.post("/v1/signals", json=body, headers=PROVIDER)
        self.assertEqual(r2.status_code, 200)
        d2 = r2.json()
        self.assertTrue(d2["duplicate"])
        self.assertEqual(d1["id"], d2["id"])

    def test_pending_and_ack(self):
        body = {
            "external_id": "ext-pending",
            "action": "open",
            "symbol": "EURUSD",
            "direction": "sell",
            "sl": 1.09,
            "tp": 1.08,
        }
        created = client.post("/v1/signals", json=body, headers=PROVIDER).json()
        pending = client.get("/v1/queue/pending", headers=CONSUMER)
        self.assertEqual(pending.status_code, 200)
        items = pending.json()["items"]
        ids = [i["id"] for i in items]
        self.assertIn(created["id"], ids)

        ack = client.post(
            f"/v1/queue/{created['id']}/ack",
            json={"status": "done", "setup_id": "setup-abc", "log_action": "executed"},
            headers=CONSUMER,
        )
        self.assertEqual(ack.status_code, 200)
        got = client.get(f"/v1/signals/{created['id']}", headers=CONSUMER).json()
        self.assertEqual(got["status"], "done")
        self.assertEqual(got["result"]["setup_id"], "setup-abc")

    def test_create_with_sendername(self):
        body = {
            "external_id": "ext-sender",
            "action": "open",
            "symbol": "XAUUSD",
            "direction": "buy",
            "sendername": "willerfx",
        }
        r = client.post("/v1/signals", json=body, headers=PROVIDER)
        self.assertEqual(r.status_code, 201)
        got = client.get(f"/v1/signals/{r.json()['id']}", headers=PROVIDER).json()
        self.assertEqual(got["payload"]["sendername"], "willerfx")


if __name__ == "__main__":
    unittest.main()
