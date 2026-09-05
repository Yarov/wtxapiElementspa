from pydantic import BaseModel, ConfigDict, Field


class SendMessageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    to: str = Field(
        ...,
        min_length=5,
        max_length=20,
        pattern=r"^\d+$",
        description="Recipient WhatsApp ID (wa_id)",
    )
    body: str = Field(..., min_length=1, max_length=4096, description="Text body to send")


class SendMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    wamid: str
    status: str = "sent"
