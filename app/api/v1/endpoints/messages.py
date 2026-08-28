# ruff: noqa: B008  - FastAPI Depends() in argument defaults is the documented idiom
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_send_service
from app.core.whatsapp_client import WhatsAppAPIError
from app.schemas.message import SendMessageRequest, SendMessageResponse
from app.services.send_service import SendService

router = APIRouter()


@router.post("", response_model=SendMessageResponse)
async def send(
    body: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    svc: SendService = Depends(get_send_service),
) -> SendMessageResponse:
    try:
        wamid = await svc.send_and_persist(db, body.to, body.body)
    except WhatsAppAPIError as e:
        raise HTTPException(status_code=502, detail=f"Cloud API error: {e}") from e
    return SendMessageResponse(wamid=wamid, status="sent")
