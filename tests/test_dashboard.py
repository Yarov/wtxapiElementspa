"""Dashboard HTML tests — covers spec §4 (conversation list, thread view, send form)."""

from datetime import UTC, datetime, timedelta

import respx
from httpx import Response
from sqlalchemy import select

from app.core.security import create_csrf_token
from app.models.conversation import Conversation
from app.models.message import Message, MessageDirection

WA_PHONE_ID = "123456"
CLOUD_URL = f"https://graph.facebook.com/v20.0/{WA_PHONE_ID}/messages"


async def test_index_lists_conversations(client, session):
    now = datetime.now(UTC)
    conv_a = Conversation(wa_id="5491155550001", name="Alice", last_message_at=now)
    conv_b = Conversation(
        wa_id="5491155550002",
        name="Bob",
        last_message_at=now + timedelta(seconds=1),
    )
    session.add_all([conv_a, conv_b])
    await session.commit()

    r = await client.get("/")
    assert r.status_code == 200
    assert "WhatsApp Inbox" in r.text
    assert "Alice" in r.text
    assert "Bob" in r.text


async def test_index_empty_state(client, session):
    r = await client.get("/")
    assert r.status_code == 200
    assert "WhatsApp Inbox" in r.text
    assert "No conversations yet." in r.text


async def test_conversation_view_lists_messages_ascending(client, session):
    now = datetime.now(UTC)
    conv = Conversation(wa_id="5491155550001", name="Alice", last_message_at=now)
    session.add(conv)
    await session.flush()

    m1 = Message(
        wamid="wamid.A",
        conversation_id=conv.id,
        direction=MessageDirection.inbound,
        body="first",
        status="received",
        created_at=now,
    )
    m2 = Message(
        wamid="wamid.B",
        conversation_id=conv.id,
        direction=MessageDirection.outbound,
        body="second",
        status="sent",
        created_at=now + timedelta(seconds=1),
    )
    session.add_all([m1, m2])
    await session.commit()

    r = await client.get(f"/c/{conv.id}")
    assert r.status_code == 200
    assert "Alice" in r.text
    assert "first" in r.text
    assert "second" in r.text
    idx_first = r.text.find("first")
    idx_second = r.text.find("second")
    assert idx_first < idx_second, "messages must render in ascending created_at order"


async def test_send_form_redirects_to_thread(client, session):
    now = datetime.now(UTC)
    conv = Conversation(wa_id="5491155550001", name="Alice", last_message_at=now)
    session.add(conv)
    await session.commit()
    conv_id = conv.id

    with respx.mock(assert_all_called=True) as mock:
        mock.post(CLOUD_URL).mock(
            return_value=Response(200, json={"messages": [{"id": "wamid.OUT"}]})
        )

        r = await client.post(
            f"/c/{conv_id}/send",
            data={
                "body": "hi",
                "csrf_token": create_csrf_token(str(conv_id), "test-secret"),
            },
            follow_redirects=False,
        )

    assert r.status_code == 303
    assert r.headers["location"] == f"/c/{conv_id}"

    msg = (await session.execute(select(Message).where(Message.wamid == "wamid.OUT"))).scalar_one()
    assert msg.body == "hi"
    assert msg.direction == MessageDirection.outbound


async def test_dashboard_requires_admin_auth(client):
    r = await client.get("/", headers={"Authorization": ""})

    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Basic"


async def test_send_form_rejects_invalid_csrf_token(client, session):
    now = datetime.now(UTC)
    conv = Conversation(wa_id="5491155550001", name="Alice", last_message_at=now)
    session.add(conv)
    await session.commit()

    r = await client.post(
        f"/c/{conv.id}/send",
        data={"body": "hi", "csrf_token": "invalid"},
        follow_redirects=False,
    )

    assert r.status_code == 403
