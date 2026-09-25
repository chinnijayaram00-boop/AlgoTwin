from database.models import User
from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.dependencies import AppSettings, CurrentUser, DbSession
from backend.app.core.config import Settings
from backend.app.core.security import (
    AuthenticationConfigurationError,
    create_access_token,
    hash_password,
    validate_jwt_configuration,
    verify_password,
)
from backend.app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserProfile,
    normalize_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _configuration_error(error: AuthenticationConfigurationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Authentication is not configured.",
    )


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _find_user_by_email(db: Session, email: str) -> User | None:
    """Look up a user case-insensitively so pre-normalized rows always match."""
    return db.scalar(select(User).where(func.lower(User.email) == normalize_email(email)))


def _issue_session(user: User, settings: Settings) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user.id, settings),
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserProfile.model_validate(user),
    )


def _require_jwt_configuration(settings: Settings) -> None:
    try:
        validate_jwt_configuration(settings)
    except AuthenticationConfigurationError as error:
        raise _configuration_error(error) from error


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: DbSession,
    settings: AppSettings,
) -> AuthResponse:
    _require_jwt_configuration(settings)

    if _find_user_by_email(db, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        # Lost a race against a concurrent registration for the same address.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        ) from error
    db.refresh(user)

    return _issue_session(user, settings)


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    db: DbSession,
    settings: AppSettings,
) -> AuthResponse:
    _require_jwt_configuration(settings)

    user = _find_user_by_email(db, payload.email)
    if user is None:
        # Hash anyway so a missing account and a wrong password cost the same.
        verify_password(payload.password, hash_password("algotwin-timing-equalizer"))
        raise _unauthorized()
    if not verify_password(payload.password, user.password_hash):
        raise _unauthorized()

    return _issue_session(user, settings)


@router.get("/me", response_model=UserProfile)
def read_current_user(current_user: CurrentUser) -> UserProfile:
    return UserProfile.model_validate(current_user)


@router.post("/logout", response_model=None, status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: CurrentUser) -> Response:
    """Acknowledge sign-out.

    Access tokens are stateless, so the authoritative revocation is the client
    discarding the token. The endpoint requires a valid token so it can never
    be used to probe account existence.
    """
    return Response(status_code=status.HTTP_204_NO_CONTENT)
