from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation, dict, dict]):
    def __init__(self) -> None:
        super().__init__(Conversation)

    async def get_by_wa_id(
        self,
        db: AsyncSession,
        wa_id: str,
    ) -> Conversation | None:
        result = await db.execute(select(Conversation).where(Conversation.wa_id == wa_id))
        return result.scalars().first()

    async def upsert_by_wa_id(
        self,
        db: AsyncSession,
        wa_id: str,
        name: str | None = None,
        last_message_at: datetime | None = None,
    ) -> Conversation:
        conversation = await self.get_by_wa_id(db, wa_id)
        if conversation is None:
            conversation = Conversation(
                wa_id=wa_id,
                name=name,
                last_message_at=last_message_at or datetime.utcnow(),
            )
            db.add(conversation)
            await db.flush()
            await db.refresh(conversation)
            return conversation

        changed = False
        if name and conversation.name != name:
            conversation.name = name
            changed = True
        if last_message_at and conversation.last_message_at != last_message_at:
            conversation.last_message_at = last_message_at
            changed = True
        if changed:
            await db.flush()
            await db.refresh(conversation)
        return conversation


conversation_repository = ConversationRepository()
