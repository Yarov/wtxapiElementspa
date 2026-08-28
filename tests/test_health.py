"""Health endpoint tests — covers spec §5 (DB-probing healthcheck)."""

from unittest.mock import AsyncMock, MagicMock

from app.api.dependencies import get_db
from app.main import app


async def test_health_ok_when_db_reachable(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_health_returns_503_when_db_unreachable(client):
    fake_session = MagicMock()
    fake_session.execute = AsyncMock(side_effect=RuntimeError("simulated DB outage"))

    async def _override():
        yield fake_session

    app.dependency_overrides[get_db] = _override
    try:
        r = await client.get("/api/v1/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert r.status_code == 503
    body = r.json()
    assert body["error"]["code"] == "service_unavailable"
    assert "database unreachable" in body["error"]["message"].lower()
