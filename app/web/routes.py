# ruff: noqa: B008  - FastAPI Depends() in argument defaults is the documented idiom
import os

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_send_service
from app.core.whatsapp_client import WhatsAppAPIError
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.send_service import SendService

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    rows = (
        (await db.execute(select(Conversation).order_by(Conversation.last_message_at.desc())))
        .scalars()
        .all()
    )
    return templates.TemplateResponse(request, "index.html", {"conversations": rows})


@router.get("/c/{conversation_id}", response_class=HTMLResponse)
async def conversation(
    request: Request,
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    conv = (
        await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    ).scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404)
    msgs = (
        (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return templates.TemplateResponse(
        request,
        "conversation.html",
        {"conversation": conv, "messages": msgs},
    )


@router.post("/c/{conversation_id}/send")
async def send_in_conversation(
    conversation_id: int,
    body: str = Form(...),
    db: AsyncSession = Depends(get_db),
    svc: SendService = Depends(get_send_service),
) -> RedirectResponse:
    conv = (
        await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    ).scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404)
    try:
        await svc.send_and_persist(db, conv.wa_id, body)
    except WhatsAppAPIError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return RedirectResponse(url=f"/c/{conversation_id}", status_code=303)
