from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.dependencies import close_ai_providers
from backend.app.api.router import api_router
from backend.app.core.config import get_settings
from backend.app.db.session import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepare the database on start-up and release pooled clients on shutdown.

    The shutdown half closes the AI provider's HTTP connection pool. Without it the
    process would exit with an open pool, which is invisible in development (the
    socket dies with the interpreter) and shows up in production as a pile of
    ``ResourceWarning``s and connections held past the last request.
    """
    init_db()
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
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["service"])
def service_root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "ok", "docs": "/docs"}
