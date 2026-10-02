"""Grounded AI coach endpoints.

Four routes. One reports whether AI works, and three generate something grounded in
data this platform already holds.

**All three generate routes are authenticated with ``CurrentUser``.** Not because
generation is sensitive, but because every insight is stored per learner: a diagnosis
is built from a submission, and a submission belongs to somebody. Making them public
would mean either storing unattributed insights or reading a submission without an
owner to check it against. Neither is a shape this feature wants.

``GET /ai/status`` is the one exception and is deliberately public. It reads
configuration and touches no learner data, an operator needs it before login, and a
learner's frontend needs it to decide whether to offer an AI action at all rather
than letting them press a button that is guaranteed to return 503.

**The error mapping is the design.** Each failure gets the code that describes who
owns it, which is why the mapping lives in one function
(:func:`_provider_failure`) rather than being spread across three handlers:

===========================================  ======  ================================
failure                                      status  who owns it
===========================================  ======  ================================
no usable provider configured                 503     this deployment
provider answered, or could not be reached    502     the provider
provider did not answer within the budget    504     the provider, this time
learner is at their per-minute budget         429     the learner
problem or submission not found               404     the request
===========================================  ======  ================================

A timeout is checked before the generic provider error because
:class:`~backend.app.ai.errors.AIProviderTimeoutError` subclasses it: the check
order is what distinguishes 504 from 502, and a caller cannot infer "slow" from
"failed".

**The three generate routes are ``async``** because a provider call is a network
call and the previous synchronous declaration would have blocked the event loop
for the length of a model response. The rest of this router stays synchronous,
which is correct for the catalog reads.

**Nothing here composes prompts.** Each route resolves an owned row, takes the shared
provider from ``AIProviderDependency``, calls the service, and maps the result. The
grounding rules live in :mod:`backend.app.ai.redaction` and the prompt text in
:mod:`backend.app.ai.prompts`, so they cannot be bypassed by a route author and
cannot vary between the three endpoints.

The provider comes from a dependency rather than from ``AIService(settings)`` built
inline. Building one per request would resolve a provider per request, and with it a
fresh HTTP client per request: no connection reuse, and a pool left to the garbage
collector instead of closed by the application lifespan.

The complexity route optionally accepts a ``problem_id`` query parameter, and that
is the only AI route with any caller-supplied identifier beyond the path. It is
used solely to attach the catalog's target complexity for comparison, and an
unpublished or unknown problem is reported as 404 rather than ignored, so a caller
never gets an analysis that silently claims to have no reference point.
"""

import json

from fastapi import APIRouter, HTTPException, Path, Query, status

from backend.app.ai.errors import (
    AIError,
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderTimeoutError,
    AIRateLimitError,
)
from backend.app.ai.provider import KIND_CODE_COMPLEXITY
from backend.app.ai.registry import provider_status
from backend.app.api.dependencies import (
    AIProviderDependency,
    AppSettings,
    CurrentUser,
    DbSession,
)
from backend.app.schemas.ai import (
    AIComplexityRequest,
    AIComplexityResponse,
    AIExplanationRequest,
    AIInsightResponse,
    AIStatusResponse,
)
from backend.app.services import ai_service
from backend.app.services.ai_service import UNDETERMINED_COMPLEXITY
from backend.app.services.problem_service import get_published_problem_by_id
from backend.app.services.submission_service import get_submission

router = APIRouter(tags=["ai"])


def _provider_failure(error: Exception) -> HTTPException:
    """Turn any AI-layer failure into the response code that names its owner.

    Written as one function with a single ``except`` at each call site so all three
    routes cannot drift apart in their mapping. The order is significant: the timeout
    error is a subclass of the provider error, so it must be matched first or a
    timeout would be reported as a 502.
    """
    if isinstance(error, AIProviderTimeoutError):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(error)
        )
    if isinstance(error, AIProviderNotConfiguredError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        )
    if isinstance(error, AIRateLimitError):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(error),
            # The limiter computed this number; the route does not re-derive it, so
            # the advertised wait and the enforced one cannot disagree.
            headers={"Retry-After": str(error.retry_after_seconds)},
        )
    if isinstance(error, AIProviderError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error))
    raise error


async def _generate(operation):
    """Await one service coroutine and translate its failures into HTTP responses.

    Catches ``AIError``, the base of every failure the AI layer raises, rather than
    naming the subclasses. ``AIProviderNotConfiguredError`` is a *sibling* of
    ``AIProviderError`` under that base -- deliberately, since it reports that no
    upstream exists rather than that one failed -- so catching the two subclasses
    would silently drop the 503 case and let it escape as an unhandled 500. Catching
    the base means a new failure kind cannot be added without being mapped.

    Takes an already-created coroutine rather than a factory, so the ``try`` wraps the
    ``await`` and everything it raises and nothing else. The mapping lives here so a
    code added for one endpoint applies to all of them, and an unrecognised exception
    is re-raised so a genuine bug stays a 500 rather than being dressed up as a
    provider outage.
    """
    try:
        return await operation
    except AIError as error:
        raise _provider_failure(error) from error
    except ValueError as error:
        # A rejected input the schema did not catch, e.g. source that passes the
        # schema's 64 KB bound but exceeds the prompt's tighter budget.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
        ) from error


def _to_response(result: ai_service.InsightResult) -> AIInsightResponse:
    """Project a completed insight into the API shape."""
    insight = result.insight
    return AIInsightResponse(
        id=insight.id,
        kind=insight.kind,
        content=insight.content,
        provider=insight.provider,
        model=insight.model,
        grounding=dict(insight.grounding or {}),
        created_at=insight.created_at_utc,
        cached=result.cached,
        is_demo_output=result.is_demo_output,
    )


@router.get("/ai/status", response_model=AIStatusResponse)
def ai_status(settings: AppSettings) -> AIStatusResponse:
    """Whether AI generation works on this deployment.

    Every field comes from the resolved provider rather than from the settings
    object, which is the fix for the defect this endpoint used to have: it used to
    read ``AI_PROVIDER`` and ``AI_API_KEY`` directly while the service held a
    disabled provider unconditionally, so a deployment with a valid key reported
    itself ready and then failed every generation. It cannot report that any more,
    because it asks the same object a request asks.

    ``requested_provider`` is reported alongside ``provider`` so an operator can see
    a configuration mistake -- an unrecognised name that resolved to ``disabled`` --
    rather than having to infer it from a message.

    Public, and it reads no learner data. See the module docstring for why that is the
    right shape for this one route.
    """
    resolved = provider_status(settings)
    return AIStatusResponse(
        provider=resolved.provider,
        model=resolved.model,
        configured=resolved.configured,
        requested_provider=resolved.requested,
        message=resolved.reason,
    )


@router.post("/problems/{problem_id}/explanation", response_model=AIInsightResponse)
async def explain_problem(
    payload: AIExplanationRequest,
    db: DbSession,
    current_user: CurrentUser,
    settings: AppSettings,
    provider: AIProviderDependency,
    problem_id: int = Path(ge=1),
) -> AIInsightResponse:
    """Explain a published problem's intended approach.

    The request body carries no content: the statement, constraints, examples,
    target complexity, and editorial all come from the catalog by id, so a caller
    cannot introduce its own "facts" into the prompt. ``focus`` selects which part of
    the approach to centre on and cannot add anything.

    Repeating this request returns the stored answer without a provider call, and
    without spending anything from the learner's rate limit.
    """
    problem = get_published_problem_by_id(db, problem_id)
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found.")

    result = await _generate(
        ai_service.explain_problem(
            db,
            user_id=current_user.id,
            problem=problem,
            settings=settings,
            provider=provider,
            limiter=ai_service.build_limiter(settings),
            focus=payload.focus,
        )
    )
    return _to_response(result)


@router.post("/submissions/{submission_id}/diagnose", response_model=AIInsightResponse)
async def diagnose_submission(
    db: DbSession,
    current_user: CurrentUser,
    settings: AppSettings,
    provider: AIProviderDependency,
    submission_id: int = Path(ge=1),
) -> AIInsightResponse:
    """Diagnose one recorded submission.

    The lookup is filtered by the authenticated learner's id, so another learner's
    submission is indistinguishable from one that does not exist -- both 404 -- and
    there is no code path that loads a submission without an owner to compare
    against.

    The grounding is the stored verdict and its measurements: status, passed and
    total case counts, runtime, memory, and the judge's own error message. No test
    case, no expected output, and no program output is available to this route, and
    none is sent. The learner's source code is not sent either -- the request is
    about the recorded result.

    A submission that was never judged is still diagnosable, and the diagnosis says
    so: the grounding reports that no verdict was recorded rather than inventing
    one.
    """
    submission = get_submission(db, current_user.id, submission_id)
    if submission is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found."
        )

    result = await _generate(
        ai_service.diagnose_submission(
            db,
            user_id=current_user.id,
            submission=submission,
            problem=submission.problem,
            settings=settings,
            provider=provider,
            limiter=ai_service.build_limiter(settings),
        )
    )
    return _to_response(result)


@router.post("/code/complexity", response_model=AIComplexityResponse)
async def analyse_complexity(
    payload: AIComplexityRequest,
    db: DbSession,
    current_user: CurrentUser,
    settings: AppSettings,
    provider: AIProviderDependency,
    problem_id: int | None = Query(
        default=None,
        ge=1,
        description="Optional published problem, used only to attach its target complexity.",
    ),
) -> AIComplexityResponse:
    """Analyse the time and space complexity of a snippet.

    This is the only AI route that takes source code, and the only one that accepts
    a caller-supplied identifier beyond the path. ``problem_id`` is optional and
    contributes nothing but the catalog's recorded target complexity for comparison;
    it is validated as a published problem and reported as 404 when it is not, so a
    caller is never told "no reference target" when they named a problem that does
    not resolve.

    ``language`` is required rather than inferred. Guessing would answer about
    JavaScript when the learner pasted Python, and a complexity analysis in the
    wrong language is worse than none.

    The snippet is not stored. It goes into one prompt and the prompt is not stored;
    only the generated analysis is, and its ``grounding`` records the language and
    the length, not the code.
    """
    problem = None
    if problem_id is not None:
        problem = get_published_problem_by_id(db, problem_id)
        if problem is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found.")

    result = await _generate(
        ai_service.analyse_complexity(
            db,
            user_id=current_user.id,
            language=payload.language,
            source_code=payload.source_code,
            settings=settings,
            provider=provider,
            limiter=ai_service.build_limiter(settings),
            problem=problem,
        )
    )

    response = _to_response(result)
    return _complexity_response(response, problem)


def _complexity_response(
    base: AIInsightResponse, problem
) -> AIComplexityResponse:
    """Add the structured verdict to a complexity insight.

    The values are parsed out of the generated text rather than requested as a
    separate model call, and they are *not* taken from the prose as the API's
    headline answer. Two things follow from that:

    * ``reasoning`` is the whole content, so a client that only wants the claim can
      read the fields and a client that wants the argument has it verbatim;
    * a response that cannot be parsed reports ``"undetermined"`` for both
      complexities. That is the honest value -- the same one a model returns when it
      genuinely cannot tell -- and it is far better than extracting a plausible
      complexity from prose with a regular expression and presenting it as the
      model's structured claim when it is not.

    The catalog's targets are passed through from the problem, never inferred from
    the analysis. They are the catalog's claim about what a good solution looks
    like, and a client should be able to label them as such.
    """
    fields = _parse_complexity_json(base.content)
    return AIComplexityResponse(
        **base.model_dump(),
        time_complexity=fields["time_complexity"],
        space_complexity=fields["space_complexity"],
        reasoning=fields["reasoning"],
        expected_time_complexity=problem.expected_time_complexity if problem else None,
        expected_space_complexity=problem.expected_space_complexity if problem else None,
    )


def _parse_complexity_json(content: str) -> dict[str, str]:
    """Pull ``time_complexity``/``space_complexity``/``reasoning`` out of a response.

    Tolerant by necessity: a model was asked for one JSON object but models wrap
    objects in prose and code fences often enough that a strict ``json.loads`` would
    fail on real responses. The tolerance is narrow on purpose -- it strips a fence
    and finds the outermost brace-balanced object -- and everything it cannot
    understand resolves to ``"undetermined"``.

    Each value is clipped, because a model that returns a paragraph in the
    ``time_complexity`` field has not answered the question, and storing an
    unbounded paragraph there would make the structured field useless.
    """
    undetermined = {
        "time_complexity": UNDETERMINED_COMPLEXITY,
        "space_complexity": UNDETERMINED_COMPLEXITY,
        "reasoning": "",
    }
    candidate = _extract_json_object(content)
    if candidate is None:
        return undetermined
    try:
        parsed = json.loads(candidate)
    except (ValueError, TypeError):
        return undetermined
    if not isinstance(parsed, dict):
        return undetermined

    result = dict(undetermined)
    for key in ("time_complexity", "space_complexity"):
        value = parsed.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = " ".join(value.split())[:120]
    reasoning = parsed.get("reasoning")
    if isinstance(reasoning, str) and reasoning.strip():
        result["reasoning"] = " ".join(reasoning.split())[:2_000]
    return result


def _extract_json_object(text: str) -> str | None:
    """The first brace-balanced object in ``text``, or ``None``.

    Scans for the first ``{`` and returns the substring up to its matching ``}``,
    counting braces while ignoring any that appear inside a JSON string -- a
    ``reasoning`` value containing a brace would otherwise end the object early and
    produce a fragment that fails to parse.
    """
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


__all__ = ["KIND_CODE_COMPLEXITY", "router"]
