from dataclasses import dataclass


@dataclass(frozen=True)
class AlgorithmDescriptor:
    id: str
    name: str
    category: str
    time_complexity: str | None
    space_complexity: str | None
    supported_languages: tuple[str, ...]


ALGORITHM_REGISTRY: tuple[AlgorithmDescriptor, ...] = ()


def list_algorithms() -> tuple[AlgorithmDescriptor, ...]:
    return ALGORITHM_REGISTRY
