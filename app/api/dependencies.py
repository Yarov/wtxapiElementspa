# ruff: noqa: B008  - FastAPI Depends() in argument defaults is the documented idiom
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.config import get_settings as _get_settings
from app.core.database import AsyncSessionLocal
from app.core.whatsapp_client import WhatsAppClient
from app.services.send_service import SendService

basic_auth = HTTPBasic(auto_error=False)


def get_settings() -> Settings:
    return _get_settings()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


def get_send_service(request: Request) -> SendService:
    wa: WhatsAppClient = request.app.state.whatsapp
    return SendService(wa)


def require_admin(
    credentials: HTTPBasicCredentials | None = Depends(basic_auth),
    settings: Settings = Depends(get_settings),
) -> None:
    valid = (
        credentials is not None
        and secrets.compare_digest(credentials.username, settings.ADMIN_USERNAME)
        and secrets.compare_digest(credentials.password, settings.ADMIN_PASSWORD)
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
