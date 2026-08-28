from pydantic import BaseModel, ConfigDict, Field


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    to: str = Field(..., description="Recipient WhatsApp ID (wa_id)")
    body: str = Field(..., description="Text body to send")


class SendMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    wamid: str
    status: str = "sent"
