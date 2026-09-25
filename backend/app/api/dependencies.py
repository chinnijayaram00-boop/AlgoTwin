"""Reusable authentication dependencies.

``get_current_user`` is the guard every authenticated backend route should use.
It returns the ``User`` row identified by the bearer token, or raises 401.
"""

from typing import Annotated

from database.models import User
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.security import (
    AuthenticationConfigurationError,
    InvalidAccessTokenError,
    decode_access_token,
)
from backend.app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
    scheme_name="ALgotwin access token",
)


def _unauthorized(detail: str = "Could not validate credentials.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _not_configured() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication is not configured.",
    )


def resolve_token_user(token: str | None, db: Session, settings: Settings) -> User:
    """Resolve a bearer token to a live user row.

    Raises 401 when the token is absent, malformed, expired, signed with the
    wrong key, or refers to a user that no longer exists. Raises 503 when the
    deployment has no JWT secret configured.
    """
    if not token:
        raise _unauthorized()

    try:
        user_id = decode_access_token(token, settings)
    except AuthenticationConfigurationError as error:
        raise _not_configured() from error
    except InvalidAccessTokenError as error:
        raise _unauthorized() from error

    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized()
    return user


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Require a valid access token. Apply to every user-specific route."""
    return resolve_token_user(token, db, settings)


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
