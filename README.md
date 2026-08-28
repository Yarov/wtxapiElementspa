# WhatsApp Webhook App

FastAPI service that receives Meta WhatsApp Cloud API webhooks, persists text
messages, and ships a server-rendered Jinja dashboard for browsing conversations
and sending replies through the Cloud API.

## Architecture

Single Python process (FastAPI + uvicorn). SQLite in WAL mode for persistence,
Jinja2 + htmx for the dashboard (no JS build step). One async `httpx` client is
shared across the app for outbound requests to the Cloud API.

```
Meta webhook ──► /api/v1/webhook (verify + HMAC) ──► BackgroundTasks ──► SQLite
Dashboard   ──► /api/v1/messages (POST)              ──► graph.facebook.com
```

Inbound acknowledgements return within ~500 ms; persistence and outbound calls
happen off the request hot path.

## Prerequisites

- Python 3.12+
- A Meta Business account with a WhatsApp Business Account (WABA) and a phone
  number ID
- A permanent system-user access token with `whatsapp_business_management` and
  `whatsapp_business_messaging` permissions
- The Meta app's **App Secret** (used to validate `X-Hub-Signature-256`)

## Local setup

```bash
cp .env.example .env          # then fill in real values
pip install -e .[dev]
uvicorn app.main:app --reload
```

The SQLite file is created at `./app.db` on first start.

## Run tests

```bash
pytest -v
```

## Meta webhook setup

1. **App Dashboard → Webhooks → Edit**:
   - Callback URL: `https://<your-domain>/api/v1/webhook`
   - Verify Token: the value of `VERIFY_TOKEN` in your `.env`
2. Subscribe to webhook fields:
   - `messages` (required)
   - `message_template_status_update` (optional, for delivery updates)
3. **App Settings → Basic → App Secret**: copy into `.env` as `APP_SECRET`.

The POST handler validates the `X-Hub-Signature-256` header against the raw
request bytes — payloads with invalid or missing signatures are rejected with
`401`.

## Cloud API send

Set `ACCESS_TOKEN` to a system-user token with the two WhatsApp permissions
listed above. The dashboard "Send" form posts to `/api/v1/messages`, which
calls `POST https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages` and
records the outbound message in SQLite on a 2xx response.

## Deploy on Railway

1. Link the repository in Railway.
2. Set the same env vars from `.env.example` in the Railway dashboard.
3. Deploy — `railway.json` configures the Dockerfile build and
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT` as the start command.

The project ships with a multi-stage-ready `Dockerfile` (Python 3.12-slim) and
`railway.json`; the SQLite file lives on the container's ephemeral filesystem,
so a Railway volume is required if persistence across restarts/deploys matters
(not needed for v1 testing).

## Notes

The dashboard has no authentication. Protect it at the network layer
(Railway private networking, Tailscale, or basic auth on a reverse proxy).
All env vars are listed in `.env.example`.
