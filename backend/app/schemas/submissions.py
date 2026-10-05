"""Request and response contracts for coding submissions.

`user_id` is deliberately absent from every shape here. The learner is
identified by the bearer token on the request, so no submission payload, query
string, or response needs to name whose it is, and no client can address
another learner's attempts by guessing an id.

Nothing in this module describes a judge. `test_cases_passed`, `runtime_ms`,
`memory_mb`, `error_message`, and `judged_at` are written only by the judge and
are read-only here: a response reports what the judge measured, and no request
can set any of them.
"""

from datetime import datetime
from typing import Literal

from database.models.submission import (
    MAX_RUNTIME_MS,
    MAX_SOURCE_CODE_LENGTH,
    SUBMISSION_STATUS_VALUES,
    SUPPORTED_LANGUAGES,
    SubmissionStatus,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Mirrors of the backend vocabularies, so the published OpenAPI contract shows
# the allowed values. `backend/tests/test_submissions.py` asserts these stay in
# step with the model constants, which is what stops the two drifting.
SubmissionStatusInput = Literal[
    "queued",
    "running",
    "accepted",
    "wrong_answer",
    "runtime_error",
    "compilation_error",
    "time_limit_exceeded",
    "memory_limit_exceeded",
    "failed",
]
#: Built from the model's own vocabulary rather than restated, so the published
#: enum cannot name a language the submission table does not accept.
#: `backend/tests/test_submissions.py` asserts this stays in step with the model
#: constants, which is what stops the two drifting.
SupportedLanguage = Literal[*SUPPORTED_LANGUAGES]


class SubmissionCreateRequest(BaseModel):
    """Body for creating a submission.

    `extra="forbid"` is the security-relevant part: a payload carrying `user_id`,
    `status`, or any measurement field is rejected with 422 rather than silently
    ignored. That makes it impossible for a caller to file a submission as
    another learner, or to file one that already claims to be accepted.

    `status`, the test-case counts, the runtime, the memory, and the error
    message are absent by design. They are the judge's to write, and they reach
    the client only in the response the judge produced.
    """

    model_config = ConfigDict(extra="forbid")

    problem_id: int = Field(ge=1, description="Primary key of a published problem.")
    language: SupportedLanguage = Field(description="Language the source is written in.")
    source_code: str = Field(
        min_length=1,
        max_length=MAX_SOURCE_CODE_LENGTH,
        description="The learner's source. Stored as sent; run only by the judge.",
    )

    @field_validator("source_code")
    @classmethod
    def reject_blank_source(cls, value: str) -> str:
        """Reject whitespace-only source.

        The column is NOT NULL, so a blank string would otherwise be storable as
        a "submission" that contains no submission at all.
        """
        if not value.strip():
            raise ValueError("source_code must contain the learner's code.")
        return value


class SubmissionSummaryResponse(BaseModel):
    """One submission as it appears in a history list.

    The learner's own source is deliberately omitted: a list of twenty
    submissions should not carry twenty code bodies, and nothing in the history
    view needs them. The single-submission response carries it instead.
    """

    id: int
    problem_id: int
    problem_slug: str
    problem_title: str
    language: str
    status: SubmissionStatus
    test_cases_passed: int | None = None
    test_cases_total: int | None = None
    runtime_ms: int | None = Field(default=None, ge=0, le=MAX_RUNTIME_MS)
    memory_mb: int | None = Field(default=None, ge=0, le=65_536)
    error_message: str | None = None
    submitted_at: datetime
    #: When the judge answered for this submission. ``None`` on a row that was
    #: stored but never judged, which is how a client tells "queued" from
    #: "finished" without inferring it from the status alone.
    judged_at: datetime | None = None


class SubmissionDetailResponse(SubmissionSummaryResponse):
    """One submission with the learner's own source attached.

    This is the response for the create route and for a single-submission read,
    where the source is the point of the record. It is never used for a list.
    """

    source_code: str


class SubmissionListResponse(BaseModel):
    """A page of one learner's submission history.

    `total` is the count matching the filters across every page, so a client can
    render "showing 20 of 137" without a second request.
    """

    items: list[SubmissionSummaryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


__all__ = [
    "MAX_SOURCE_CODE_LENGTH",
    "SUBMISSION_STATUS_VALUES",
    "SUPPORTED_LANGUAGES",
    "SubmissionCreateRequest",
    "SubmissionDetailResponse",
    "SubmissionListResponse",
    "SubmissionStatusInput",
    "SubmissionSummaryResponse",
    "SupportedLanguage",
]
