import httpx

from app.core.config import Settings


class WhatsAppAPIError(Exception):
    pass


class WhatsAppClient:
    def __init__(
        self,
        phone_id: str,
        token: str,
        version: str = "v20.0",
    ) -> None:
        self._phone_id = phone_id
        self._token = token
        self._url = f"https://graph.facebook.com/{version}/{phone_id}/messages"
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send_text(self, to_wa_id: str, body: str) -> str:
        if not self._client:
            raise RuntimeError("WhatsAppClient not started")
        payload = {
            "messaging_product": "whatsapp",
            "to": to_wa_id,
            "type": "text",
            "text": {"body": body},
        }
        headers = {"Authorization": f"Bearer {self._token}"}
        r = await self._client.post(self._url, json=payload, headers=headers)
        if r.status_code >= 400:
            raise WhatsAppAPIError(f"Cloud API returned HTTP {r.status_code}")
        data = r.json()
        return data["messages"][0]["id"]


def build_client(settings: Settings) -> WhatsAppClient:
    return WhatsAppClient(settings.PHONE_NUMBER_ID, settings.ACCESS_TOKEN)
