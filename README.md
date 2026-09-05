# WhatsApp Webhook App

FastAPI service that receives Meta WhatsApp Cloud API webhooks, persists text
messages, and ships a server-rendered Jinja dashboard for browsing conversations
and sending replies through the Cloud API.

## Architecture

Single Python process (FastAPI + uvicorn). SQLite in WAL mode for persistence,
Jinja2 + htmx for the dashboard (no JS build step). One async `httpx` client is
shared across the app for outbound requests to the Cloud API.

```
Meta webhook ──► /api/v1/webhook (verify + HMAC) ──► SQLite
Dashboard   ──► /api/v1/messages (POST)           ──► graph.facebook.com
```

Inbound messages are committed before the webhook returns `200`, preventing
message loss during a restart or deployment.

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

Local runs create SQLite at `./app.db`; Docker deployments override this to
`/app/data/app.db` so the database lives in the persistent volume.
The dashboard and outbound API use HTTP Basic authentication configured with
`ADMIN_USERNAME` and `ADMIN_PASSWORD`.

## Run tests

```bash
pytest -v
```

> Tip: the system `python` may be 3.9 which can't import `UTC` from `datetime`.
> Use your venv interpreter explicitly: `.venv/bin/pytest`.

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

## Deploy on Coolify

1. Create a **Docker Compose** resource from this Git repository.
2. Use the default compose file `/docker-compose.yaml`.
3. Set these environment variables in Coolify:
   - `PHONE_NUMBER_ID`
   - `ACCESS_TOKEN`
   - `VERIFY_TOKEN`
   - `APP_SECRET`
   - `ADMIN_USERNAME`
   - `ADMIN_PASSWORD`
4. Assign `https://wtxapi.elementspa.mx:8000` to the `app` service. The `:8000`
   tells Coolify which internal container port to proxy; the public URL remains
   standard HTTPS.
5. Keep one replica and one Uvicorn process because SQLite is used.
6. Deploy and set `/api/v1/health` as the healthcheck path.

The Coolify compose file declares a persistent named volume at `/app/data` and
forces `DATABASE_URL=sqlite+aiosqlite:////app/data/app.db`. Back up the complete
volume because SQLite WAL mode also creates `app.db-wal` and `app.db-shm`.

After deployment, verify:

```bash
curl https://wtxapi.elementspa.mx/api/v1/health
# {"status":"ok"}
```

Use `https://wtxapi.elementspa.mx/api/v1/webhook` as the callback URL in Meta.

For local Docker development, use the compose file that publishes port 8000:

```bash
docker compose -f docker-compose.local.yml up -d --build
```

## Notes

The webhook and healthcheck are public. The dashboard and outbound-message API
require Basic Auth. API documentation is disabled when `DEBUG=false`. All env
vars are listed in `.env.example`; never commit `.env` or Meta credentials.
