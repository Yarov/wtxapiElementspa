from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.whatsapp_client import WhatsAppClient
from app.repositories.conversation import ConversationRepository
from app.repositories.message import MessageRepository


class SendService:
    def __init__(self, wa: WhatsAppClient) -> None:
        self.wa = wa

    async def send_and_persist(self, db: AsyncSession, to_wa_id: str, body: str) -> str:
        wamid = await self.wa.send_text(to_wa_id, body)
        conv_repo = ConversationRepository()
        msg_repo = MessageRepository()
        conv = await conv_repo.upsert_by_wa_id(
            db,
            wa_id=to_wa_id,
            last_message_at=datetime.now(UTC),
        )
        await msg_repo.create(
            db,
            {
                "wamid": wamid,
                "conversation_id": conv.id,
                "direction": "outbound",
                "body": body,
                "status": "sent",
                "created_at": datetime.now(UTC),
            },
        )
        await db.commit()
        return wamid
