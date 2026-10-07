from fastapi import APIRouter

from backend.app.api.routes import (
    ai,
    algorithms,
    analytics,
    auth,
    dashboard,
    health,
    interviews,
    judge,
    learning_path,
    problems,
    progress,
    submissions,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(problems.router)
api_router.include_router(dashboard.router)
api_router.include_router(analytics.router)
api_router.include_router(progress.router)
api_router.include_router(learning_path.router)
# Registered after `problems` because the judge and submission routers also serve
# `/problems/{problem_id}/...`. The two cannot collide -- a path parameter does not
# match across a `/` -- but keeping the longer, more specific feature grouped with
# the rest of the learner-scoped routes reads better than splitting it away from
# the submission routes above it.
api_router.include_router(judge.router)
api_router.include_router(submissions.router)
api_router.include_router(interviews.router)
api_router.include_router(algorithms.router)
api_router.include_router(ai.router)
api_router.include_router(auth.router)
