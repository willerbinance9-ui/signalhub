# AARE Signal Hub API

External signal ingest service for third-party apps. Deploy on Render; AARE Quantum polls and executes on MT5.

## Base URL

```
https://your-service.onrender.com
```

Interactive docs: `GET /docs`

## Authentication

Two API keys (set as environment variables on Render):

| Header | Who uses it | Env var |
|--------|-------------|---------|
| `X-Provider-Key` | Your third-party app posting signals | `PROVIDER_KEYS` (comma-separated) |
| `X-Consumer-Key` | AARE Quantum VPS polling the queue | `CONSUMER_KEY` |

---

## POST /v1/signals

Submit a new trading signal.

### Headers

```
Content-Type: application/json
X-Provider-Key: your-provider-secret
```

### Request body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `external_id` | string | recommended | Your platform message ID — duplicate POSTs return the same signal (idempotent) |
| `action` | string | yes | `open`, `add`, `close`, `breakeven`, `modify`, `partial_close`, `close_all` |
| `symbol` | string | open/add | e.g. `XAUUSD`, `GBPUSD`, `Volatility 75 Index` — must exist on Quantum watchlist |
| `direction` | string | open/add | `buy` or `sell` (also accepts `long`/`short`) |
| `order_type` | string | no | `market` (default), `limit`, `stop` |
| `entry` | number | no | Limit/stop price; omit for market (Quantum uses live MT5 price) |
| `sl` | number | no | Stop loss; Quantum auto-builds 2R if omitted (trusted path) |
| `tp` | number | no | Take profit |
| `lot` | number | no | Fixed lot (optional; Quantum sizes from risk % if omitted) |
| `lot_scale` | number | no | Scale for add/partial (0.01–10) |
| `ticket` | integer | no | MT5 ticket for modify/close when symbol ambiguous |
| `message` | string | no | Raw text for logs |
| `provider_name` | string | no | Display name in Quantum logs (e.g. `Alpha Signals`) |
| `confidence` | number | no | 0–100 (default 100 for trusted execution) |

### Example — market buy gold

```json
{
  "external_id": "post-8842",
  "action": "open",
  "symbol": "XAUUSD",
  "direction": "buy",
  "order_type": "market",
  "sl": 2640.0,
  "tp": 2680.0,
  "message": "BUY GOLD NOW SL 2640 TP 2680",
  "provider_name": "My Signal Platform"
}
```

### Responses

| HTTP | Meaning |
|------|---------|
| 201 | Signal queued |
| 200 | Duplicate `external_id` — returns existing signal (`duplicate: true`) |
| 401 | Invalid `X-Provider-Key` |
| 422 | Validation error (missing symbol/direction, etc.) |

### cURL

```bash
curl -X POST "https://your-hub.onrender.com/v1/signals" \
  -H "Content-Type: application/json" \
  -H "X-Provider-Key: YOUR_PROVIDER_KEY" \
  -d '{
    "external_id": "post-8842",
    "action": "open",
    "symbol": "XAUUSD",
    "direction": "buy",
    "order_type": "market",
    "sl": 2640,
    "tp": 2680,
    "provider_name": "My Platform"
  }'
```

### JavaScript (fetch)

```javascript
const res = await fetch("https://your-hub.onrender.com/v1/signals", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "X-Provider-Key": process.env.SIGNAL_HUB_PROVIDER_KEY,
  },
  body: JSON.stringify({
    external_id: String(postId),
    action: "open",
    symbol: "XAUUSD",
    direction: "buy",
    order_type: "market",
    sl: 2640,
    tp: 2680,
    provider_name: "My Platform",
  }),
});
const signal = await res.json();
console.log(signal.id, signal.status, signal.duplicate);
```

### Python

```python
import httpx

resp = httpx.post(
    "https://your-hub.onrender.com/v1/signals",
    headers={"X-Provider-Key": "YOUR_PROVIDER_KEY"},
    json={
        "external_id": "post-8842",
        "action": "open",
        "symbol": "XAUUSD",
        "direction": "buy",
        "order_type": "market",
        "sl": 2640.0,
        "tp": 2680.0,
        "provider_name": "My Platform",
    },
    timeout=30,
)
resp.raise_for_status()
data = resp.json()
print(data["id"], data["status"])
```

---

## Follow-up actions

### Breakeven

```json
{
  "external_id": "post-8842-be",
  "action": "breakeven",
  "symbol": "XAUUSD",
  "provider_name": "My Platform"
}
```

### Close

```json
{
  "action": "close",
  "symbol": "XAUUSD",
  "message": "Close gold — TP hit"
}
```

### Modify SL/TP

```json
{
  "action": "modify",
  "symbol": "XAUUSD",
  "sl": 2655.0,
  "tp": 2700.0
}
```

---

## GET /v1/signals/{id}

Check signal status. Auth: `X-Provider-Key` or `X-Consumer-Key`.

```bash
curl "https://your-hub.onrender.com/v1/signals/SIGNAL_UUID" \
  -H "X-Provider-Key: YOUR_PROVIDER_KEY"
```

Response:

```json
{
  "id": "uuid",
  "external_id": "post-8842",
  "status": "done",
  "payload": { "...": "..." },
  "result": {
    "setup_id": "abc123",
    "log_action": "executed",
    "error": null
  },
  "created_at": "2026-06-21T12:00:00Z",
  "acked_at": "2026-06-21T12:00:05Z",
  "duplicate": false
}
```

Status values: `pending` → `processing` → `done` | `failed`

---

## GET /v1/queue/pending (Quantum consumer)

Poll new signals. Marks returned rows as `processing`.

```
X-Consumer-Key: YOUR_CONSUMER_KEY
```

```json
{
  "items": [
    {
      "id": "uuid",
      "external_id": "post-8842",
      "status": "processing",
      "payload": { "action": "open", "symbol": "XAUUSD", ... },
      "created_at": "..."
    }
  ],
  "count": 1
}
```

---

## POST /v1/queue/{id}/ack (Quantum consumer)

Mark signal processed after MT5 execution attempt.

```json
{
  "status": "done",
  "setup_id": "quantum-setup-uuid",
  "log_action": "executed",
  "error": null
}
```

On failure:

```json
{
  "status": "failed",
  "error": "MT5 offline or risk rejected"
}
```

---

## GET /health

No auth. Used by Render health checks.

```json
{ "ok": true, "service": "aare-signal-hub" }
```

---

## Render deployment

1. Push repo; create **Web Service** from `aare_signal_hub/` (Dockerfile).
2. Add **PostgreSQL**; link `DATABASE_URL`.
3. Set secrets:
   - `PROVIDER_KEYS= key1,key2` (for your app)
   - `CONSUMER_KEY= long-random-secret` (for Quantum dashboard)
4. Copy service URL into Quantum → Settings → **Signal Hub URL** + consumer key.

## Quantum setup

1. Dashboard → Settings → enable **Signal Hub listener**
2. Set **Signal Hub URL** = `https://your-hub.onrender.com`
3. Set **Signal Hub consumer key** = same as `CONSUMER_KEY`
4. Ensure operating mode is **Auto trade** and MT5 is connected
5. Trusted direct execution applies (risk limits only, no MTF gate)

Signals poll every 5 seconds by default (`signal_hub_poll_seconds`).
