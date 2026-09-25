from fastapi import APIRouter

from backend.app.api.routes import ai, algorithms, auth, dashboard, health, problems

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(problems.router)
api_router.include_router(dashboard.router)
api_router.include_router(algorithms.router)
api_router.include_router(ai.router)
api_router.include_router(auth.router)
