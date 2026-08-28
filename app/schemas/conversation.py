from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wa_id: str
    name: str | None = None
    last_message_at: datetime
    last_message_preview: str | None = None
    unread_count: int = 0
