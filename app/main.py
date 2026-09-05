import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import init_db
from app.core.errors import install_error_handlers
from app.core.whatsapp_client import build_client
from app.web.routes import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    settings = get_settings()
    wa = build_client(settings)
    await wa.start()
    app.state.whatsapp = wa
    await init_db()
    try:
        yield
    finally:
        await wa.close()


settings = get_settings()
app = FastAPI(
    title="WhatsApp Inbox",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)
install_error_handlers(app)
app.include_router(api_router, prefix="/api/v1")
app.include_router(web_router)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
