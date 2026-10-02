"""Reusable dependencies for authentication and application-wide resources.

``get_current_user`` is the guard every authenticated backend route should use.
It returns the ``User`` row identified by the bearer token, or raises 401.

``get_ai_provider`` is the other kind of dependency: not a guard but a process-wide
resource. It hands routes the *same* provider instance for the lifetime of the
process, which is what makes the HTTP connection pool inside the OpenAI-compatible
provider a pool rather than a fresh client per request. :func:`close_ai_providers`
is its counterpart and is called from the application lifespan.
"""

from __future__ import annotations

import hashlib
from typing import Annotated

from database.models import User
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.ai.provider import AIProvider
from backend.app.ai.service import AIService
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


def _ai_provider_key(settings: Settings) -> tuple[str, str, str, str]:
    """A hashable identity for the provider ``settings`` describes.

    Keyed on the fields that change what a provider *is*, and on a digest of the
    credential rather than the credential itself. A secret must not end up in a
    ``repr``, a traceback, or a debugging tool's object inspector, and a dict key is
    exactly the sort of thing that turns up in all three.

    The digest is over a settings-derived key rather than a deployment-wide salt. It
    exists so two configurations with different credentials cannot share one pooled
    client -- a bug that would be silent and would send one deployment's bearer token
    to another deployment's endpoint.
    """
    credential = settings.ai_api_key_value
    digest = (
        hashlib.sha256(credential.encode("utf-8")).hexdigest()
        if credential
        else ""
    )
    return (
        settings.ai_provider.strip().lower(),
        settings.ai_base_url,
        settings.ai_model,
        digest,
    )


def get_ai_provider(
    request: Request, settings: Settings = Depends(get_settings)
) -> AIProvider:
    """The resolved provider for this process, built once and reused.

    Routes must take their provider from here rather than constructing
    :class:`~backend.app.ai.service.AIService` themselves. Constructing one per
    request would resolve a fresh provider per request, and with it a fresh HTTP
    client per request: no connection reuse, and a socket left for the garbage
    collector instead of closed by :func:`close_ai_providers`.

    The cache lives on ``app.state`` rather than in a module global so it is created
    with the application, discarded with it, and cannot leak between the
    ``TestClient`` instances a test suite creates. Keyed by configuration, so a test
    that overrides ``get_settings`` gets its own provider rather than the one the
    previous test caused to be built.
    """
    cache = getattr(request.app.state, "ai_services", None)
    if cache is None:
        cache = {}
        request.app.state.ai_services = cache

    key = _ai_provider_key(settings)
    service = cache.get(key)
    if service is None:
        service = AIService(settings)
        cache[key] = service
    return service.provider


async def close_ai_providers(app: FastAPI) -> None:
    """Close every provider this process built. Call from the lifespan shutdown.

    Idempotent and never raises: a failure to close a connection pool must not stop
    the application from shutting down, and the process is about to exit regardless.
    """
    services = getattr(app.state, "ai_services", {})
    for service in list(services.values()):
        try:
            await service.aclose()
        except Exception:  # noqa: BLE001 - shutdown must not fail on cleanup
            pass
    app.state.ai_services = {}


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]
AIProviderDependency = Annotated[AIProvider, Depends(get_ai_provider)]
