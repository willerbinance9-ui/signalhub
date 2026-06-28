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
        self.assertEqual(got["progress"]["stage"], "queued")

    def test_list_signals_by_sendername(self):
        for ext, sn in [("ext-a", "alice"), ("ext-b", "bob"), ("ext-c", "alice")]:
            client.post("/v1/signals", json={
                "external_id": ext, "action": "open", "symbol": "XAUUSD",
                "direction": "buy", "sendername": sn,
            }, headers=PROVIDER)

        listed = client.get("/v1/signals?sendername=alice", headers=PROVIDER)
        self.assertEqual(listed.status_code, 200)
        data = listed.json()
        self.assertEqual(data["sendername"], "alice")
        self.assertEqual(data["count"], 2)
        ext_ids = {i["external_id"] for i in data["items"]}
        self.assertEqual(ext_ids, {"ext-a", "ext-c"})

    def test_sender_cannot_read_other_sender_signal(self):
        created = client.post("/v1/signals", json={
            "external_id": "ext-private",
            "action": "open",
            "symbol": "XAUUSD",
            "direction": "buy",
            "sendername": "alice",
        }, headers=PROVIDER).json()

        wrong = client.get(
            f"/v1/signals/{created['id']}?sendername=bob",
            headers=PROVIDER,
        )
        self.assertEqual(wrong.status_code, 404)

        ok = client.get(
            f"/v1/signals/{created['id']}?sendername=alice",
            headers=PROVIDER,
        )
        self.assertEqual(ok.status_code, 200)

    def test_get_by_external_id(self):
        client.post("/v1/signals", json={
            "external_id": "my-post-99",
            "action": "open",
            "symbol": "EURUSD",
            "direction": "sell",
            "sendername": "trader1",
        }, headers=PROVIDER)
        r = client.get("/v1/signals/external/my-post-99?sendername=trader1", headers=PROVIDER)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["external_id"], "my-post-99")

    def test_progress_after_ack(self):
        created = client.post("/v1/signals", json={
            "external_id": "ext-progress",
            "action": "open",
            "symbol": "XAUUSD",
            "direction": "buy",
            "sendername": "willerfx",
        }, headers=PROVIDER).json()
        client.post(
            f"/v1/queue/{created['id']}/ack",
            json={"status": "done", "setup_id": "s1", "log_action": "executed"},
            headers=CONSUMER,
        )
        got = client.get(
            f"/v1/signals/{created['id']}?sendername=willerfx",
            headers=PROVIDER,
        ).json()
        self.assertEqual(got["status"], "done")
        self.assertEqual(got["progress"]["stage"], "executed")
        self.assertTrue(got["progress"]["executed"])

    def test_api_logs_by_sendername(self):
        client.post("/v1/signals", json={
            "external_id": "ext-log-1",
            "action": "open",
            "symbol": "XAUUSD",
            "direction": "buy",
            "sendername": "logalice",
        }, headers=PROVIDER)
        logs = client.get("/v1/logs?sendername=logalice", headers=PROVIDER)
        self.assertEqual(logs.status_code, 200)
        data = logs.json()
        self.assertEqual(data["sendername"], "logalice")
        self.assertGreaterEqual(data["count"], 1)
        events = {i["event"] for i in data["items"]}
        self.assertIn("created", events)

        bob = client.get("/v1/logs?sendername=bob", headers=PROVIDER)
        self.assertEqual(bob.json()["count"], 0)

    def test_queue_recent(self):
        body = {
            "external_id": "ext-recent",
            "action": "open",
            "symbol": "EURUSD",
            "direction": "buy",
            "sendername": "trader1",
        }
        created = client.post("/v1/signals", json=body, headers=PROVIDER).json()
        recent = client.get("/v1/queue/recent?limit=10", headers=CONSUMER)
        self.assertEqual(recent.status_code, 200)
        ids = [i["id"] for i in recent.json()["items"]]
        self.assertIn(created["id"], ids)

    def test_order_type_messy_ui_label(self):
        """TraderRank and similar apps may send placeholder text as order_type."""
        body = {
            "external_id": "ext-messy-ot",
            "action": "open",
            "symbol": "XAUUSD",
            "direction": "buy",
            "order_type": "limit (or market / stop)",
            "entry": "5160 - 5170",
            "sl": 5150,
            "tp": 5200,
            "sendername": "willerfx",
        }
        r = client.post("/v1/signals", json=body, headers=PROVIDER)
        self.assertEqual(r.status_code, 201, r.text)
        payload = r.json()["payload"]
        self.assertEqual(payload["order_type"], "limit")
        self.assertEqual(payload["entry"], 5165.0)


    def test_order_type_open_alias(self):
        body = {
            "external_id": "ext-open-alias",
            "action": "open",
            "symbol": "XAUUSD",
            "direction": "buy",
            "order_type": "open",
            "sl": 2640,
            "tp": 2680,
        }
        r = client.post("/v1/signals", json=body, headers=PROVIDER)
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["payload"]["order_type"], "market")

    def test_image_fields_stored(self):
        body = {
            "external_id": "ext-img",
            "action": "open",
            "symbol": "XAUUSD",
            "direction": "buy",
            "order_type": "limit",
            "entry": 2650,
            "image_url": "https://example.com/chart.png",
            "image_mime": "image/png",
        }
        r = client.post("/v1/signals", json=body, headers=PROVIDER)
        self.assertEqual(r.status_code, 201)
        p = r.json()["payload"]
        self.assertEqual(p["image_url"], "https://example.com/chart.png")
        self.assertEqual(p["order_type"], "limit")


    def test_invalidate_pending_signal(self):
        created = client.post("/v1/signals", json={
            "external_id": "ext-inv-pending",
            "action": "open",
            "symbol": "XAUUSD",
            "direction": "buy",
            "order_type": "limit",
            "entry": 2650,
            "sendername": "willerfx",
        }, headers=PROVIDER).json()

        inv = client.post(
            f"/v1/signals/{created['id']}/invalidate",
            json={"reason": "deleted on channel"},
            headers=PROVIDER,
        )
        self.assertEqual(inv.status_code, 200)
        body = inv.json()
        self.assertEqual(body["status"], "invalidated")
        self.assertEqual(body["progress"]["stage"], "invalidated")
        self.assertFalse(body["duplicate"])

        again = client.post(
            f"/v1/signals/{created['id']}/invalidate",
            headers=PROVIDER,
        )
        self.assertTrue(again.json()["duplicate"])

        pending = client.get("/v1/queue/pending", headers=CONSUMER).json()["items"]
        self.assertNotIn(created["id"], [i["id"] for i in pending])

        inv_q = client.get("/v1/queue/invalidations", headers=CONSUMER)
        self.assertEqual(inv_q.status_code, 200)
        inv_ids = [i["id"] for i in inv_q.json()["items"]]
        self.assertIn(created["id"], inv_ids)

        ack = client.post(f"/v1/queue/{created['id']}/invalidate-ack", headers=CONSUMER)
        self.assertEqual(ack.status_code, 200)

        inv_q2 = client.get("/v1/queue/invalidations", headers=CONSUMER).json()["items"]
        self.assertNotIn(created["id"], [i["id"] for i in inv_q2])

    def test_invalidate_done_with_setup_id(self):
        created = client.post("/v1/signals", json={
            "external_id": "ext-inv-done",
            "action": "open",
            "symbol": "EURUSD",
            "direction": "sell",
            "order_type": "limit",
            "entry": 1.10,
            "sendername": "alice",
        }, headers=PROVIDER).json()
        client.post(
            f"/v1/queue/{created['id']}/ack",
            json={"status": "done", "setup_id": "setup-xyz", "log_action": "executed"},
            headers=CONSUMER,
        )

        inv = client.post(
            f"/v1/signals/external/ext-inv-done/invalidate?sendername=alice",
            json={"reason": "no longer valid"},
            headers=PROVIDER,
        )
        self.assertEqual(inv.status_code, 200)
        got = client.get(
            f"/v1/signals/{created['id']}?sendername=alice",
            headers=PROVIDER,
        ).json()
        self.assertEqual(got["status"], "invalidated")
        self.assertEqual(got["result"]["setup_id"], "setup-xyz")
        self.assertEqual(got["result"]["error"], "no longer valid")

    def test_force_entry_stored_as_market(self):
        body = {
            "external_id": "ext-force",
            "action": "open",
            "symbol": "XAUUSD",
            "direction": "buy",
            "order_type": "limit",
            "entry": 2650,
            "force_entry": True,
            "sl": 2640,
            "tp": 2680,
            "sendername": "willerfx",
        }
        r = client.post("/v1/signals", json=body, headers=PROVIDER)
        self.assertEqual(r.status_code, 201, r.text)
        p = r.json()["payload"]
        self.assertTrue(p["force_entry"])
        self.assertEqual(p["order_type"], "market")


if __name__ == "__main__":
    unittest.main()
