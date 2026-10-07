"""The learning path endpoint.

Authenticated exactly like the progress routes: the learner's identity comes
only from the bearer token via ``CurrentUser``, and there is no ``user_id``
parameter, query field, or body field anywhere in this module, so no request
can read another learner's path. The response is built from the published
catalog plus that one learner's stored progress rows.
"""

from fastapi import APIRouter

from backend.app.api.dependencies import CurrentUser, DbSession
from backend.app.schemas.learning_path import LearningPathResponse
from backend.app.services.learning_path_service import load_learning_path

router = APIRouter(prefix="/learning-path", tags=["learning-path"])


@router.get("", response_model=LearningPathResponse)
def read_my_learning_path(db: DbSession, current_user: CurrentUser) -> LearningPathResponse:
    """The authenticated learner's ordered stages and their next recommendation.

    One endpoint returns the whole path -- stages, per-stage progress, and the
    single recommended next problem with its reason -- so the dashboard and the
    learning path page read the same computation instead of maintaining two
    approximations of it. ``recommendation`` is ``null`` only when every
    published problem is solved.
    """
    return load_learning_path(db, current_user.id)
