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

### Environment variables (Render)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | yes | PostgreSQL connection string |
| `PROVIDER_KEYS` | yes | Comma-separated provider API keys |
| `CONSUMER_KEY` | yes | Secret for Quantum to poll/ack |
| `QUANTUM_BRIDGE_URL` | for positions | Quantum VPS URL, e.g. `http://your-vps:8090` — enables live position API |

### Endpoint overview (provider)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/signals` | Submit open/close/modify signal |
| `GET` | `/v1/signals` | List signals for a sender |
| `GET` | `/v1/signals/{id}` | Poll signal status + progress |
| `GET` | `/v1/signals/external/{external_id}` | Lookup by your message ID |
| `GET` | `/v1/logs` | Activity audit log for a sender |
| `GET` | `/v1/positions` | Live MT5 positions for a sender |
| `POST` | `/v1/positions/{ticket}/close` | Close one position |
| `POST` | `/v1/positions/close-all` | Close all sender positions |
| `GET` | `/health` | Health check |

All provider endpoints require `X-Provider-Key`. Sender-scoped routes require `?sendername=`.

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
| `order_type` | string | no | `market` / `open` = execute at **current price**; `limit` = pending at `entry`; `stop` = stop order at `entry`. Hub normalizes messy labels (e.g. `limit (or market / stop)` → `limit`) |
| `entry` | number or string | limit/stop | Limit/stop price or range (`5160 - 5170` uses midpoint). **Omit for `market`/`open`** — Quantum uses live bid/ask |
| `sl` | number | no | Stop loss; Quantum auto-builds 2R if omitted (trusted path) |
| `tp` | number | no | Take profit |
| `image_url` | string | no | HTTPS URL to a chart/screenshot — forwarded to your Telegram alert with the signal |
| `image_base64` | string | no | Base64-encoded image (or `data:image/png;base64,...`) — alternative to `image_url` |
| `image_mime` | string | no | `image/jpeg`, `image/png`, `image/webp` (default `image/jpeg` when using base64) |
| `lot` | number | no | Fixed lot (optional; Quantum sizes from risk % if omitted) |
| `lot_scale` | number | no | Scale for add/partial (0.01–10) |
| `ticket` | integer | no | MT5 ticket for modify/close when symbol ambiguous |
| `message` | string | no | Raw text for logs |
| `provider_name` | string | no | Display name in Quantum logs (e.g. `Alpha Signals`) |
| `sendername` | string | no | Name or username of the user who posted the signal — appears in the MT5 order comment (max 64 chars, truncated to 31 in MT5) |
| `callback_url` | string | no | HTTPS URL — hub POSTs a JSON webhook when the signal reaches `done` or `failed` |
| `confidence` | number | no | 0–100 (default 100 for trusted execution) |

### Execution style: OPEN vs LIMIT

| `order_type` | Meaning | `entry` | Quantum behavior |
|--------------|---------|---------|------------------|
| `open` or `market` | Open now at live price | omit | **MARKET** at current bid/ask |
| `limit` | Pending limit from your signal | **required** | **LIMIT** at `entry` |
| `stop` | Stop order from your signal | **required** | **STOP** at `entry` |

When a chart image is included (`image_url` or `image_base64`), Quantum sends a **Telegram photo** with the signal caption (SL/TP, sender, message).

### Example — OPEN at market with chart image

```json
{
  "external_id": "post-8843",
  "action": "open",
  "symbol": "XAUUSD",
  "direction": "buy",
  "order_type": "open",
  "sl": 2640.0,
  "tp": 2680.0,
  "sendername": "willerfx",
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "image_mime": "image/png"
}
```

### Example — LIMIT at your entry with image URL

```json
{
  "external_id": "post-8844",
  "action": "open",
  "symbol": "XAUUSD",
  "direction": "sell",
  "order_type": "limit",
  "entry": 2685.0,
  "sl": 2695.0,
  "tp": 2665.0,
  "sendername": "willerfx",
  "image_url": "https://your-cdn.com/charts/gold-setup.png"
}
```

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
  "provider_name": "My Signal Platform",
  "sendername": "willerfx"
}
```

When `sendername` is set, Quantum writes `QTE {sendername}` on the MT5 order comment (max 31 characters). Without it, hub trades use `QTE hub`.

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
    "provider_name": "My Platform",
    "sendername": "willerfx"
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
    sendername: "willerfx",
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
        "sendername": "willerfx",
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

## Track signal progress (provider)

After submitting a signal, poll status or use an optional webhook. **Senders only see their own signals** — list and lookup endpoints require `sendername` matching the value you sent on POST.

### Status lifecycle

| `status` | Meaning |
|----------|---------|
| `pending` | Queued — waiting for Quantum to poll |
| `processing` | Quantum picked it up and is executing on MT5 |
| `done` | Finished (check `progress.executed` and `result.log_action`) |
| `failed` | Could not execute — see `result.error` |

Every status response includes a **`progress`** object:

```json
{
  "stage": "executed",
  "message": "Trade executed on MT5",
  "executed": true
}
```

`stage` values: `queued`, `processing`, `executed`, `failed`, `skipped`, `done`

### Option A — Poll by signal ID

Save `id` from the POST response, then poll every 2–5 seconds until `status` is `done` or `failed`:

```bash
curl "https://your-hub.onrender.com/v1/signals/SIGNAL_UUID?sendername=willerfx" \
  -H "X-Provider-Key: YOUR_PROVIDER_KEY"
```

Pass **`sendername`** so users cannot read each other's signals (returns 404 if the signal belongs to another sender).

### Option B — Poll by your `external_id`

If you use `external_id` on POST:

```bash
curl "https://your-hub.onrender.com/v1/signals/external/post-8842?sendername=willerfx" \
  -H "X-Provider-Key: YOUR_PROVIDER_KEY"
```

### Option C — List a sender's recent signals

```bash
curl "https://your-hub.onrender.com/v1/signals?sendername=willerfx&status=done&limit=20" \
  -H "X-Provider-Key: YOUR_PROVIDER_KEY"
```

Query parameters:

| Param | Required | Description |
|-------|----------|-------------|
| `sendername` | **yes** | Only signals posted by this user |
| `status` | no | Filter: `pending`, `processing`, `done`, `failed` |
| `external_id` | no | Filter to one platform message ID |
| `limit` | no | 1–100 (default 50) |
| `offset` | no | Pagination offset |
| `since` | no | ISO datetime — only signals after this time |

Response:

```json
{
  "sendername": "willerfx",
  "count": 1,
  "items": [
    {
      "id": "uuid",
      "external_id": "post-8842",
      "status": "done",
      "progress": {
        "stage": "executed",
        "message": "Trade executed on MT5",
        "executed": true
      },
      "payload": { "symbol": "XAUUSD", "sendername": "willerfx", "...": "..." },
      "result": {
        "setup_id": "abc123",
        "log_action": "executed",
        "error": null
      },
      "created_at": "2026-06-21T12:00:00Z",
      "acked_at": "2026-06-21T12:00:05Z"
    }
  ]
}
```

### Option D — Webhook (push)

Include `callback_url` when posting a signal. When Quantum finishes, the hub POSTs once to your URL:

```json
{
  "external_id": "post-8842",
  "action": "open",
  "symbol": "XAUUSD",
  "direction": "buy",
  "sendername": "willerfx",
  "callback_url": "https://myapp.com/api/signalhub/webhook"
}
```

Webhook body (your server receives):

```json
{
  "event": "signal.done",
  "id": "uuid",
  "external_id": "post-8842",
  "status": "done",
  "sendername": "willerfx",
  "action": "open",
  "symbol": "XAUUSD",
  "direction": "buy",
  "progress": {
    "stage": "executed",
    "message": "Trade executed on MT5",
    "executed": true
  },
  "result": {
    "setup_id": "abc123",
    "log_action": "executed",
    "error": null
  },
  "created_at": "2026-06-21T12:00:00.000Z",
  "acked_at": "2026-06-21T12:00:05.000Z"
}
```

Events: `signal.done` or `signal.failed`. Delivery is best-effort (no retries). Use polling as a fallback.

### Option E — Activity log (audit trail)

Full event history for one sender (POST, poll pickup, execution, webhook):

```bash
curl "https://your-hub.onrender.com/v1/logs?sendername=willerfx&limit=50" \
  -H "X-Provider-Key: YOUR_PROVIDER_KEY"
```

Optional filter: `&signal_id=UUID`

Response:

```json
{
  "sendername": "willerfx",
  "count": 3,
  "items": [
    {
      "id": "event-uuid",
      "signal_id": "signal-uuid",
      "sendername": "willerfx",
      "event": "created",
      "message": "Signal queued: open XAUUSD by willerfx",
      "detail": { "action": "open", "symbol": "XAUUSD" },
      "created_at": "2026-06-21T12:00:00Z"
    },
    {
      "event": "processing",
      "message": "Quantum picked up: open XAUUSD",
      "created_at": "2026-06-21T12:00:02Z"
    },
    {
      "event": "executed",
      "message": "Completed: executed",
      "created_at": "2026-06-21T12:00:05Z"
    }
  ]
}
```

Event types: `created`, `duplicate`, `processing`, `executed`, `failed`, `webhook_sent`, `webhook_failed`

Only events for the requested `sendername` are returned — senders cannot see each other's activity.

### JavaScript — poll until executed

```javascript
async function waitForSignal(signalId, sendername) {
  for (let i = 0; i < 60; i++) {
    const res = await fetch(
      `https://your-hub.onrender.com/v1/signals/${signalId}?sendername=${encodeURIComponent(sendername)}`,
      { headers: { "X-Provider-Key": process.env.SIGNAL_HUB_PROVIDER_KEY } },
    );
    const data = await res.json();
    if (data.status === "done" || data.status === "failed") {
      return data;
    }
    await new Promise((r) => setTimeout(r, 3000));
  }
  throw new Error("timeout waiting for signal");
}
```

---

## GET /v1/signals/{id}

Check signal status. Auth: `X-Provider-Key` or `X-Consumer-Key`.

Providers should pass **`?sendername=`** so each user only sees their own trades.

```bash
curl "https://your-hub.onrender.com/v1/signals/SIGNAL_UUID?sendername=willerfx" \
  -H "X-Provider-Key: YOUR_PROVIDER_KEY"
```

Response:

```json
{
  "id": "uuid",
  "external_id": "post-8842",
  "status": "done",
  "progress": {
    "stage": "executed",
    "message": "Trade executed on MT5",
    "executed": true
  },
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

## Live market quote

Get the **current bid/ask/mid** from your MT5 terminal via Quantum. Requires `QUANTUM_BRIDGE_URL` on Signal Hub.

### GET /v1/quote?symbol=XAUUSD

```bash
curl "https://your-hub.onrender.com/v1/quote?symbol=XAUUSD" \
  -H "X-Provider-Key: YOUR_PROVIDER_KEY"
```

### POST /v1/quote

```bash
curl -X POST "https://your-hub.onrender.com/v1/quote" \
  -H "X-Provider-Key: YOUR_PROVIDER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "GOLD"}'
```

Response:

```json
{
  "symbol": "GOLD",
  "resolved_symbol": "XAUUSD",
  "bid": 2650.10,
  "ask": 2650.30,
  "price": 2650.20,
  "mid": 2650.20,
  "spread": 0.20,
  "digits": 2,
  "point": 0.01,
  "time": "2026-06-25T14:30:00Z",
  "source": "mt5"
}
```

Alias codes like `GOLD`, `VIX75`, `BOOM1000` are resolved to broker symbol names automatically.

---

## Sender performance report

Rank signal senders by **net P/L (profitability)**, win rate, signal volume, or profit factor. Closed trades are matched via:

- MT5 order comment `QTE {sendername}` (Telegram / manual sources)
- Hub setup metadata `hub_sendername` on linked setups

### GET /v1/senders/report

Full leaderboard with optional filters and sort.

| Query | Default | Description |
|-------|---------|-------------|
| `days` | `90` | Lookback window (7–365) |
| `sort` | `profit` | `profit` · `win_rate` · `signals` · `profit_factor` · `expectancy` |
| `min_closed_trades` | `0` | Hide senders with fewer closed trades |
| `limit` | `50` | Max rows returned (1–200) |

```bash
curl "https://your-hub.onrender.com/v1/senders/report?days=90&sort=profit&min_closed_trades=1" \
  -H "X-Provider-Key: YOUR_PROVIDER_KEY"
```

### GET /v1/senders/profitability

Convenience endpoint: **only senders with ≥1 closed trade**, sorted by net profit. **Rank 1 = most profitable.**

| Query | Default | Description |
|-------|---------|-------------|
| `days` | `90` | Lookback window (7–365) |
| `min_closed_trades` | `1` | Minimum closed trades to appear |
| `limit` | `50` | Max rows (1–200) |

```bash
curl "https://your-hub.onrender.com/v1/senders/profitability?days=90" \
  -H "X-Provider-Key: YOUR_PROVIDER_KEY"
```

**Response** (both endpoints):

```json
{
  "days": 90,
  "sort": "profit",
  "min_closed_trades": 1,
  "total_senders": 5,
  "returned": 5,
  "generated_at": "2026-06-27T21:00:00Z",
  "summary": {
    "total_profit": 412.35,
    "total_closed_trades": 38,
    "profitable_senders": 3,
    "unprofitable_senders": 2
  },
  "senders": [
    {
      "rank": 1,
      "sender": "willer_Fx",
      "signals": 42,
      "executed": 28,
      "skipped": 14,
      "failed": 0,
      "closed_trades": 25,
      "wins": 16,
      "losses": 9,
      "profit": 340.5,
      "win_rate": 64.0,
      "profit_factor": 1.85,
      "expectancy": 13.62,
      "profitable": true
    },
    {
      "rank": 2,
      "sender": "alice",
      "signals": 10,
      "executed": 8,
      "skipped": 2,
      "failed": 0,
      "closed_trades": 8,
      "wins": 3,
      "losses": 5,
      "profit": -120.0,
      "win_rate": 37.5,
      "profit_factor": 0.42,
      "expectancy": -15.0,
      "profitable": false
    }
  ]
}
```

| Field | Meaning |
|-------|---------|
| `rank` | Position in the sorted list (1 = best for chosen sort) |
| `profit` | Net closed-trade P/L ($) |
| `profit_factor` | Gross wins ÷ gross losses |
| `expectancy` | Average $ per closed trade |
| `profitable` | `true` when `profit > 0` and `closed_trades > 0` |

**Direct Quantum API** (same JSON, dashboard auth or hub consumer key on `/v1/hub/*`):

```bash
# Dashboard session / API auth
curl "http://your-vps:8090/api/signal-hub/senders/profitability?days=90"

# Hub bridge (Signal Hub → Quantum)
curl "http://your-vps:8090/v1/hub/senders/profitability?days=90" \
  -H "X-Consumer-Key: YOUR_CONSUMER_KEY"
```

Skipped/passed signals are logged in Quantum but **not** sent to Telegram by default.

---

## Sender positions (live MT5)

Senders can view and close **only their own** open trades. Positions are matched by MT5 order comment `QTE {sendername}` (set when you POST with `sendername`).

Requires `QUANTUM_BRIDGE_URL` on Signal Hub pointing at your Quantum VPS (same host as MT5, port `8090`). Hub calls Quantum with `X-Consumer-Key`.

### GET /v1/positions

List open positions for one sender.

```bash
curl "https://your-hub.onrender.com/v1/positions?sendername=willerfx" \
  -H "X-Provider-Key: YOUR_PROVIDER_KEY"
```

Response:

```json
{
  "sendername": "willerfx",
  "count": 1,
  "items": [
    {
      "ticket": 12345678,
      "symbol": "XAUUSD",
      "direction": "buy",
      "lot": 0.1,
      "entry": 2650.5,
      "sl": 2640.0,
      "tp": 2680.0,
      "profit": 12.5,
      "price": 2651.2,
      "comment": "QTE willerfx",
      "opened_at": "2026-06-21T14:00:00+00:00",
      "sendername": "willerfx"
    }
  ]
}
```

### POST /v1/positions/{ticket}/close

Close one position by MT5 ticket (must belong to sender).

```bash
curl -X POST "https://your-hub.onrender.com/v1/positions/12345678/close?sendername=willerfx" \
  -H "X-Provider-Key: YOUR_PROVIDER_KEY"
```

Response:

```json
{
  "ok": true,
  "ticket": 12345678,
  "symbol": "XAUUSD",
  "profit": 12.5,
  "sendername": "willerfx"
}
```

### POST /v1/positions/close-all

Close every open position for this sender.

```bash
curl -X POST "https://your-hub.onrender.com/v1/positions/close-all?sendername=willerfx" \
  -H "X-Provider-Key: YOUR_PROVIDER_KEY"
```

Response:

```json
{
  "ok": true,
  "closed": 2,
  "count": 2,
  "sendername": "willerfx",
  "items": [
    { "ticket": 12345678, "symbol": "XAUUSD", "profit": 12.5, "ok": true },
    { "ticket": 12345679, "symbol": "EURUSD", "profit": -3.2, "ok": true }
  ]
}
```

### Alternative — close via signal queue

You can also POST a signal (async, polled by Quantum):

```json
{
  "action": "close",
  "symbol": "XAUUSD",
  "ticket": 12345678,
  "sendername": "willerfx"
}
```

Or close all for sender only:

```json
{
  "action": "close_all",
  "sendername": "willerfx"
}
```

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
   - `QUANTUM_BRIDGE_URL= http://your-quantum-vps:8090` (for live positions API — VPS must be reachable from Render)
4. Copy service URL into Quantum → Settings → **Signal Hub URL** + consumer key.

## Quantum setup

1. Dashboard → Settings → enable **Signal Hub listener**
2. Set **Signal Hub URL** = `https://your-hub.onrender.com`
3. Set **Signal Hub consumer key** = same as `CONSUMER_KEY`
4. Expose Quantum on port **8090** (or tunnel) so Render can reach `QUANTUM_BRIDGE_URL`
5. Ensure operating mode is **Auto trade** and MT5 is connected
6. Trusted direct execution applies (risk limits only, no MTF gate)

Signals poll every 5 seconds by default (`signal_hub_poll_seconds`).
