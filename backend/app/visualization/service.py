"""Where the algorithm lab's public types lived before they had an implementation.

The foundation release published :class:`VisualizationRequest`,
:class:`VisualizationFrame`, :class:`VisualizationService` and
:class:`VisualizationNotConfiguredError` here, with the service raising
"not configured" because there was nothing to run. All four still exist -- they are
now backed by the registry and the worker rather than by a stub -- but they live in
:mod:`backend.app.services.visualization_service`, next to the code that uses them,
so that "what a frame means" has one definition in the platform.

This module re-exports them rather than deleting them. A dead stub that raises is
worse than no module; a module that keeps the old import path working is neither.
"""

from backend.app.services.visualization_service import (
    AlgorithmNotFoundError,
    InvalidVisualizationInputError,
    VisualizationFrame,
    VisualizationNotConfiguredError,
    VisualizationRequest,
    VisualizationResult,
    VisualizationService,
    VisualizationUnavailableError,
    describe_algorithm,
    visualize_algorithm,
)

__all__ = [
    "AlgorithmNotFoundError",
    "InvalidVisualizationInputError",
    "VisualizationFrame",
    "VisualizationNotConfiguredError",
    "VisualizationRequest",
    "VisualizationResult",
    "VisualizationService",
    "VisualizationUnavailableError",
    "describe_algorithm",
    "visualize_algorithm",
]
