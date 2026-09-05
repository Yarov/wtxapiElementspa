import hashlib
import hmac


def verify_signature(raw_body: bytes, header: str | None, app_secret: str) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def create_csrf_token(subject: str, app_secret: str) -> str:
    return hmac.new(app_secret.encode(), subject.encode(), hashlib.sha256).hexdigest()


def verify_csrf_token(subject: str, token: str, app_secret: str) -> bool:
    expected = create_csrf_token(subject, app_secret)
    return hmac.compare_digest(expected, token)
