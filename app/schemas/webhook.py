from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ContactProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None


class WebhookContact(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    wa_id: str | None = None
    profile: ContactProfile = Field(default_factory=ContactProfile)


class MessageMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    display_phone_number: str | None = None
    phone_number_id: str | None = None


class WebhookText(BaseModel):
    model_config = ConfigDict(extra="ignore")

    body: str = ""


class WebhookMessage(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str
    from_: str = Field(validation_alias=AliasChoices("from_", "from"))
    timestamp: str | None = None
    type: str
    text: WebhookText | None = None


class WebhookStatus(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    status: str
    timestamp: str | None = None


class ChangeValue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    messaging_product: str | None = None
    metadata: MessageMetadata | None = None
    contacts: list[WebhookContact] | None = None
    messages: list[WebhookMessage] | None = None
    statuses: list[WebhookStatus] | None = None


class Change(BaseModel):
    model_config = ConfigDict(extra="ignore")

    field: str
    value: ChangeValue


class Entry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    changes: list[Change] = Field(default_factory=list)


class WebhookPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    object: str
    entry: list[Entry] = Field(default_factory=list)
