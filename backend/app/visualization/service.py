from dataclasses import dataclass


class VisualizationNotConfiguredError(RuntimeError):
    pass


@dataclass(frozen=True)
class VisualizationRequest:
    algorithm_id: str
    input: str


@dataclass(frozen=True)
class VisualizationFrame:
    step: int
    state: dict[str, object]
    explanation: str


class VisualizationService:
    def generate_frames(self, request: VisualizationRequest) -> tuple[VisualizationFrame, ...]:
        raise VisualizationNotConfiguredError("Algorithm execution is not enabled in the foundation release.")
