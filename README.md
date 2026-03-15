# Pixflix

PIX-powered interactive terminal tooling for arcades.

## Goal

Build a terminal flow where a customer pays (for example R$1 via PIX) and then earns one interaction, starting with selecting a song to play on the arcade sound system.

## MVP status

Implemented backend MVP skeleton:

- FastAPI service with payment, webhook, kiosk, and queue endpoints
- SQLite persistence for payments, credits, webhook events, and music queue
- Webhook token check and idempotent payment confirmation
- Simulated payment confirmation endpoint for local development
- Tests covering PIX -> credit -> music queue flow

## Tech baseline

- Python `3.12`
- Build backend: `hatchling`
- Test runner: `pytest`
- Linter: `ruff`
- API framework: `FastAPI`

## Quickstart

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
pytest
ruff check .
uvicorn pixflix.app:app --reload
```

## Run with Docker

```bash
# Build and run API in container (with persistent SQLite volume)
docker compose up --build
```

App URL:

```bash
http://127.0.0.1:8000
```

Useful commands:

```bash
# Stop container
docker compose down

# Stop and remove DB volume
docker compose down -v
```

## Local API flow (simulation)

1. Create payment:
```bash
'{"session_id":"terminal-1","amount_cents":100}' | Out-File -Encoding ascii body.json
curl.exe -X POST "http://127.0.0.1:8000/payments/create" -H "Content-Type: application/json" --data-binary "@body.json"
```
2. Simulate PIX confirmation:
```bash
$payment = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/payments/create" -ContentType "application/json" -Body '{"session_id":"terminal-1","amount_cents":100}'
$paymentId = $payment.payment_id
$paymentId

curl.exe -X POST "http://127.0.0.1:8000/payments/$paymentId/simulate-paid"
```
3. Request a song:
```bash
'{"session_id":"terminal-1","song_id":"song-001","title":"Neon Nights"}' | Out-File -Encoding ascii music.json
curl.exe -X POST "http://127.0.0.1:8000/music/request" -H "Content-Type: application/json" --data-binary "@music.json"
```
4. Check queue:
```bash
curl.exe "http://127.0.0.1:8000/player/queue"
```

## Important endpoints

- `POST /payments/create`
- `POST /payments/{payment_id}/simulate-paid`
- `POST /webhooks/pix` (header `x-pixflix-webhook-token`)
- `POST /music/request`
- `GET /kiosk/{session_id}/status`
- `GET /player/queue`

## Environment variables

- `PIXFLIX_WEBHOOK_TOKEN` default: `local-dev-token`
- `PIXFLIX_DEFAULT_AMOUNT_CENTS` default: `100`
- `PIXFLIX_DB_PATH` default: `pixflix.db`
- `PIXFLIX_DATABASE_URL` default: `sqlite:///pixflix.db`
- `PIXFLIX_PIX_PROVIDER` default: `mock` (`mock` or `efi_sandbox`)

Webhook payloads accepted by `POST /webhooks/pix`:

- Generic/internal:
  - `{"event_id":"evt-1","payment_id":"pix_xxx","status":"paid"}`
- Efí-sandbox style:
  - `{"id":"evt-1","pix":[{"txid":"pix_xxx"}]}`

## Database migrations

```bash
# apply latest schema
alembic upgrade head

# create a new migration
alembic revision -m "describe change"
```

Production URL example:

```bash
PIXFLIX_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/pixflix
```

## Next milestones

1. Integrate a real PIX provider.
2. Add database migrations and move to PostgreSQL for production.
3. Add kiosk frontend screen flow.
4. Integrate local audio player controls.
5. Add admin dashboard, retries, and observability.
