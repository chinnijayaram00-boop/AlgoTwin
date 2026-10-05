"""Request and response contracts for the grounded AI coach.

Three properties of this module are load-bearing, and each exists because of a
specific way a naive shape here would be wrong:

**No request can choose what it is grounded in.** Every endpoint takes only a path
id, and the server resolves the problem or the submission from the database. There
is no body field, query field, or path field for a problem statement, an editorial,
a test case, a submission status, or a set of "facts". A caller cannot smuggle its
own context into a prompt, and cannot ask a model about a submission that is not
its own.

**``extra="forbid"`` everywhere.** A payload carrying an unexpected field is
rejected with 422 instead of silently ignored. Without it, a client could send
``{"problem_id": 7, "hidden_test_cases": [...]}`` and receive no complaint while
believing it had been included -- and a future field named something like
``grounding`` would quietly start meaning something.

**Generated content is never confused with stored editorial.** A response carries
its own ``provider``, ``model``, ``created_at``, and ``grounding``, and its prose
lives in a field named for what it is. The catalog's written explanation continues
to arrive as ``ProblemDetail.description``/``explanation`` from a different route.
A learner can always tell which words were written by the platform and which were
generated, and by which model, without trusting either.
"""

from datetime import datetime
from typing import Literal

from database.models.ai_insight import (
    AI_INSIGHT_KIND_VALUES,
    MAX_INSIGHT_CONTENT_LENGTH,
)
from database.models.submission import MAX_SOURCE_CODE_LENGTH
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.judge.languages import LANGUAGE_IDS

# Mirrors `backend.app.ai.provider.AI_INSIGHT_KINDS`, which mirrors
# `database.models.ai_insight.AIInsightKind`. Three lists of the same three values
# is one list too many, but they cannot be imported from one another: the provider
# layer must stay independent of the database, and a Pydantic `Literal` cannot be
# built from a runtime enum without losing its published schema. `backend/tests/
# test_ai.py` asserts all three agree, so the duplication cannot rot silently.
AIInsightKindInput = Literal[
    "problem_explanation",
    "submission_diagnosis",
    "code_complexity",
]


class AIStatusResponse(BaseModel):
    """What ``GET /ai/status`` reports.

    Replaces the earlier version of this shape, which was assembled straight from
    the settings object. Every field here now comes from the resolved provider, so
    this endpoint and an actual request cannot disagree: the platform can no longer
    report itself ready while every generation fails.

    ``provider`` is the *resolved* name, which may differ from what was configured.
    An unrecognised ``AI_PROVIDER`` resolves to ``disabled``, and saying so is more
    useful than echoing back the string the operator typed.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(description="The provider that actually serves requests.")
    model: str = Field(description="The model that provider will name.")
    configured: bool = Field(
        description="Whether a request would reach a provider. Read from the provider itself."
    )
    #: The configured provider name, normalised. Present so an operator can see the
    #: difference between "configured" and "what the configuration asked for".
    requested_provider: str = Field(description="The normalised AI_PROVIDER setting.")
    message: str = Field(description="A learner-safe explanation of the current state.")


class AIExplanationRequest(BaseModel):
    """Body for the problem-explanation route.

    Intentionally empty of content. The problem is named by the path and its facts
    are read from the catalog by the server, so there is nothing for a caller to
    supply. The model is kept rather than omitted so the route has an explicit,
    documented request shape -- an endpoint that documents no body is one whose
    contract is whatever the client sends.
    """

    model_config = ConfigDict(extra="forbid")

    #: Optional, and a *preference* rather than an instruction. When a problem ships
    #: an editorial in more than one form this selects which one is used; it can
    #: never introduce content, because only an identifier from the catalog's own
    #: vocabulary is accepted and the server resolves it.
    focus: Literal["approach", "correctness"] | None = Field(
        default=None,
        description=(
            "Which part of the approach to centre on. Omit for the whole approach. "
            "Never adds information the catalog does not already have."
        ),
    )


class AIComplexityRequest(BaseModel):
    """Body for the complexity route: the only AI endpoint that takes source code.

    ``source_code`` is bounded by the same ceiling a submission uses, because it is
    the same quantity: a program someone is asking about. The bound is enforced here
    rather than deep in the service so the rejection is a 422 at the edge with a
    message that names the limit, instead of a provider error after a billable call.

    ``language`` is required rather than inferred. Guessing would mean answering
    about JavaScript when the learner pasted Python, and a complexity analysis in
    the wrong language is worse than none.
    """

    model_config = ConfigDict(extra="forbid")

    language: Literal[*LANGUAGE_IDS] = Field(
        description="The language the source is written in. Not inferred from the source."
    )
    source_code: str = Field(
        min_length=1,
        max_length=MAX_SOURCE_CODE_LENGTH,
        description="The source to analyse. Stored nowhere; sent once and discarded.",
    )

    @field_validator("source_code")
    @classmethod
    def reject_blank_source(cls, value: str) -> str:
        """Reject whitespace-only source.

        An empty program has no loops, no scans, and no nesting to describe, so the
        honest answer for one is not "O(1)" -- it is to refuse it.
        """
        if not value.strip():
            raise ValueError("source_code must contain code to analyse.")
        return value


class AIInsightResponse(BaseModel):
    """One generated insight, with everything needed to judge it.

    Shared by all three endpoints because all three return the same thing: a piece
    of generated text, who it is for, what it was generated from, and who generated
    it. A single shape means the frontend builds one renderer and one loading state
    instead of three.
    """

    id: int = Field(description="The stored insight's id, for referencing the record.")
    kind: AIInsightKindInput = Field(description="Which kind of insight this is.")
    content: str = Field(
        max_length=MAX_INSIGHT_CONTENT_LENGTH,
        description="The generated text, verbatim as the provider returned it.",
    )
    #: Attribution, stored with the row rather than read from current settings, so a
    #: cached answer keeps reporting the model that actually produced it.
    provider: str
    model: str
    #: Exactly which safe facts were sent. Lets a learner, or a reviewer, check what
    #: the model was actually told rather than trusting the prompt code.
    grounding: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    #: ``True`` when this response was served from the stored insight rather than
    #: generated now. A client can label it: a cached answer and a fresh one are
    #: both honest, but they are not the same act.
    cached: bool = Field(
        default=False,
        description="True when no provider call was made for this response.",
    )
    #: ``True`` only for the deterministic fake provider, whose output is fixed text
    #: and never a model's answer. The UI surfaces this; it must never be silently
    #: hidden, because "no model was consulted" is the single most important thing
    #: to tell a reader of generated output.
    is_demo_output: bool = Field(
        default=False, description="True when this text came from the fake provider, not a model."
    )


class AIComplexityResponse(AIInsightResponse):
    """A complexity analysis.

    The structured verdict travels beside the prose rather than being extracted from
    it. Two reasons, both practical: a learner can sort or compare on a field instead
    of parsing Markdown, and the API does not have to trust a model to emit
    well-formed JSON before it can show the headline result. A value of
    ``"undetermined"`` is a legitimate answer -- it is what an empty or
    unrecognisable program gets -- and is never silently replaced with a guess.
    """

    time_complexity: str = Field(description="Analysed time complexity, or 'undetermined'.")
    space_complexity: str = Field(description="Analysed space complexity, or 'undetermined'.")
    reasoning: str = Field(description="The model's justification for the two claims.")
    #: The complexity the catalog records for this problem, when the source was
    #: analysed in the context of a problem. Never presented as a measurement, and
    #: ``None`` when there is nothing to compare against.
    expected_time_complexity: str | None = Field(
        default=None, description="The catalog's target time complexity, if known."
    )
    expected_space_complexity: str | None = Field(
        default=None, description="The catalog's target space complexity, if known."
    )


__all__ = [
    "AI_INSIGHT_KIND_VALUES",
    "AIComplexityRequest",
    "AIComplexityResponse",
    "AIExplanationRequest",
    "AIInsightKindInput",
    "AIInsightResponse",
    "AIStatusResponse",
]
