import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.api.dependencies import close_ai_providers
from backend.app.api.router import api_router
from backend.app.core.config import MIN_JWT_SECRET_LENGTH, Settings, get_settings
from backend.app.core.security import (
    AuthenticationConfigurationError,
    validate_jwt_configuration,
)
from backend.app.db.session import init_db

logger = logging.getLogger(__name__)

settings = get_settings()


def warn_if_auth_is_unconfigured(settings: Settings) -> None:
    """Report an unusable JWT configuration at start-up.

    The auth routes already fail closed with a 503, but a deployment that boots
    silently and only reveals the problem on the first login wastes the operator's
    time -- which is exactly how a too-short placeholder in ``.env`` surfaced as
    "Authentication is not configured." on the sign-in form. This is deliberately a
    warning rather than an exception: public routes such as health and the catalog
    must stay available, and the request-time 503 remains the authority. The message
    never contains the secret itself, only the requirement it failed.
    """
    try:
        validate_jwt_configuration(settings)
    except AuthenticationConfigurationError:
        logger.warning(
            "Authentication is not configured: JWT_SECRET_KEY is missing or shorter "
            "than %d characters. /api/v1/auth/* will answer 503 until a usable secret "
            "is set in .env.",
            MIN_JWT_SECRET_LENGTH,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepare the database on start-up and release pooled clients on shutdown.

    The shutdown half closes the AI provider's HTTP connection pool. Without it the
    process would exit with an open pool, which is invisible in development (the
    socket dies with the interpreter) and shows up in production as a pile of
    ``ResourceWarning``s and connections held past the last request.
    """
    init_db()
    warn_if_auth_is_unconfigured(settings)
    try:
        yield
    finally:
        await close_ai_providers(app)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


def install_security_headers() -> None:
    """Add the hardening headers every response carries (see :func:`add_security_headers`).

    A production deployment will want a strict Content-Security-Policy tuned to
    its own origin, so CSP is deliberately not emitted here. This middleware is
    registered regardless of whether the process has HTTPS or a reverse proxy;
    the headers are inert over plain HTTP but become meaningful once the
    deployment terminates TLS.
    """
    app.add_middleware(BaseHTTPMiddleware, dispatch=add_security_headers)


async def add_security_headers(request, call_next):
    """Add `Cache-Control: no-store` for authenticated traffic plus the fixed headers.

    ``no-store`` is the load-bearing one: without it a browser can replay a
    signed JWT from back-history or a hop cache. It is only set when this
    request came in authenticated (``Authorization`` header), because the
    public reads (catalog, health) are cacheable by design.
    """
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    if request.headers.get("authorization"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


install_security_headers()
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["service"])
def service_root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "ok", "docs": "/docs"}
