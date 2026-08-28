import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MessageDirection(enum.StrEnum):
    inbound = "inbound"
    outbound = "outbound"


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wamid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
    )
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, name="message_direction"),
    )
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="received")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    conversation: Mapped["Conversation"] = relationship(  # noqa: F821
        "Conversation",
        backref="messages",
        lazy="noload",
    )

    def __repr__(self) -> str:
        return f"Message(id={self.id}, wamid={self.wamid!r}, direction={self.direction.value})"
