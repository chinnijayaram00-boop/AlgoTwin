"""The AI feature's service layer: cache, rate limit, provider call, persistence.

This is where a request becomes a stored insight, and it is the only module that
knows about all four of those things at once. Everything below it is unaware of
each other on purpose -- the provider does not know about caching, the prompts do
not know about the database -- and this file is the composition.

**The order of operations is the design.** It is not incidental:

1. resolve the problem or submission, *owned by the caller*;
2. build the prompt from safe facts, deriving the cache key from the prompt itself;
3. look for a stored insight with that key and return it if present;
4. only now, charge the rate limit;
5. only now, call the provider;
6. store the result.

Steps 3 and 4 are in that order because the second is the one that would cost
money. A cache hit must never consume a learner's budget, and if the limit were
checked before the lookup then every repeat view of an already-generated answer
would push the learner towards being rate limited on the one thing they wanted. It
also means a learner who has already been shown an answer is never refused it.

Step 1 before everything else is the ownership boundary. A diagnosis is built from
a submission id in the URL, and the lookup is filtered by the authenticated
learner's id, so "not yours" and "does not exist" are the same 404. There is no code
path in this file that can load a submission without an owner to compare against.

**Stored text is never re-rendered or post-processed.** The content that goes into
the row is the string the provider returned, after the two checks that protect the
rest of the system: it must be non-empty, and it must fit the column. Both raise
before anything is written, because storing an empty insight would show a learner a
blank panel labelled as a generated explanation.

**A failure is not cached.** If the provider errors, the rate limit has already been
spent -- the call really was made -- and the learner can retry, but nothing is
written. Caching a failure would turn one provider outage into a permanent blank
panel for every request that hit it.

What this module deliberately does not do: no streaming, no background regeneration
of a stale answer, no sharing of one learner's insight with another, and no
re-generation on read. A cached answer is served until the prompt changes, which
the digest detects.
"""

from __future__ import annotations

from database.models.ai_insight import MAX_INSIGHT_CONTENT_LENGTH, AIInsight
from database.models.problem import Problem
from database.models.submission import Submission
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.ai.errors import (
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderTimeoutError,
)
from backend.app.ai.prompts import (
    RenderedPrompt,
    render_complexity_prompt,
    render_diagnosis_prompt,
    render_explanation_prompt,
)
from backend.app.ai.provider import (
    KIND_CODE_COMPLEXITY,
    AICompletionRequest,
    AIProvider,
)
from backend.app.ai.rate_limit import NullRateLimiter, RateLimiter
from backend.app.ai.redaction import (
    MAX_SUBMISSION_SOURCE_CHARS,
    MAX_USER_INPUT_CHARS,
    clip_source,
    editorial_text,
    problem_facts,
    submission_facts,
)

#: The name of the one provider that answers without a model. A response from it is
#: labelled ``is_demo_output`` so the UI can say so. Matching on the provider name
#: rather than threading a flag through is deliberate: the property belongs to the
#: provider, so it is read off the provider that answered.
DEMO_PROVIDER_NAME = "fake"

#: Complexity values a model may return when it genuinely cannot tell. Anything else
#: is accepted as written -- normalising a claimed complexity would misrepresent it.
UNDETERMINED_COMPLEXITY = "undetermined"


class InsightResult:
    """What a completed request produced: the row, and whether it was a hit.

    Returning the model row rather than a response shape keeps the mapping to the
    API in one place (:mod:`backend.app.api.routes.ai`) and keeps this module free
    of HTTP concerns.
    """

    __slots__ = ("insight", "cached")

    def __init__(self, insight: AIInsight, cached: bool) -> None:
        self.insight = insight
        self.cached = cached

    @property
    def is_demo_output(self) -> bool:
        return self.insight.provider == DEMO_PROVIDER_NAME


# ---------------------------------------------------------------------------
# limiter
# ---------------------------------------------------------------------------


#: One limiter per process, keyed by the configured limit.
#:
#: The cache must outlive a request: a limiter rebuilt per request starts every
#: request from zero counts, so it would limit nothing while looking like it limited
#: something. Keying by the limit means a test that configures a different limit gets
#: its own counters without a global reset, and two deployments in one process (a
#: real one, which is the only one in practice) share exactly the counters they
#: should.
_limiters: dict[int, RateLimiter | NullRateLimiter] = {}


def build_limiter(settings) -> RateLimiter | NullRateLimiter:
    """The process-wide limiter for this deployment.

    Constructed once per distinct configured limit and then reused, so every request
    in this process shares one set of counters.
    """
    limit = int(getattr(settings, "ai_rate_limit_per_minute", 0) or 0)
    if limit < 1:
        return NullRateLimiter()
    existing = _limiters.get(limit)
    if existing is None:
        existing = RateLimiter(limit)
        _limiters[limit] = existing
    return existing


def reset_limiters() -> None:
    """Forget every cached limiter. For tests only.

    Exists because the limiter is deliberately process-wide, which is what makes it
    work, and a test suite asserting on limits needs a way to start from zero. No
    request path calls this.
    """
    for limiter in _limiters.values():
        limiter.reset()
    _limiters.clear()


# ---------------------------------------------------------------------------
# cache and persistence
# ---------------------------------------------------------------------------


def find_cached_insight(db: Session, user_id: int, scope_key: str) -> AIInsight | None:
    """The stored insight for this exact request scope, or ``None``.

    Scoped to the learner as well as the key. The key is a digest of the prompt and
    two learners asking the identical question produce identical digests, so a
    lookup on the key alone would serve one learner's answer to another.
    """
    if not scope_key:
        return None
    statement = (
        select(AIInsight)
        .where(
            AIInsight.user_id == user_id,
            AIInsight.scope_key == scope_key,
        )
        .limit(1)
    )
    return db.execute(statement).scalars().first()


def store_insight(
    db: Session,
    *,
    user_id: int,
    prompt: RenderedPrompt,
    content: str,
    provider: str,
    model: str,
    problem_id: int | None = None,
    submission_id: int | None = None,
) -> AIInsight:
    """Persist one generated insight and return the row.

    The content is validated before the insert rather than after, because a row that
    has been committed and then found unusable is a row that has to be cleaned up
    separately. The insert is wrapped so a concurrent request that generated the same
    scope between this request's lookup and its write does not surface as a 500: the
    unique constraint catches it, and the winning row is returned instead. That is
    what makes the cache exact rather than best-effort -- a learner cannot be charged
    twice for one answer.
    """
    text = (content or "").strip()
    if not text:
        raise AIProviderError("The AI provider returned an empty completion.")
    if len(text) > MAX_INSIGHT_CONTENT_LENGTH:
        # Reported as a provider failure rather than silently trimmed: a response
        # that does not fit the column is a response this platform cannot store, and
        # a learner should be told the request failed rather than shown half of it.
        raise AIProviderError("The AI provider returned a response too large to store.")

    insight = AIInsight(
        user_id=user_id,
        kind=prompt.kind,
        problem_id=problem_id,
        submission_id=submission_id,
        scope_key=prompt.scope_key,
        content=text,
        provider=provider,
        model=model,
        grounding=prompt.grounding,
    )
    db.add(insight)
    try:
        db.commit()
    except IntegrityError:
        # The unique constraint on (user_id, scope_key) fired: another request for
        # this same scope stored an answer while this one was in flight. The stored
        # answer is the correct one to show, so it is returned instead of this one.
        db.rollback()
        existing = find_cached_insight(db, user_id, prompt.scope_key)
        if existing is not None:
            return existing
        raise
    db.refresh(insight)
    return insight


async def _generate(
    provider: AIProvider,
    prompt: RenderedPrompt,
    settings,
) -> str:
    """One provider call for one rendered prompt.

    The token budget and temperature come from settings and are already validated by
    :class:`~backend.app.core.config.Settings`, so this does not re-check them. The
    request carries the prompt verbatim: a provider is not permitted to amend it,
    because the prompt is where the redaction guarantees live.
    """
    response = await provider.complete(
        AICompletionRequest(
            kind=prompt.kind,
            system=prompt.system,
            user=prompt.user,
            max_output_tokens=int(settings.ai_max_output_tokens),
            temperature=float(settings.ai_temperature),
        )
    )
    return response.text


# ---------------------------------------------------------------------------
# the three endpoints
# ---------------------------------------------------------------------------


async def explain_problem(
    db: Session,
    *,
    user_id: int,
    problem: Problem,
    settings,
    provider: AIProvider,
    limiter: RateLimiter | NullRateLimiter,
    focus: str | None = None,
) -> InsightResult:
    """Generate or reuse an explanation of a problem's approach.

    The problem has already been resolved and its published-ness checked by the
    route; this function is about generating, not about deciding what may be
    generated.
    """
    prompt = render_explanation_prompt(
        facts=problem_facts(problem),
        editorial=editorial_text(problem),
        focus=focus,
        provider=provider.name,
        model=provider.model,
    )
    return await _resolve(
        db,
        user_id=user_id,
        prompt=prompt,
        settings=settings,
        provider=provider,
        limiter=limiter,
        problem_id=problem.id,
    )


async def diagnose_submission(
    db: Session,
    *,
    user_id: int,
    submission: Submission,
    problem: Problem,
    settings,
    provider: AIProvider,
    limiter: RateLimiter | NullRateLimiter,
) -> InsightResult:
    """Generate or reuse a diagnosis of one recorded submission.

    ``submission`` must already have been loaded *filtered by* ``user_id``. This
    function does not verify ownership and cannot: by the time it is called the row
    is loaded, and a check here would be a second, weaker gate. The single
    ownership gate is the query in the route, which is why it filters by owner rather
    than loading and comparing.
    """
    prompt = render_diagnosis_prompt(
        submission_facts=submission_facts(submission),
        problem_title=problem.title if problem is not None else "",
        language=submission.language,
        provider=provider.name,
        model=provider.model,
    )
    return await _resolve(
        db,
        user_id=user_id,
        prompt=prompt,
        settings=settings,
        provider=provider,
        limiter=limiter,
        problem_id=problem.id if problem is not None else None,
        submission_id=submission.id,
    )


async def analyse_complexity(
    db: Session,
    *,
    user_id: int,
    language: str,
    source_code: str,
    settings,
    provider: AIProvider,
    limiter: RateLimiter | NullRateLimiter,
    problem: Problem | None = None,
) -> InsightResult:
    """Generate or reuse a complexity analysis for a snippet.

    ``problem`` is optional and, when given, only contributes the catalog's target
    complexity for comparison. It changes the prompt, and therefore the scope key,
    so the same snippet analysed with and without a problem gets its own cache entry
    rather than one answer being served for two different questions.

    The source is length-checked *here* rather than only in the request schema,
    because a rejection after the prompt was built would have already spent the
    budget for this request. The check refuses rather than truncates: see
    :mod:`backend.app.ai.redaction`.
    """
    if not source_code or not source_code.strip():
        raise ValueError("source_code must contain code to analyse.")
    if len(source_code) > MAX_USER_INPUT_CHARS:
        raise ValueError(
            f"Source is too long to analyse: {len(source_code)} characters, "
            f"limit {MAX_USER_INPUT_CHARS}."
        )
    prepared = clip_source(source_code, limit=MAX_USER_INPUT_CHARS)

    prompt = render_complexity_prompt(
        source_code=prepared,
        language=language,
        expected_time_complexity=problem.expected_time_complexity if problem else None,
        expected_space_complexity=problem.expected_space_complexity if problem else None,
        provider=provider.name,
        model=provider.model,
    )
    return await _resolve(
        db,
        user_id=user_id,
        prompt=prompt,
        settings=settings,
        provider=provider,
        limiter=limiter,
        problem_id=problem.id if problem is not None else None,
    )


# ---------------------------------------------------------------------------
# the shared path
# ---------------------------------------------------------------------------


async def _resolve(
    db: Session,
    *,
    user_id: int,
    prompt: RenderedPrompt,
    settings,
    provider: AIProvider,
    limiter: RateLimiter | NullRateLimiter,
    problem_id: int | None,
    submission_id: int | None = None,
) -> InsightResult:
    """Cache lookup, then rate limit, then provider call, then store.

    The order is the point of this function; see the module docstring. Each endpoint
    above funnels into it so all three share one ordering and one set of
    guarantees, rather than three copies of the sequence that could drift.
    """
    cached = find_cached_insight(db, user_id, prompt.scope_key)
    if cached is not None:
        # Returned before the limiter is consulted. A cache hit costs nothing, so
        # charging for it would make repetition a penalty.
        return InsightResult(cached, cached=True)

    if not provider.configured:
        # Checked before the limiter so an unconfigured deployment cannot exhaust a
        # budget that no call could ever spend. The route maps this to 503.
        raise AIProviderNotConfiguredError()

    limiter.check(user_id)

    content = await _generate(provider, prompt, settings)

    insight = store_insight(
        db,
        user_id=user_id,
        prompt=prompt,
        content=content,
        provider=provider.name,
        model=provider.model,
        problem_id=problem_id,
        submission_id=submission_id,
    )
    return InsightResult(insight, cached=False)


__all__ = [
    "DEMO_PROVIDER_NAME",
    "MAX_SUBMISSION_SOURCE_CHARS",
    "UNDETERMINED_COMPLEXITY",
    "InsightResult",
    "NullRateLimiter",
    "RateLimiter",
    "analyse_complexity",
    "build_limiter",
    "diagnose_submission",
    "explain_problem",
    "find_cached_insight",
    "store_insight",
    "KIND_CODE_COMPLEXITY",
    "AIProviderTimeoutError",
]
