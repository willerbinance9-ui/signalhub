# AARE Signal Hub

Lightweight API for ingesting trading signals from third-party apps. Deploy on **Render**; **AARE Quantum** on your MT5 VPS polls and executes (trusted direct path).

## Quick start (local)

```bash
cd aare_signal_hub
pip install -r requirements.txt
set PROVIDER_KEYS=test-provider-key
set CONSUMER_KEY=test-consumer-key
set DATABASE_URL=sqlite:///./signal_hub.db
uvicorn app.main:app --port 8100
```

Docs: http://localhost:8100/docs

Full API reference: [docs/API.md](docs/API.md)

## Render

1. New Web Service → connect repo → root directory `aare_signal_hub`
2. Add Postgres; link `DATABASE_URL`
3. Set `PROVIDER_KEYS` and `CONSUMER_KEY`
4. Deploy via `render.yaml` or Dockerfile

## Quantum

Dashboard → Settings → enable **Signal Hub listener**, paste URL + consumer key.
