"""Outbound messages endpoint tests — covers spec §3 (send text, Cloud API errors)."""

import respx
from httpx import Response
from sqlalchemy import select

from app.models.conversation import Conversation
from app.models.message import Message, MessageDirection

WA_PHONE_ID = "123456"
CLOUD_URL = f"https://graph.facebook.com/v26.0/{WA_PHONE_ID}/messages"


async def test_post_send_message_returns_wamid_and_persists(client, session):
    with respx.mock(assert_all_called=True) as mock:
        route = mock.post(CLOUD_URL).mock(
            return_value=Response(
                200,
                json={"messages": [{"id": "wamid.OUT"}]},
            )
        )

        r = await client.post(
            "/api/v1/messages",
            json={"to": "5491155550001", "body": "hi"},
        )

    assert r.status_code == 200, r.text
    assert r.json() == {"wamid": "wamid.OUT", "status": "sent"}
    assert route.called

    conv = (
        await session.execute(select(Conversation).where(Conversation.wa_id == "5491155550001"))
    ).scalar_one()
    msgs = (
        (await session.execute(select(Message).where(Message.conversation_id == conv.id)))
        .scalars()
        .all()
    )
    assert len(msgs) == 1
    assert msgs[0].wamid == "wamid.OUT"
    assert msgs[0].direction == MessageDirection.outbound
    assert msgs[0].body == "hi"
    assert msgs[0].status == "sent"


async def test_post_send_message_cloud_api_400_returns_502(client, session):
    with respx.mock(assert_all_called=True) as mock:
        mock.post(CLOUD_URL).mock(
            return_value=Response(400, json={"error": {"message": "bad recipient"}})
        )

        r = await client.post(
            "/api/v1/messages",
            json={"to": "5491155550001", "body": "hi"},
        )

    assert r.status_code == 502, r.text

    conv = (
        await session.execute(select(Conversation).where(Conversation.wa_id == "5491155550001"))
    ).scalar_one_or_none()
    assert conv is None

    msgs = (await session.execute(select(Message))).scalars().all()
    assert msgs == []


async def test_post_send_message_requires_admin_auth(client):
    r = await client.post(
        "/api/v1/messages",
        json={"to": "5491155550001", "body": "hi"},
        headers={"Authorization": ""},
    )

    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Basic"
