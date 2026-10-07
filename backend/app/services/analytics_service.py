"""Learner analytics: real calculations over one learner's persisted rows.

Two rules hold everywhere in this module, matching every other learner-scoped
service in the codebase:

* the caller supplies ``user_id``, and it is the id resolved from the bearer
  token by ``get_current_user`` -- never a value from the request body, query
  string, or path, so no request can address another learner's analytics;
* every read is filtered by that ``user_id`` (or, for the catalog, by
  ``is_published``), so two learners working side by side get entirely separate
  summaries from the same endpoint.

What is computed, and from what
-------------------------------

============================  ==============================================
Section                       Evidence
============================  ==============================================
overview                      published catalog + progress rows + submissions
difficulty / topic breakdown  published catalog + progress rows + submissions
verdicts                      submission statuses, normalized on read
activity                      ``submitted_at`` / ``last_attempted_at`` /
                              ``solved_at`` timestamps, zero-filled daily
learning path                 the real ``build_learning_path`` computation
interviews                    interview sessions, questions, linked verdicts
============================  ==============================================

Nothing here is estimated. A rate is a division of two counts that are both
reported beside it, an average is taken only over rows that carry a
measurement, and a timestamp-derived number (streak, activity) comes from
stored timestamps alone. Where no evidence exists the field is ``None`` or
``0.0``: an empty history reads as an empty history, never as a plausible
default.

The computation is split in two on purpose. :func:`build_summary` is a pure
function of already-fetched rows -- which is what lets the tests drive it with
plain objects and assert on the arithmetic without a database or a token --
and :func:`load_summary` only fetches those rows.
"""

from datetime import date, timedelta

from database.models import InterviewQuestion, InterviewSession, Problem, Progress, Submission
from database.models.interview import ACTIVE_INTERVIEW_STATUSES, InterviewStatus
from database.models.progress import ProgressStatus, as_utc, normalize_status, utc_now
from database.models.submission import (
    PENDING_SUBMISSION_STATUSES,
    SubmissionStatus,
    normalize_submission_status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.schemas.analytics import (
    DEFAULT_ACTIVITY_DAYS,
    DIFFICULTY_ORDER,
    MAX_ACTIVITY_DAYS,
    MIN_ACTIVITY_DAYS,
    ActivityDay,
    AnalyticsOverview,
    AnalyticsSummaryResponse,
    DifficultyAnalytics,
    InterviewAnalytics,
    InterviewScorePoint,
    LearningPathAnalytics,
    LearningPathStageAnalytics,
    TopicAnalytics,
    VerdictAnalytics,
)
from backend.app.services import learning_path_service, progress_service


def _topics_of(problem: Problem) -> list[str]:
    """The topic labels of a problem, defensively typed.

    The same coercion the progress and learning path services use, because
    ``Problem.topics`` is a JSON column: whatever the database holds, the
    summary has to make a decision from it rather than raise.
    """
    topics = problem.topics
    if not isinstance(topics, list):
        return []
    return [str(topic) for topic in topics if isinstance(topic, (str, int, float))]


def clamp_activity_days(days: int) -> int:
    """Bound a requested activity window to the range the API promises."""
    return min(max(int(days), MIN_ACTIVITY_DAYS), MAX_ACTIVITY_DAYS)


# ------------------------------------------------------------------ overview


def _submission_totals(submissions: list[Submission]) -> dict[str, object]:
    """Counts and measurement averages across one learner's submissions."""
    total = len(submissions)
    judged = 0
    accepted = 0
    runtimes: list[int] = []
    memories: list[int] = []
    for submission in submissions:
        status = normalize_submission_status(submission.status)
        if status in PENDING_SUBMISSION_STATUSES:
            continue
        judged += 1
        if status == SubmissionStatus.ACCEPTED.value:
            accepted += 1
        if submission.runtime_ms is not None:
            runtimes.append(int(submission.runtime_ms))
        if submission.memory_mb is not None:
            memories.append(int(submission.memory_mb))
    return {
        "total": total,
        "judged": judged,
        "accepted": accepted,
        "acceptance_rate": round(accepted / judged * 100, 2) if judged else 0.0,
        "problems_submitted": len({submission.problem_id for submission in submissions}),
        "average_runtime_ms": round(sum(runtimes) / len(runtimes), 2) if runtimes else None,
        "average_memory_mb": round(sum(memories) / len(memories), 2) if memories else None,
    }


def build_overview(
    problems: list[Problem],
    progress_rows: list[Progress],
    submissions: list[Submission],
    today: date | None = None,
) -> AnalyticsOverview:
    """The headline numbers for one learner.

    The catalog is the denominator for the first half, so a learner who has
    done nothing yet gets real zeros against a real total instead of an empty
    object; the second half counts submissions, and its rate is over judged
    rows only.
    """
    status_by_problem = {row.problem_id: normalize_status(row.status) for row in progress_rows}

    solved = 0
    attempted = 0
    for problem in problems:
        status = status_by_problem.get(problem.id)
        if status == ProgressStatus.SOLVED.value:
            solved += 1
        elif status == ProgressStatus.ATTEMPTED.value:
            attempted += 1

    total = len(problems)
    totals = _submission_totals(submissions)
    return AnalyticsOverview(
        total_problems=total,
        solved=solved,
        attempted=attempted,
        not_started=max(total - solved - attempted, 0),
        completion_percentage=round(solved / total * 100, 2) if total else 0.0,
        current_streak_days=progress_service.current_streak_days(progress_rows, today=today),
        total_submissions=totals["total"],
        judged_submissions=totals["judged"],
        accepted_submissions=totals["accepted"],
        acceptance_rate=totals["acceptance_rate"],
        problems_submitted=totals["problems_submitted"],
        average_runtime_ms=totals["average_runtime_ms"],
        average_memory_mb=totals["average_memory_mb"],
    )


# --------------------------------------------------------------- breakdowns


def _difficulty_order(values: set[str]) -> list[str]:
    """Known difficulties in teaching order first, unknown ones after, a-z."""
    known = [level for level in DIFFICULTY_ORDER if level in values]
    unknown = sorted(values.difference(DIFFICULTY_ORDER))
    return known + unknown


def build_difficulty_breakdown(
    problems: list[Problem],
    progress_rows: list[Progress],
    submissions: list[Submission],
    difficulty_by_problem: dict[int, str],
) -> list[DifficultyAnalytics]:
    """Per-difficulty catalog standing and submission performance.

    A tier the catalog does not contain but the learner has submitted to still
    gets a row (with ``total=0``) rather than vanishing, and the three catalog
    tiers always appear first in teaching order.
    """
    status_by_problem = {row.problem_id: normalize_status(row.status) for row in progress_rows}

    totals: dict[str, int] = {}
    solved_by: dict[str, int] = {}
    attempted_by: dict[str, int] = {}
    for problem in problems:
        level = problem.difficulty
        totals[level] = totals.get(level, 0) + 1
        status = status_by_problem.get(problem.id)
        if status == ProgressStatus.SOLVED.value:
            solved_by[level] = solved_by.get(level, 0) + 1
        elif status == ProgressStatus.ATTEMPTED.value:
            attempted_by[level] = attempted_by.get(level, 0) + 1

    submissions_by: dict[str, int] = {}
    judged_by: dict[str, int] = {}
    accepted_by: dict[str, int] = {}
    for submission in submissions:
        level = difficulty_by_problem.get(submission.problem_id)
        if level is None:
            continue
        submissions_by[level] = submissions_by.get(level, 0) + 1
        status = normalize_submission_status(submission.status)
        if status in PENDING_SUBMISSION_STATUSES:
            continue
        judged_by[level] = judged_by.get(level, 0) + 1
        if status == SubmissionStatus.ACCEPTED.value:
            accepted_by[level] = accepted_by.get(level, 0) + 1

    levels = set(totals) | set(submissions_by)
    rows: list[DifficultyAnalytics] = []
    for level in _difficulty_order(levels):
        total = totals.get(level, 0)
        solved = solved_by.get(level, 0)
        attempted = attempted_by.get(level, 0)
        judged = judged_by.get(level, 0)
        accepted = accepted_by.get(level, 0)
        rows.append(
            DifficultyAnalytics(
                difficulty=level,
                total=total,
                solved=solved,
                attempted=attempted,
                not_started=max(total - solved - attempted, 0),
                completion_percentage=round(solved / total * 100, 2) if total else 0.0,
                submissions=submissions_by.get(level, 0),
                judged=judged,
                accepted=accepted,
                acceptance_rate=round(accepted / judged * 100, 2) if judged else 0.0,
            )
        )
    return rows


def build_topic_breakdown(
    problems: list[Problem], progress_rows: list[Progress]
) -> list[TopicAnalytics]:
    """Per-topic catalog standing, alphabetically ordered and totalled.

    A problem may carry several topics, so the rows sum to more than the
    catalog size -- the same convention the progress summary uses, so the two
    cannot disagree about what a topic count means.
    """
    status_by_problem = {row.problem_id: normalize_status(row.status) for row in progress_rows}

    totals: dict[str, int] = {}
    solved_by: dict[str, int] = {}
    attempted_by: dict[str, int] = {}
    for problem in problems:
        status = status_by_problem.get(problem.id)
        for topic in _topics_of(problem):
            totals[topic] = totals.get(topic, 0) + 1
            if status == ProgressStatus.SOLVED.value:
                solved_by[topic] = solved_by.get(topic, 0) + 1
            elif status == ProgressStatus.ATTEMPTED.value:
                attempted_by[topic] = attempted_by.get(topic, 0) + 1

    rows: list[TopicAnalytics] = []
    for topic in sorted(totals):
        total = totals[topic]
        solved = solved_by.get(topic, 0)
        attempted = attempted_by.get(topic, 0)
        rows.append(
            TopicAnalytics(
                topic=topic,
                total=total,
                solved=solved,
                attempted=attempted,
                not_started=max(total - solved - attempted, 0),
                completion_percentage=round(solved / total * 100, 2) if total else 0.0,
            )
        )
    return rows


def build_verdict_breakdown(submissions: list[Submission]) -> list[VerdictAnalytics]:
    """Counts per verdict, most frequent first, over the learner's history.

    The status is normalized on read, so a legacy label the vocabulary cannot
    express is counted as ``failed`` exactly as every other reader counts it.
    Slices with no rows are omitted rather than reported as zeros: a chart with
    seven zero-width wedges teaches nothing, and the totals are already in the
    overview.
    """
    total = len(submissions)
    if total == 0:
        return []
    counts: dict[str, int] = {}
    for submission in submissions:
        status = normalize_submission_status(submission.status)
        counts[status] = counts.get(status, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [
        VerdictAnalytics(
            status=status,
            count=count,
            percentage=round(count / total * 100, 2),
        )
        for status, count in ordered
    ]


# ------------------------------------------------------------------ activity


def build_activity(
    progress_rows: list[Progress],
    submissions: list[Submission],
    days: int,
    today: date | None = None,
) -> list[ActivityDay]:
    """A zero-filled daily series over the requested window.

    Every entry is a real calendar day ending ``today``, so the axis is
    continuous and a quiet day reads as a zero rather than as a gap. Timestamps
    outside the window -- older history, or a clock that ran ahead -- are
    ignored rather than bent into range.
    """
    window_days = clamp_activity_days(days)
    end = today or utc_now().date()
    start = end - timedelta(days=window_days - 1)
    series = {
        offset: ActivityDay(date=start + timedelta(days=offset))
        for offset in range(window_days)
    }

    def offset_for(stamp) -> int | None:
        if stamp is None:
            return None
        day = stamp.date()
        if day < start or day > end:
            return None
        return (day - start).days

    for submission in submissions:
        offset = offset_for(as_utc(submission.submitted_at))
        if offset is not None:
            series[offset].submissions += 1

    for row in progress_rows:
        attempt_offset = offset_for(as_utc(row.last_attempted_at))
        if attempt_offset is not None:
            series[attempt_offset].attempts += 1
        solve_offset = offset_for(as_utc(row.solved_at))
        if solve_offset is not None:
            series[solve_offset].solves += 1

    return [series[offset] for offset in range(window_days)]


# ------------------------------------------------------------- learning path


def build_learning_path_analytics(
    problems: list[Problem],
    progress_rows: list[Progress],
) -> LearningPathAnalytics:
    """The learning path, projected down to its headline numbers.

    The computation is the real one -- :func:`learning_path_service.build_
    learning_path`, the same call ``/learning-path`` makes -- so the analytics
    page cannot drift from the path page about the current stage, the weak
    topics, or the recommendation.
    """
    published_ids = {problem.id for problem in problems}
    progress_by_problem = {
        row.problem_id: row for row in progress_rows if row.problem_id in published_ids
    }
    path = learning_path_service.build_learning_path(problems, progress_by_problem)
    recommendation = path.recommendation
    return LearningPathAnalytics(
        total_problems=path.total_problems,
        solved_problems=path.solved_problems,
        attempted_problems=path.attempted_problems,
        completion_percentage=path.completion_percentage,
        stages_total=path.stages_total,
        stages_complete=path.stages_complete,
        current_stage_title=path.current_stage_title,
        weak_topics=list(path.weak_topics),
        recommended_problem=recommendation.problem.title if recommendation else None,
        recommended_reason=recommendation.reason if recommendation else None,
        stages=[
            LearningPathStageAnalytics(
                index=stage.index,
                title=stage.title,
                state=stage.state,
                problem_count=stage.problem_count,
                solved_count=stage.solved_count,
                attempted_count=stage.attempted_count,
                completion_percentage=stage.completion_percentage,
            )
            for stage in path.stages
        ],
    )


# ---------------------------------------------------------------- interviews


def _question_is_answered(question: InterviewQuestion) -> bool:
    """Whether a question carries a judge verdict to read."""
    return question.submission is not None


def _question_is_accepted(question: InterviewQuestion) -> bool:
    """Whether the question's linked submission was accepted.

    The verdict comes from the stored submission row, never from the question's
    own status column -- the same rule the interview report applies.
    """
    if question.submission is None:
        return False
    return normalize_submission_status(question.submission.status) == (
        SubmissionStatus.ACCEPTED.value
    )


def build_interview_analytics(
    interviews: list[InterviewSession],
    questions: list[InterviewQuestion],
) -> InterviewAnalytics:
    """Session counts, score statistics, and question outcomes.

    Scores are read from completed sessions that actually carry one: an
    abandoned session has ``score=None`` by construction, and folding that into
    an average as zero would invent a result the platform never wrote.
    """
    completed = [row for row in interviews if row.status == InterviewStatus.COMPLETED.value]
    abandoned = [
        row for row in interviews if row.status == InterviewStatus.ABANDONED.value
    ]
    active = [row for row in interviews if row.status in ACTIVE_INTERVIEW_STATUSES]
    scored = [row for row in completed if row.score is not None]

    answered = [question for question in questions if _question_is_answered(question)]
    accepted = [question for question in questions if _question_is_accepted(question)]

    ordered_scored = sorted(
        scored,
        key=lambda row: (as_utc(row.completed_at) or as_utc(row.created_at), row.id),
    )
    scores = [
        InterviewScorePoint(
            interview_id=row.id,
            score=int(row.score),
            completed_at=as_utc(row.completed_at),
            timed_out=row.was_timed_out,
        )
        for row in ordered_scored
    ]
    values = [point.score for point in scores]
    return InterviewAnalytics(
        total=len(interviews),
        completed=len(completed),
        abandoned=len(abandoned),
        active=len(active),
        average_score=round(sum(values) / len(values), 2) if values else None,
        best_score=max(values) if values else None,
        questions_total=len(questions),
        questions_answered=len(answered),
        questions_accepted=len(accepted),
        acceptance_rate=(
            round(len(accepted) / len(answered) * 100, 2) if answered else 0.0
        ),
        scores=scores,
    )


# ------------------------------------------------------------------- summary


def build_summary(
    problems: list[Problem],
    progress_rows: list[Progress],
    submissions: list[Submission],
    difficulty_by_problem: dict[int, str],
    interviews: list[InterviewSession],
    questions: list[InterviewQuestion],
    days: int = DEFAULT_ACTIVITY_DAYS,
    today: date | None = None,
) -> AnalyticsSummaryResponse:
    """Assemble the whole summary from already-fetched rows.

    Pure by construction: it reads the rows it is handed and nothing else --
    no clock beyond ``today``, no database, no request. That is what lets the
    tests assert on the arithmetic directly.
    """
    as_of = today or utc_now().date()
    window_days = clamp_activity_days(days)
    return AnalyticsSummaryResponse(
        overview=build_overview(problems, progress_rows, submissions, today=as_of),
        difficulty=build_difficulty_breakdown(
            problems, progress_rows, submissions, difficulty_by_problem
        ),
        topics=build_topic_breakdown(problems, progress_rows),
        verdicts=build_verdict_breakdown(submissions),
        activity=build_activity(progress_rows, submissions, window_days, today=as_of),
        learning_path=build_learning_path_analytics(problems, progress_rows),
        interviews=build_interview_analytics(interviews, questions),
        activity_days=window_days,
        as_of=as_of,
    )


def load_summary(
    session: Session,
    user_id: int,
    days: int = DEFAULT_ACTIVITY_DAYS,
    today: date | None = None,
) -> AnalyticsSummaryResponse:
    """Build the summary for one learner from the database.

    Every learner-scoped query carries ``user_id`` in its WHERE clause, exactly
    like the progress, submission, and interview services: the catalog is the
    only thing read without one, and it is filtered to published rows. The
    difficulty lookup below is the one exception -- it reads catalog rows a
    submission already points at, purely to label the submission, and returns
    nothing a learner could not already read from the public catalog.
    """
    problems = list(
        session.scalars(
            select(Problem).where(Problem.is_published.is_(True)).order_by(Problem.id)
        )
    )
    progress_rows = list(
        session.scalars(select(Progress).where(Progress.user_id == user_id))
    )
    submissions = list(
        session.scalars(
            select(Submission)
            .where(Submission.user_id == user_id)
            .order_by(Submission.submitted_at, Submission.id)
        )
    )
    interviews = list(
        session.scalars(
            select(InterviewSession)
            .where(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.created_at, InterviewSession.id)
        )
    )
    questions = list(
        session.scalars(
            select(InterviewQuestion)
            .join(InterviewSession, InterviewQuestion.session_id == InterviewSession.id)
            .where(InterviewSession.user_id == user_id)
            .options(selectinload(InterviewQuestion.submission))
        )
    )

    difficulty_by_problem = {problem.id: problem.difficulty for problem in problems}
    unlabelled = {
        submission.problem_id
        for submission in submissions
        if submission.problem_id not in difficulty_by_problem
    }
    if unlabelled:
        for problem_id, difficulty in session.execute(
            select(Problem.id, Problem.difficulty).where(Problem.id.in_(unlabelled))
        ):
            difficulty_by_problem[problem_id] = difficulty

    return build_summary(
        problems,
        progress_rows,
        submissions,
        difficulty_by_problem,
        interviews,
        questions,
        days=days,
        today=today,
    )


__all__ = [
    "build_activity",
    "build_difficulty_breakdown",
    "build_interview_analytics",
    "build_learning_path_analytics",
    "build_overview",
    "build_summary",
    "build_topic_breakdown",
    "build_verdict_breakdown",
    "clamp_activity_days",
    "load_summary",
]
