from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.config import get_settings as _get_settings
from app.core.database import AsyncSessionLocal
from app.core.whatsapp_client import WhatsAppClient
from app.services.send_service import SendService


def get_settings() -> Settings:
    return _get_settings()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


def get_send_service(request: Request) -> SendService:
    wa: WhatsAppClient = request.app.state.whatsapp
    return SendService(wa)
