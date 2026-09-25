from fastapi import APIRouter

from backend.app.algorithms.registry import list_algorithms
from backend.app.schemas.platform import AlgorithmListResponse, AlgorithmResponse

router = APIRouter(prefix="/algorithms", tags=["algorithms"])


@router.get("", response_model=AlgorithmListResponse)
def get_algorithms() -> AlgorithmListResponse:
    return AlgorithmListResponse(
        items=[
            AlgorithmResponse(
                id=algorithm.id,
                name=algorithm.name,
                category=algorithm.category,
                time_complexity=algorithm.time_complexity,
                space_complexity=algorithm.space_complexity,
                supported_languages=list(algorithm.supported_languages),
            )
            for algorithm in list_algorithms()
        ]
    )
