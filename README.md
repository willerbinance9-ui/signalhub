# AARE Signal Hub

Lightweight API for ingesting trading signals from third-party apps. Deploy on **Render**; **AARE Quantum** on your MT5 VPS polls and executes (trusted direct path).

## Features

- **POST /v1/signals** — submit trades (open, close, modify, breakeven, etc.)
- **sendername** — tags MT5 order comment + scopes all sender data
- **Progress tracking** — poll status, activity logs, optional webhooks
- **Live positions** — list/close positions per sender (`GET/POST /v1/positions`)

Full reference: **[docs/API.md](docs/API.md)** · Interactive: `/docs`

## Quick start (local)

```bash
cd aare_signal_hub
pip install -r requirements.txt
set PROVIDER_KEYS=test-provider-key
set CONSUMER_KEY=test-consumer-key
set DATABASE_URL=sqlite:///./signal_hub.db
set QUANTUM_BRIDGE_URL=http://localhost:8090
uvicorn app.main:app --port 8100
```

## Render

1. New Web Service → connect repo → root directory empty or `aare_signal_hub`
2. Add Postgres; link `DATABASE_URL`
3. Set env vars:
   - `PROVIDER_KEYS` — your app keys
   - `CONSUMER_KEY` — Quantum poll key
   - `QUANTUM_BRIDGE_URL` — Quantum VPS URL for positions API
4. Deploy via `render.yaml` or Dockerfile

## Quantum

Dashboard → Settings → enable **Signal Hub listener**, paste hub URL + consumer key.

Quantum must run with MT5 connected. For position API, set `QUANTUM_BRIDGE_URL` on Render to your Quantum host (`http://vps-ip:8090`).
