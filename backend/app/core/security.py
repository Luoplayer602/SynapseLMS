import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import get_settings
from app.core.errors import APIError

password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def now():
    return datetime.now(UTC)


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def verify_password(password: str, password_hash: str):
    try:
        return password_hasher.verify(password, password_hash)
    except (ValueError, UnknownHashError):
        return False


def access_token(user_id, session_id):
    settings = get_settings()
    issued = now()
    return jwt.encode(
        {
            "sub": str(user_id),
            "sid": str(session_id),
            "type": "access",
            "jti": str(uuid4()),
            "iat": issued,
            "exp": issued + timedelta(minutes=settings.access_minutes),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def decode_access(token):
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "sid", "type", "iat", "exp", "jti"]},
        )
        if claims["type"] != "access":
            raise APIError(401, "INVALID_SESSION")
        return claims
    except jwt.InvalidTokenError as error:
        raise APIError(401, "INVALID_SESSION") from error
