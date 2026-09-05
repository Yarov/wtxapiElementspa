"""Pure unit tests for verify_signature."""

import hashlib
import hmac

from app.core.security import create_csrf_token, verify_csrf_token, verify_signature


def test_valid_signature():
    body = b'{"hello":"world"}'
    sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_signature(body, sig, "secret") is True


def test_wrong_secret():
    body = b"x"
    sig = "sha256=" + hmac.new(b"right", body, hashlib.sha256).hexdigest()
    assert verify_signature(body, sig, "wrong") is False


def test_missing_header():
    assert verify_signature(b"x", None, "secret") is False


def test_wrong_prefix():
    assert verify_signature(b"x", "md5=abc", "secret") is False


def test_tampered_body():
    body = b'{"hello":"world"}'
    sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    assert verify_signature(b'{"hello":"WORLD"}', sig, "secret") is False


def test_csrf_token_is_bound_to_subject_and_secret():
    token = create_csrf_token("42", "secret")

    assert verify_csrf_token("42", token, "secret") is True
    assert verify_csrf_token("43", token, "secret") is False
    assert verify_csrf_token("42", token, "wrong") is False
