import os

os.environ.setdefault("PHONE_NUMBER_ID", "123456")
os.environ.setdefault("ACCESS_TOKEN", "test-token")
os.environ.setdefault("VERIFY_TOKEN", "test-verify")
os.environ.setdefault("APP_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.database import Base
from app.core.whatsapp_client import WhatsAppClient
from app.main import app

test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

import app.api.dependencies as _deps_mod  # noqa: E402
import app.api.v1.endpoints.webhooks as _wh_mod  # noqa: E402
import app.core.database as _db_mod  # noqa: E402

_db_mod.engine = test_engine
_db_mod.AsyncSessionLocal = TestSessionLocal
_deps_mod.AsyncSessionLocal = TestSessionLocal
_wh_mod.AsyncSessionLocal = TestSessionLocal


async def _override_init_db() -> None:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


_db_mod.init_db = _override_init_db


TEST_SETTINGS = Settings(
    PHONE_NUMBER_ID="123456",
    ACCESS_TOKEN="test-token",
    VERIFY_TOKEN="test-verify",
    APP_SECRET="test-secret",
    DATABASE_URL="sqlite+aiosqlite:///:memory:",
    DEBUG=False,
)


@pytest_asyncio.fixture(autouse=True)
async def _create_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest_asyncio.fixture
async def session():
    async with TestSessionLocal() as s:
        yield s


@pytest_asyncio.fixture
async def whatsapp():
    wa = WhatsAppClient(TEST_SETTINGS.PHONE_NUMBER_ID, TEST_SETTINGS.ACCESS_TOKEN)
    await wa.start()
    yield wa
    await wa.close()


@pytest_asyncio.fixture
async def client(whatsapp):
    from app.api.dependencies import get_db, get_send_service, get_settings

    async def _override_db():
        async with TestSessionLocal() as s:
            yield s

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    app.dependency_overrides[get_send_service] = lambda: _SendServiceStub(whatsapp)

    app.state.whatsapp = whatsapp

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


class _SendServiceStub:
    def __init__(self, wa: WhatsAppClient) -> None:
        from app.services.send_service import SendService

        self._svc = SendService(wa)

    async def send_and_persist(self, db, to_wa_id, body):
        return await self._svc.send_and_persist(db, to_wa_id, body)
