from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wa_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    def __repr__(self) -> str:
        return f"Conversation(id={self.id}, wa_id={self.wa_id!r})"
