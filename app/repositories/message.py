from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message, dict, dict]):
    def __init__(self) -> None:
        super().__init__(Message)

    async def list_for_conversation(
        self,
        db: AsyncSession,
        conversation_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_wamid(
        self,
        db: AsyncSession,
        wamid: str,
    ) -> Message | None:
        result = await db.execute(select(Message).where(Message.wamid == wamid))
        return result.scalars().first()


message_repository = MessageRepository()
