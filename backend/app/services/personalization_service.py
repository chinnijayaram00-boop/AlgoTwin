"""Deterministic learner profile, and grounded mentor guidance built from it.

The profile answers *"what should this learner work on, and why?"* and it
answers it the same way every time. It is assembled from computations the
platform already trusts -- :func:`backend.app.services.analytics_service.load_summary`
and :func:`backend.app.services.learning_path_service.load_learning_path` -- so
the coach can never disagree with the analytics page about a count or with the
learning path page about what comes next. Nothing here is estimated and nothing
here is model-authored: a strength is a fact about stored rows, and a weakness
is the same fact read from the other side.

Mentor guidance is the one part that *may* involve a model, and it is layered
strictly on top of the deterministic profile:

* if the deployment has no usable provider, the learner still gets guidance,
  written from the profile by :func:`build_mentor_fallback`;
* if the provider is at its limit, or fails, or times out, the same fallback is
  served rather than an error -- a learner asking for advice should get advice;
* only when a provider answers does its text replace the fallback, and the
  response says so through ``fallback`` and ``degraded_reason``.

The guidance is deliberately not persisted. Advice about "what to do next" is a
statement about the learner's state *now*; caching it under a digest would keep
serving yesterday's advice after today's work, which is the opposite of what a
coach is for. The route recomputes the profile on every request, and the
provider is charged only when a provider is actually called.

Ownership follows the rest of the learner-scoped services exactly: the caller's
``user_id`` comes from the bearer token and every read is filtered by it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from database.models.progress import ProgressStatus
from sqlalchemy.orm import Session

from backend.app.ai.errors import (
    AIProviderError,
    AIProviderTimeoutError,
    AIRateLimitError,
)
from backend.app.ai.prompts import render_mentor_prompt
from backend.app.ai.provider import AICompletionRequest, AIProvider
from backend.app.ai.rate_limit import NullRateLimiter, RateLimiter
from backend.app.ai.redaction import clip
from backend.app.schemas.analytics import AnalyticsSummaryResponse
from backend.app.schemas.learning_path import REASON_CONTINUE_STAGE, LearningPathResponse
from backend.app.schemas.personalization import (
    DEFAULT_MENTOR_FOCUS,
    DEGRADED_PROVIDER_ERROR,
    DEGRADED_PROVIDER_NOT_CONFIGURED,
    DEGRADED_PROVIDER_TIMEOUT,
    DEGRADED_RATE_LIMITED,
    MAX_FOCUS_AREAS,
    MAX_RECOMMENDATIONS,
    MAX_SIGNALS,
    STRENGTH_DIFFICULTY_MASTERY,
    STRENGTH_HIGH_ACCEPTANCE,
    STRENGTH_INTERVIEW_PERFORMANCE,
    STRENGTH_PRACTICE_STREAK,
    STRENGTH_SOLVED_VOLUME,
    STRENGTH_TOPIC_MASTERY,
    WEAKNESS_INTERVIEW_QUESTIONS,
    WEAKNESS_LOW_ACCEPTANCE,
    WEAKNESS_NO_SUBMISSIONS,
    WEAKNESS_NOT_STARTED,
    WEAKNESS_UNFINISHED_ATTEMPTS,
    WEAKNESS_WEAK_TOPICS,
    FocusArea,
    PersonalizationProfileResponse,
    PersonalizationRecommendation,
    ProfileOverview,
    ProfileSignal,
)
from backend.app.services import analytics_service, learning_path_service
from backend.app.services.ai_service import DEMO_PROVIDER_NAME

#: The provider and model the fallback reports. They name a real thing -- this
#: module, which derived the text from stored rows -- rather than borrowing the
#: configured model's name, which would attribute rules-based prose to a model
#: that never saw the request.
FALLBACK_PROVIDER_NAME = "deterministic"
FALLBACK_MODEL_NAME = "profile-rules"

#: Thresholds that turn a measurement into a signal. Named so the tests assert
#: on the same numbers the prose is derived from, and so an operator can see the
#: one place to change a definition of "strong" or "struggling".
HIGH_ACCEPTANCE_RATE = 60.0
LOW_ACCEPTANCE_RATE = 50.0
MIN_PRACTICE_STREAK_DAYS = 2
MIN_INTERVIEW_SCORE = 60.0

#: The one-line emphasis appended to each fallback body, selected by focus. A
#: closed map, so an unknown focus degrades to the overview line rather than
#: being interpolated.
_FOCUS_EMPHASIS: dict[str, str] = {
    "overview": "Work the next step above before adding breadth.",
    "strengths": "Lean into the strengths above and pick a problem that exercises them.",
    "weaknesses": "Address the weaknesses above one small, consistent step at a time.",
    "next_steps": "Start the next step above today, while the context is fresh.",
}


@dataclass
class MentorGuidanceResult:
    """One mentor response, whether it came from a model or from the rules.

    Returning a small result rather than a response model keeps the HTTP
    mapping in the route, where every other route keeps it, and lets the service
    stay free of FastAPI types.
    """

    focus: str
    content: str
    provider: str
    model: str
    grounding: dict[str, Any]
    fallback: bool
    degraded_reason: str | None
    is_demo_output: bool


# ------------------------------------------------------------------- profile


def _overview(summary: AnalyticsSummaryResponse) -> ProfileOverview:
    """The headline counts, lifted from the analytics summary unchanged.

    Lifted rather than recomputed: the analytics overview is already the
    platform's one answer to "how is this learner doing", and a second
    implementation here would be a second answer that could drift.
    """
    overview = summary.overview
    interviews = summary.interviews
    return ProfileOverview(
        total_problems=overview.total_problems,
        solved=overview.solved,
        attempted=overview.attempted,
        not_started=overview.not_started,
        completion_percentage=overview.completion_percentage,
        current_streak_days=overview.current_streak_days,
        total_submissions=overview.total_submissions,
        judged_submissions=overview.judged_submissions,
        accepted_submissions=overview.accepted_submissions,
        acceptance_rate=overview.acceptance_rate,
        problems_submitted=overview.problems_submitted,
        interviews_completed=interviews.completed,
        questions_answered=interviews.questions_answered,
        questions_accepted=interviews.questions_accepted,
        average_interview_score=interviews.average_score,
    )


def build_strengths(summary: AnalyticsSummaryResponse) -> list[ProfileSignal]:
    """The signals the recorded evidence supports, most general first.

    Each signal is only produced when its evidence exists, so a fresh learner
    gets an empty list rather than a hollow compliment. The list is capped, and
    because the difficulty and topic rows are already in a stable order the cap
    selects the same signals on every read.
    """
    overview = summary.overview
    signals: list[ProfileSignal] = []

    if overview.solved > 0:
        signals.append(
            ProfileSignal(
                code=STRENGTH_SOLVED_VOLUME,
                title="Problem-solving momentum",
                detail=(
                    f"You have solved {overview.solved} of {overview.total_problems} "
                    "published problems."
                ),
                evidence=(
                    f"{overview.solved}/{overview.total_problems} solved "
                    f"({overview.completion_percentage}%)"
                ),
            )
        )

    if overview.judged_submissions > 0 and overview.acceptance_rate >= HIGH_ACCEPTANCE_RATE:
        signals.append(
            ProfileSignal(
                code=STRENGTH_HIGH_ACCEPTANCE,
                title="Strong acceptance rate",
                detail=(
                    f"{overview.accepted_submissions} of {overview.judged_submissions} "
                    "judged submissions were accepted."
                ),
                evidence=f"{overview.acceptance_rate}% accepted",
            )
        )

    if overview.current_streak_days >= MIN_PRACTICE_STREAK_DAYS:
        signals.append(
            ProfileSignal(
                code=STRENGTH_PRACTICE_STREAK,
                title="Consistent practice",
                detail=(
                    f"You have recorded activity on {overview.current_streak_days} "
                    "consecutive days."
                ),
                evidence=f"{overview.current_streak_days}-day streak",
            )
        )

    # One difficulty and up to two topic masteries: enough to be encouraging
    # without letting a short catalog dominate the list.
    for row in summary.difficulty:
        if row.total > 0 and row.solved == row.total:
            signals.append(
                ProfileSignal(
                    code=STRENGTH_DIFFICULTY_MASTERY,
                    title=f"Mastered every {row.difficulty} problem",
                    detail=f"You have solved all {row.total} {row.difficulty} problems in the catalog.",
                    evidence=f"{row.solved}/{row.total} {row.difficulty}",
                )
            )
            break

    mastered_topics = [row for row in summary.topics if row.total > 0 and row.solved == row.total]
    for row in mastered_topics[:2]:
        signals.append(
            ProfileSignal(
                code=STRENGTH_TOPIC_MASTERY,
                title=f"Mastered {row.topic}",
                detail=f"You have solved every published {row.topic} problem.",
                evidence=f"{row.solved}/{row.total} {row.topic}",
            )
        )

    interviews = summary.interviews
    if (
        interviews.completed > 0
        and interviews.average_score is not None
        and interviews.average_score >= MIN_INTERVIEW_SCORE
    ):
        signals.append(
            ProfileSignal(
                code=STRENGTH_INTERVIEW_PERFORMANCE,
                title="Interview-ready performance",
                detail=(
                    f"You averaged {interviews.average_score}% across "
                    f"{interviews.completed} completed mock interview(s)."
                ),
                evidence=f"average score {interviews.average_score}%",
            )
        )

    return signals[:MAX_SIGNALS]


def build_weaknesses(
    summary: AnalyticsSummaryResponse, weak_topics: list[str]
) -> list[ProfileSignal]:
    """The signals that point at work still owed, in rough priority order.

    ``weak_topics`` is the learning path's own computation of "started but not
    finished", passed in so the two features name the same topics.
    """
    overview = summary.overview
    signals: list[ProfileSignal] = []

    if overview.solved == 0 and overview.attempted == 0 and overview.total_submissions == 0:
        signals.append(
            ProfileSignal(
                code=WEAKNESS_NOT_STARTED,
                title="No activity recorded yet",
                detail="Solve or attempt a problem to start building your coaching profile.",
                evidence="0 problems touched",
            )
        )

    if overview.attempted > 0:
        signals.append(
            ProfileSignal(
                code=WEAKNESS_UNFINISHED_ATTEMPTS,
                title="Unfinished attempts",
                detail=f"{overview.attempted} problem(s) are started but not yet solved.",
                evidence=f"{overview.attempted} attempted, unsolved",
            )
        )

    if overview.judged_submissions > 0 and overview.acceptance_rate < LOW_ACCEPTANCE_RATE:
        signals.append(
            ProfileSignal(
                code=WEAKNESS_LOW_ACCEPTANCE,
                title="Acceptance rate below 50%",
                detail=(
                    f"Only {overview.accepted_submissions} of "
                    f"{overview.judged_submissions} judged submissions were accepted."
                ),
                evidence=f"{overview.acceptance_rate}% accepted",
            )
        )

    if overview.total_submissions == 0 and (overview.solved > 0 or overview.attempted > 0):
        signals.append(
            ProfileSignal(
                code=WEAKNESS_NO_SUBMISSIONS,
                title="No judge submissions yet",
                detail="You have marked progress but have not sent code to the judge.",
                evidence="0 submissions",
            )
        )

    if weak_topics:
        signals.append(
            ProfileSignal(
                code=WEAKNESS_WEAK_TOPICS,
                title="Topics to shore up",
                detail="You have started but not finished: " + ", ".join(weak_topics) + ".",
                evidence=", ".join(weak_topics),
            )
        )

    interviews = summary.interviews
    if (
        interviews.questions_answered > 0
        and interviews.questions_accepted < interviews.questions_answered
        and interviews.questions_accepted / interviews.questions_answered < 0.5
    ):
        signals.append(
            ProfileSignal(
                code=WEAKNESS_INTERVIEW_QUESTIONS,
                title="Interview questions need work",
                detail=(
                    f"You accepted {interviews.questions_accepted} of "
                    f"{interviews.questions_answered} answered interview questions."
                ),
                evidence=(
                    f"{interviews.questions_accepted}/{interviews.questions_answered} accepted"
                ),
            )
        )

    return signals[:MAX_SIGNALS]


def _recommendation(
    problem, reason_code: str, reason: str, priority: int
) -> PersonalizationRecommendation:
    """Project one learning-path problem into the coach's recommendation shape."""
    return PersonalizationRecommendation(
        problem_id=problem.problem_id,
        slug=problem.slug,
        title=problem.title,
        difficulty=problem.difficulty,
        topics=list(problem.topics),
        primary_topic=problem.primary_topic,
        status=problem.status,
        reason_code=reason_code,
        reason=reason,
        priority=priority,
    )


def build_recommendations(path: LearningPathResponse) -> list[PersonalizationRecommendation]:
    """The next few problems to try, all inside the learner's current stage.

    The first entry is the learning path's own recommendation, reason and all.
    The rest are the other unsolved problems in the same stage, in the stage's
    Easy-to-Hard order, so following the list never pulls a learner out of the
    stage they are standing in.
    """
    if path.current_stage_index is None:
        return []
    stage = path.stages[path.current_stage_index]
    recommendations: list[PersonalizationRecommendation] = []
    seen: set[int] = set()

    if path.recommendation is not None:
        primary = path.recommendation
        recommendations.append(
            _recommendation(primary.problem, primary.reason_code, primary.reason, primary.score)
        )
        seen.add(primary.problem.problem_id)

    for problem in stage.problems:
        if len(recommendations) >= MAX_RECOMMENDATIONS:
            break
        if problem.problem_id in seen or problem.status == ProgressStatus.SOLVED:
            continue
        recommendations.append(
            _recommendation(
                problem,
                REASON_CONTINUE_STAGE,
                f"Continue your {stage.title} progression.",
                0,
            )
        )
        seen.add(problem.problem_id)

    return recommendations


def build_focus_areas(summary: AnalyticsSummaryResponse) -> list[FocusArea]:
    """Topics ordered weakest-first, then largest-first.

    Every catalog topic is a candidate, including ones the learner has not
    touched -- an untouched topic at 0% is a genuine place to focus. Sorting by
    completion, then by size descending, surfaces the biggest untouched areas
    before the small ones.
    """
    ordered = sorted(
        summary.topics,
        key=lambda row: (row.completion_percentage, -row.total, row.topic),
    )
    return [
        FocusArea(
            topic=row.topic,
            solved=row.solved,
            attempted=row.attempted,
            total=row.total,
            completion_percentage=row.completion_percentage,
        )
        for row in ordered[:MAX_FOCUS_AREAS]
    ]


def build_profile(
    summary: AnalyticsSummaryResponse, path: LearningPathResponse
) -> PersonalizationProfileResponse:
    """Assemble the whole profile from already-computed analytics and a path.

    Pure by construction: it reads the two objects it is handed and nothing
    else, which is what lets the tests drive it without a database or a token.
    """
    return PersonalizationProfileResponse(
        overview=_overview(summary),
        strengths=build_strengths(summary),
        weaknesses=build_weaknesses(summary, list(path.weak_topics)),
        recommendations=build_recommendations(path),
        focus_areas=build_focus_areas(summary),
        as_of=summary.as_of,
    )


def load_profile(session: Session, user_id: int) -> PersonalizationProfileResponse:
    """Build the profile for one learner from the database.

    Both underlying services filter by ``user_id`` themselves, so this is the
    only identity the profile can be built from.
    """
    summary = analytics_service.load_summary(session, user_id)
    path = learning_path_service.load_learning_path(session, user_id)
    return build_profile(summary, path)


# -------------------------------------------------------------------- mentor


def mentor_facts(profile: PersonalizationProfileResponse) -> dict[str, Any]:
    """The safe, bounded grounding for a mentor prompt.

    Counts are passed as integers -- there is nothing to disclose in "3 of 50"
    -- and every string is a catalog topic, a signal title, or the learning
    path's own reason sentence, each clipped. No test case, expected output,
    program output, source code, or reference solution is reachable from a
    profile, so none can reach a prompt.
    """
    overview = profile.overview
    primary = profile.recommendations[0] if profile.recommendations else None
    return {
        "solved": overview.solved,
        "total_problems": overview.total_problems,
        "completion_percentage": overview.completion_percentage,
        "attempted": overview.attempted,
        "not_started": overview.not_started,
        "current_streak_days": overview.current_streak_days,
        "total_submissions": overview.total_submissions,
        "judged_submissions": overview.judged_submissions,
        "accepted_submissions": overview.accepted_submissions,
        "acceptance_rate": overview.acceptance_rate,
        "interviews_completed": overview.interviews_completed,
        "average_interview_score": overview.average_interview_score,
        "strengths": [clip(signal.title, 120) for signal in profile.strengths][:MAX_SIGNALS],
        "weaknesses": [clip(signal.title, 120) for signal in profile.weaknesses][:MAX_SIGNALS],
        "focus_areas": [clip(area.topic, 60) for area in profile.focus_areas][:MAX_FOCUS_AREAS],
        "recommended_problem": clip(primary.title, 200) if primary else None,
        "recommended_reason": clip(primary.reason, 300) if primary else None,
        "recommended_reason_code": primary.reason_code if primary else None,
    }


def build_mentor_fallback(profile: PersonalizationProfileResponse, focus: str) -> str:
    """Deterministic coaching written from the profile alone.

    This is the answer when no model is available, and it is deliberately
    complete: it states where the learner stands, what they are doing well, what
    needs attention, where to focus, and what to do next. A learner who never
    reaches a provider still gets a useful reply.

    The text is a pure function of the profile and ``focus``, so a test can
    assert on it exactly and a second read of the same state returns the same
    words.
    """
    overview = profile.overview
    lines: list[str] = [
        "## Where you stand",
        "",
        f"You have solved **{overview.solved} of {overview.total_problems}** published "
        f"problems ({overview.completion_percentage}%), with {overview.attempted} started "
        "but unfinished.",
    ]
    if overview.judged_submissions:
        lines.append(
            f"Across {overview.judged_submissions} judged submissions your acceptance rate "
            f"is **{overview.acceptance_rate}%**."
        )
    if overview.current_streak_days:
        lines.append(f"You are on a {overview.current_streak_days}-day practice streak.")

    lines += ["", "## Strengths"]
    lines += [f"- **{signal.title}** — {signal.detail}" for signal in profile.strengths] or [
        "- No strengths recorded yet — your first solved problem will change that."
    ]

    lines += ["", "## Worth your attention"]
    lines += [f"- **{signal.title}** — {signal.detail}" for signal in profile.weaknesses] or [
        "- Nothing is standing out yet; keep building the record."
    ]

    if profile.focus_areas:
        areas = "; ".join(f"{area.topic} ({area.solved}/{area.total})" for area in profile.focus_areas)
        lines += ["", "## Focus areas", f"- {areas}"]

    lines += ["", "## Next step"]
    if profile.recommendations:
        top = profile.recommendations[0]
        lines.append(f"Start with **{top.title}** ({top.difficulty}) — {top.reason}")
        for extra in profile.recommendations[1:3]:
            lines.append(f"Then try **{extra.title}** ({extra.difficulty}).")
    else:
        lines.append(
            "Every published problem is solved. Keep the edge sharp with mock interviews "
            "and re-solving by pattern."
        )

    lines += ["", f"_{_FOCUS_EMPHASIS.get(focus, _FOCUS_EMPHASIS[DEFAULT_MENTOR_FOCUS])}_"]
    return "\n".join(lines)


def _fallback_result(
    profile: PersonalizationProfileResponse,
    focus: str,
    facts: dict[str, Any],
    reason: str,
) -> MentorGuidanceResult:
    """Package the deterministic fallback, with the reason it was used."""
    return MentorGuidanceResult(
        focus=focus,
        content=build_mentor_fallback(profile, focus),
        provider=FALLBACK_PROVIDER_NAME,
        model=FALLBACK_MODEL_NAME,
        grounding={**facts, "fallback": True, "degraded_reason": reason},
        fallback=True,
        degraded_reason=reason,
        is_demo_output=False,
    )


async def generate_mentor_guidance(
    *,
    user_id: int,
    profile: PersonalizationProfileResponse,
    settings,
    provider: AIProvider,
    limiter: RateLimiter | NullRateLimiter,
    focus: str | None = None,
) -> MentorGuidanceResult:
    """Grounded coaching, or the deterministic fallback -- never an error.

    The sequence mirrors :mod:`backend.app.services.ai_service`: an unconfigured
    provider is refused before the limiter is consulted (so a switched-off
    deployment cannot exhaust a budget nobody can spend), the limiter is charged
    before the call, and every provider failure returns the fallback instead of
    propagating. The difference is the last step: the free path is always
    available, so a rate-limited learner gets rules-based advice rather than a
    429, and the response names that outcome instead of hiding it.
    """
    resolved_focus = focus or DEFAULT_MENTOR_FOCUS
    facts = mentor_facts(profile)

    if not provider.configured:
        return _fallback_result(
            profile, resolved_focus, facts, DEGRADED_PROVIDER_NOT_CONFIGURED
        )

    try:
        limiter.check(user_id)
    except AIRateLimitError:
        return _fallback_result(profile, resolved_focus, facts, DEGRADED_RATE_LIMITED)

    prompt = render_mentor_prompt(
        profile=facts,
        focus=resolved_focus,
        provider=provider.name,
        model=provider.model,
    )
    request = AICompletionRequest(
        kind=prompt.kind,
        system=prompt.system,
        user=prompt.user,
        max_output_tokens=int(settings.ai_max_output_tokens),
        temperature=float(settings.ai_temperature),
    )

    try:
        response = await provider.complete(request)
    except AIProviderTimeoutError:
        return _fallback_result(profile, resolved_focus, facts, DEGRADED_PROVIDER_TIMEOUT)
    except AIProviderError:
        return _fallback_result(profile, resolved_focus, facts, DEGRADED_PROVIDER_ERROR)

    return MentorGuidanceResult(
        focus=resolved_focus,
        content=response.text,
        provider=response.provider,
        model=response.model,
        grounding=prompt.grounding,
        fallback=False,
        degraded_reason=None,
        is_demo_output=response.provider == DEMO_PROVIDER_NAME,
    )


__all__ = [
    "FALLBACK_MODEL_NAME",
    "FALLBACK_PROVIDER_NAME",
    "HIGH_ACCEPTANCE_RATE",
    "LOW_ACCEPTANCE_RATE",
    "MIN_INTERVIEW_SCORE",
    "MIN_PRACTICE_STREAK_DAYS",
    "MentorGuidanceResult",
    "build_focus_areas",
    "build_mentor_fallback",
    "build_profile",
    "build_recommendations",
    "build_strengths",
    "build_weaknesses",
    "generate_mentor_guidance",
    "load_profile",
    "mentor_facts",
]
