"""Webhook endpoint tests — covers spec §1 (ingestion, signature, persistence, idempotency, fast ack)."""

import asyncio
import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.models.conversation import Conversation
from app.models.message import Message, MessageDirection
from app.schemas.webhook import WebhookStatus
from app.services.webhook_service import apply_statuses

VERIFY_TOKEN = "test-verify"
APP_SECRET = "test-secret"
WA_PHONE_ID = "123456"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _payload(wamid: str | None = None) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "ENTRY_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "1555",
                                "phone_number_id": WA_PHONE_ID,
                            },
                            "contacts": [{"profile": {"name": "Alice"}, "wa_id": "5491155550001"}],
                            "messages": [
                                {
                                    "from": "5491155550001",
                                    "id": wamid or f"wamid.{uuid.uuid4().hex}",
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": "Hello!"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


async def _wait_for_message(session, wamid: str, timeout: float = 2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = (
            await session.execute(select(Message).where(Message.wamid == wamid))
        ).scalar_one_or_none()
        if row is not None:
            return row
        await asyncio.sleep(0.02)
    return None


async def test_handshake_valid_returns_challenge(client):
    r = await client.get(
        "/api/v1/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "12345",
        },
    )
    assert r.status_code == 200
    assert r.text == "12345"


async def test_handshake_bad_token_returns_403(client):
    r = await client.get(
        "/api/v1/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "WRONG",
            "hub.challenge": "12345",
        },
    )
    assert r.status_code == 403


async def test_handshake_wrong_mode_returns_403(client):
    r = await client.get(
        "/api/v1/webhook",
        params={
            "hub.mode": "unsubscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "12345",
        },
    )
    assert r.status_code == 403


async def test_post_valid_signature_persists_message(client, session):
    wamid = f"wamid.{uuid.uuid4().hex}"
    body = json.dumps(_payload(wamid)).encode()
    sig = _sign(body)

    r = await client.post(
        "/api/v1/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": sig,
        },
    )
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    msg = await _wait_for_message(session, wamid)
    assert msg is not None, "Message was not persisted in time"
    assert msg.direction == MessageDirection.inbound
    assert msg.body == "Hello!"
    conv = (
        await session.execute(select(Conversation).where(Conversation.wa_id == "5491155550001"))
    ).scalar_one()
    assert conv.name == "Alice"


async def test_post_invalid_signature_returns_401_and_no_persist(client, session):
    wamid = f"wamid.{uuid.uuid4().hex}"
    body = json.dumps(_payload(wamid)).encode()

    r = await client.post(
        "/api/v1/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
        },
    )
    assert r.status_code == 401

    await asyncio.sleep(0.1)
    msg = (
        await session.execute(select(Message).where(Message.wamid == wamid))
    ).scalar_one_or_none()
    assert msg is None


async def test_post_missing_signature_returns_401(client):
    body = json.dumps(_payload()).encode()
    r = await client.post("/api/v1/webhook", content=body)
    assert r.status_code == 401


async def test_post_duplicate_wamid_is_idempotent(client, session):
    wamid = f"wamid.{uuid.uuid4().hex}"
    body = json.dumps(_payload(wamid)).encode()
    sig = _sign(body)

    r1 = await client.post(
        "/api/v1/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
    )
    assert r1.status_code == 200

    r2 = await client.post(
        "/api/v1/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
    )
    assert r2.status_code == 200

    msg = await _wait_for_message(session, wamid)
    assert msg is not None

    await asyncio.sleep(0.2)
    rows = (await session.execute(select(Message).where(Message.wamid == wamid))).scalars().all()
    assert len(rows) == 1, f"expected 1 persisted message, got {len(rows)}"


async def test_post_ack_under_500ms(client):
    wamid = f"wamid.{uuid.uuid4().hex}"
    body = json.dumps(_payload(wamid)).encode()
    sig = _sign(body)

    t0 = time.monotonic()
    r = await client.post(
        "/api/v1/webhook",
        content=body,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig},
    )
    elapsed = time.monotonic() - t0

    assert r.status_code == 200
    assert elapsed < 0.5, f"ack took {elapsed * 1000:.1f} ms, budget is 500 ms"


async def test_webhook_response_does_not_leak_secret(client, caplog):
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    sig = "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()

    with caplog.at_level("DEBUG"):
        r = await client.post(
            "/api/v1/webhook",
            content=body,
            headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
        )

    assert r.status_code == 200
    assert APP_SECRET.encode() not in r.content
    assert b"APP_SECRET" not in r.content
    for record in caplog.records:
        assert APP_SECRET not in record.getMessage()


async def test_webhook_invalid_signature_does_not_leak_secret(client, caplog):
    body = json.dumps(_payload()).encode()

    with caplog.at_level("DEBUG"):
        r = await client.post(
            "/api/v1/webhook",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=" + "0" * 64,
            },
        )

    assert r.status_code == 401
    assert APP_SECRET.encode() not in r.content
    for record in caplog.records:
        assert APP_SECRET not in record.getMessage()


async def test_error_envelope_returns_error_code_and_message(client):
    body = json.dumps(_payload()).encode()
    r = await client.post(
        "/api/v1/webhook",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
        },
    )

    assert r.status_code == 401
    body_json = r.json()
    assert "error" in body_json, f"expected {{error: ...}} envelope, got {body_json}"
    assert "code" in body_json["error"], f"missing 'code' key in {body_json['error']}"
    assert "message" in body_json["error"], f"missing 'message' key in {body_json['error']}"
    assert body_json["error"]["code"] == "unauthorized"
    assert isinstance(body_json["error"]["message"], str)


async def test_apply_statuses_updates_message(session):
    wamid = f"wamid.{uuid.uuid4().hex}"
    now = datetime.now(UTC)
    conv = Conversation(wa_id="5491155550001", name="Alice", last_message_at=now)
    session.add(conv)
    await session.flush()
    msg = Message(
        wamid=wamid,
        conversation_id=conv.id,
        direction=MessageDirection.outbound,
        body="hi",
        status="sent",
        created_at=now,
    )
    session.add(msg)
    await session.commit()

    statuses = [WebhookStatus(id=wamid, status="delivered", timestamp="1700000010")]
    await apply_statuses(statuses, session)
    await session.commit()

    await session.refresh(msg)
    assert msg.status == "delivered"


async def test_inbound_reuses_existing_conversation_by_wa_id(client, session):
    """Spec §2 — Conversation Reuse: same wa_id MUST reuse the existing Conversation row."""
    body1 = json.dumps(_payload(wamid="wamid.AAA")).encode()
    sig1 = _sign(body1)
    r1 = await client.post(
        "/api/v1/webhook",
        content=body1,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig1},
    )
    assert r1.status_code == 200

    # BackgroundTask runs after ack — give it a moment to commit
    await asyncio.sleep(0.05)
    convs = (await session.execute(select(Conversation))).scalars().all()
    assert len(convs) == 1, f"expected 1 conversation after first POST, got {len(convs)}"
    original_id = convs[0].id
    original_last = convs[0].last_message_at

    # Second inbound from same wa_id — new wamid so it's not a wamid-dup short-circuit
    body2 = json.dumps(_payload(wamid="wamid.BBB")).encode()
    sig2 = _sign(body2)
    r2 = await client.post(
        "/api/v1/webhook",
        content=body2,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig2},
    )
    assert r2.status_code == 200

    # The webhook persists via a BackgroundTask that uses its own AsyncSessionLocal
    # session, separate from the `session` fixture. Verify via a fresh session so
    # we definitely see the post-POST state without identity-map staleness.
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as s2:
        convs_after = (await s2.execute(select(Conversation))).scalars().all()
        assert len(convs_after) == 1, (
            f"expected single conversation after second POST, got {len(convs_after)}"
        )
        assert convs_after[0].id == original_id, "conversation id changed; should reuse"
        assert convs_after[0].last_message_at >= original_last, "last_message_at not refreshed"


async def test_upsert_by_wa_id_reuses_existing_row(session):
    """Spec §2 — direct unit test for ConversationRepository.upsert_by_wa_id."""
    from app.repositories.conversation import ConversationRepository

    repo = ConversationRepository()
    conv1 = await repo.upsert_by_wa_id(
        session,
        wa_id="5491155550099",
        name="Bob",
        last_message_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    await session.commit()
    conv2 = await repo.upsert_by_wa_id(
        session,
        wa_id="5491155550099",
        name="Bob",
        last_message_at=datetime(2024, 6, 1, tzinfo=UTC),
    )
    await session.commit()
    assert conv1.id == conv2.id
    assert conv2.last_message_at.replace(tzinfo=UTC) == datetime(2024, 6, 1, tzinfo=UTC)
