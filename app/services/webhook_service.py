from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository
from app.schemas.webhook import WebhookPayload, WebhookStatus


async def handle_inbound(payload: WebhookPayload, db: AsyncSession) -> None:
    conv_repo = ConversationRepository()
    msg_repo = MessageRepository()
    now = datetime.now(UTC)

    for entry in payload.entry:
        for change in entry.changes:
            if change.field != "messages":
                continue
            value = change.value
            profile_name = value.contacts[0].profile.name if value.contacts else None
            if value.messages:
                for msg in value.messages:
                    if await msg_repo.get_by_wamid(db, msg.id):
                        continue
                    wa_id = msg.from_
                    body = msg.text.body if msg.text and msg.type == "text" else ""
                    conv = await conv_repo.upsert_by_wa_id(
                        db,
                        wa_id=wa_id,
                        name=profile_name,
                        last_message_at=now,
                    )
                    await msg_repo.create(
                        db,
                        {
                            "wamid": msg.id,
                            "conversation_id": conv.id,
                            "direction": "inbound",
                            "body": body,
                            "status": "received",
                            "created_at": now,
                        },
                    )
            if value.statuses:
                await apply_statuses(value.statuses, db)
            await db.commit()


async def apply_statuses(statuses: list[WebhookStatus], db: AsyncSession) -> None:
    msg_repo = MessageRepository()
    for status in statuses:
        msg = await msg_repo.get_by_wamid(db, status.id)
        if msg is None:
            continue
        msg.status = status.status
        await db.flush()
