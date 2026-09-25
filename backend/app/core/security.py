"""Password hashing and access-token primitives.

Credentials are stored as Argon2id hashes produced by ``pwdlib``'s recommended
hasher. Plaintext passwords are never persisted, logged, or returned.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError

from backend.app.core.config import Settings

# Argon2id via pwdlib's recommended parameters. Each salt is generated per hash.
password_hasher = PasswordHash.recommended()

ACCESS_TOKEN_TYPE = "access"


class AuthenticationConfigurationError(RuntimeError):
    """Raised when the deployment has not supplied usable JWT settings."""


class InvalidAccessTokenError(RuntimeError):
    """Raised when a bearer token is malformed, tampered with, or expired."""


def hash_password(password: str) -> str:
    """Return a salted Argon2id hash. Never store or return the plaintext."""
    if not isinstance(password, str) or not password:
        raise ValueError("A non-empty password string is required.")
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Check a candidate password against a stored hash.

    Returns ``False`` rather than raising for absent, malformed, or
    unreadable hashes so that a corrupt row can never surface as a 500 and can
    never be used to distinguish accounts.
    """
    if not password_hash or not isinstance(password_hash, str):
        return False
    if not isinstance(password, str):
        return False
    try:
        return password_hasher.verify(password, password_hash)
    except (PwdlibError, TypeError, ValueError):
        return False


def _secret(settings: Settings) -> str:
    try:
        return settings.jwt_secret
    except RuntimeError as error:
        raise AuthenticationConfigurationError(str(error)) from error


def validate_jwt_configuration(settings: Settings) -> None:
    """Fail fast when the deployment cannot issue or verify tokens."""
    _secret(settings)


def create_access_token(user_id: int, settings: Settings) -> str:
    """Issue a signed access token whose subject is the user's primary key.

    Only the identifier is carried: no email or name, so a leaked token does
    not disclose personal data. A unique ``jti`` is included to give a future
    revocation list something to key on.
    """
    if user_id < 1:
        raise ValueError("A valid user id is required to issue an access token.")

    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": expires_at,
        "type": ACCESS_TOKEN_TYPE,
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, _secret(settings), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> int:
    """Validate a bearer token and return the user id it authenticates.

    Signature, algorithm, expiry, and token type are all verified. Any failure
    raises :class:`InvalidAccessTokenError` so callers cannot accidentally
    treat a bad token as anonymous-but-trusted.
    """
    if not isinstance(token, str) or not token.strip():
        raise InvalidAccessTokenError("The access token is missing.")

    try:
        payload = jwt.decode(
            token.strip(),
            _secret(settings),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "iat", "exp"]},
        )
    except InvalidTokenError as error:
        raise InvalidAccessTokenError("The access token is invalid or expired.") from error

    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise InvalidAccessTokenError("The access token is invalid.")

    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as error:
        raise InvalidAccessTokenError("The access token subject is invalid.") from error

    if user_id < 1:
        raise InvalidAccessTokenError("The access token subject is invalid.")
    return user_id
