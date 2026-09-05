# ruff: noqa: B008  - FastAPI Depends() in argument defaults is the documented idiom
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_settings
from app.core.config import Settings
from app.core.security import verify_signature
from app.schemas.webhook import WebhookPayload
from app.services.webhook_service import handle_inbound

router = APIRouter()


@router.get("")
async def verify(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    settings: Settings = Depends(get_settings),
) -> Response:
    if hub_mode == "subscribe" and hub_verify_token == settings.VERIFY_TOKEN:
        return Response(content=hub_challenge or "", media_type="text/plain")
    raise HTTPException(status_code=403, detail="Forbidden")


@router.post("")
async def receive(
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    raw = await request.body()
    if not verify_signature(raw, request.headers.get("X-Hub-Signature-256"), settings.APP_SECRET):
        raise HTTPException(status_code=401, detail="Invalid signature")
    payload = WebhookPayload.model_validate_json(raw)
    await handle_inbound(payload, db)
    return {"status": "ok"}
