from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from backend.app.core.config import Settings

password_hasher = PasswordHash.recommended()


class AuthenticationConfigurationError(RuntimeError):
    pass


class InvalidAccessTokenError(RuntimeError):
    pass


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    try:
        return password_hasher.verify(password, password_hash)
    except (TypeError, ValueError):
        return False


def _secret(settings: Settings) -> str:
    try:
        return settings.jwt_secret
    except RuntimeError as error:
        raise AuthenticationConfigurationError(str(error)) from error


def validate_jwt_configuration(settings: Settings) -> None:
    _secret(settings)


def create_access_token(user_id: int, settings: Settings) -> str:
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": expires_at,
        "type": "access",
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, _secret(settings), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> int:
    try:
        payload = jwt.decode(
            token,
            _secret(settings),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "iat", "exp"]},
        )
    except InvalidTokenError as error:
        raise InvalidAccessTokenError("The access token is invalid or expired.") from error

    if payload.get("type") != "access":
        raise InvalidAccessTokenError("The access token is invalid.")

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidAccessTokenError("The access token subject is invalid.") from error

    if user_id < 1:
        raise InvalidAccessTokenError("The access token subject is invalid.")
    return user_id
