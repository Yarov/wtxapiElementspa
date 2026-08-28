"""Webhook endpoint tests — covers spec §1 (ingestion, signature, persistence, idempotency, fast ack)."""

import asyncio
import hashlib
import hmac
import json
import time
import uuid

from sqlalchemy import select

from app.models.conversation import Conversation
from app.models.message import Message, MessageDirection

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
