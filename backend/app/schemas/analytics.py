"""Request and response contracts for the learner analytics summary.

Every shape here is a projection of one learner's own persisted rows: the
published catalog, that learner's progress records, that learner's submissions,
and that learner's mock interviews. Like the progress, submission, and interview
contracts, ``user_id`` is deliberately absent from all of them -- the learner is
identified by the bearer token on the request, so no response needs to echo
whose record it is and no client can ask for somebody else's numbers.

Nothing here is estimated. A count is a count of stored rows, a rate is a
division of two counts that are both reported beside it, and a measurement
average is taken only over rows the judge actually measured; where no evidence
exists the field is ``None`` or ``0.0`` rather than a plausible-looking guess.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field

#: How many days of activity the default summary covers, and the window a
#: caller may ask for. The window only bounds the activity series; every other
#: section of the summary covers the learner's whole recorded history.
DEFAULT_ACTIVITY_DAYS = 30
MIN_ACTIVITY_DAYS = 7
MAX_ACTIVITY_DAYS = 90

#: The catalog's difficulty vocabulary, in teaching order. A difficulty outside
#: it is still reported -- appended alphabetically -- rather than dropped, so a
#: catalog addition cannot disappear from the analytics.
DIFFICULTY_ORDER: tuple[str, ...] = ("Easy", "Medium", "Hard")


class AnalyticsOverview(BaseModel):
    """The headline numbers for the requesting learner.

    Two groups, matching the two kinds of evidence behind them: the catalog and
    the learner's progress rows answer the first half, and the learner's
    submissions answer the second. ``acceptance_rate`` is ``accepted /
    judged_submissions`` -- never over total submissions, because counting an
    unjudged row as a failure would be a verdict nothing wrote.
    """

    total_problems: int
    solved: int
    attempted: int
    not_started: int
    completion_percentage: float
    current_streak_days: int

    total_submissions: int
    judged_submissions: int
    accepted_submissions: int
    acceptance_rate: float
    problems_submitted: int
    average_runtime_ms: float | None = None
    average_memory_mb: float | None = None


class DifficultyAnalytics(BaseModel):
    """Catalog standing and submission performance for one difficulty tier.

    The first half counts problems (the catalog is the denominator); the second
    counts that tier's submissions. They are separate because they answer
    separate questions -- "how much of this tier have I solved" is not "how well
    do I code under this tier's pressure".
    """

    difficulty: str
    total: int
    solved: int
    attempted: int
    not_started: int
    completion_percentage: float
    submissions: int
    judged: int
    accepted: int
    acceptance_rate: float


class TopicAnalytics(BaseModel):
    """Catalog standing for one topic label.

    A problem may carry several topics, so these rows sum to more than the
    catalog size -- exactly as the progress summary's topic counts do.
    """

    topic: str
    total: int
    solved: int
    attempted: int
    not_started: int
    completion_percentage: float


class VerdictAnalytics(BaseModel):
    """One judge verdict and its share of the learner's submissions.

    ``percentage`` is over *all* submissions, judged or not, so the slices add
    up to 100. A verdict with no rows is omitted rather than reported as a
    zero-width slice; ``queued`` is a real state and is reported like any other.
    """

    status: str
    count: int
    percentage: float


class ActivityDay(BaseModel):
    """One calendar day inside the requested activity window.

    ``submissions`` counts rows sent to the judge that day, ``solves`` counts
    problems that reached ``solved`` that day, and ``attempts`` counts problems
    whose last recorded attempt was that day. All three come from stored
    timestamps; the series is zero-filled so a quiet day reads as a real zero
    rather than a gap in the axis.
    """

    date: date
    submissions: int = 0
    attempts: int = 0
    solves: int = 0


class LearningPathStageAnalytics(BaseModel):
    """One curriculum stage as the analytics summary reads it."""

    index: int
    title: str
    state: str
    problem_count: int
    solved_count: int
    attempted_count: int
    completion_percentage: float


class LearningPathAnalytics(BaseModel):
    """The learning path summarized: progress, position, and what is outstanding.

    Built by the same :func:`learning_path_service.build_learning_path` the
    ``/learning-path`` endpoint runs, then projected down to the headline
    numbers -- so the analytics page and the path page can never disagree about
    which stage the learner is standing in.
    """

    total_problems: int
    solved_problems: int
    attempted_problems: int
    completion_percentage: float
    stages_total: int
    stages_complete: int
    current_stage_title: str | None = None
    weak_topics: list[str] = Field(default_factory=list)
    recommended_problem: str | None = None
    recommended_reason: str | None = None
    stages: list[LearningPathStageAnalytics] = Field(default_factory=list)


class InterviewScorePoint(BaseModel):
    """One completed interview's stored score, for the score trend."""

    interview_id: int
    score: int
    completed_at: datetime | None = None
    timed_out: bool = False


class InterviewAnalytics(BaseModel):
    """Mock interview performance across the requesting learner's sessions.

    ``average_score`` and ``best_score`` are computed over completed sessions
    only: an abandoned session carries no score by construction, and treating
    its ``None`` as zero would invent a result the platform never wrote.
    """

    total: int
    completed: int
    abandoned: int
    active: int
    average_score: float | None = None
    best_score: int | None = None
    questions_total: int = 0
    questions_answered: int = 0
    questions_accepted: int = 0
    #: Accepted over *answered* questions. A question nobody submitted is not a
    #: failed question, so it is excluded from the denominator rather than
    #: counted as a miss.
    acceptance_rate: float = 0.0
    scores: list[InterviewScorePoint] = Field(default_factory=list)


class AnalyticsSummaryResponse(BaseModel):
    """The whole analytics summary in one read.

    One endpoint rather than a family of narrowly-scoped ones, because every
    section is a projection of the same learner's rows over the same moment:
    splitting them would let the overview and the charts be computed at
    different times and disagree.
    """

    overview: AnalyticsOverview
    difficulty: list[DifficultyAnalytics] = Field(default_factory=list)
    topics: list[TopicAnalytics] = Field(default_factory=list)
    verdicts: list[VerdictAnalytics] = Field(default_factory=list)
    activity: list[ActivityDay] = Field(default_factory=list)
    learning_path: LearningPathAnalytics
    interviews: InterviewAnalytics
    #: The window ``activity`` actually covers, echoed back so a chart can
    #: label its axis from the response instead of assuming its own default.
    activity_days: int = DEFAULT_ACTIVITY_DAYS
    #: The day the summary was computed for. Activity and streaks are measured
    #: against this date, which the tests can pin so assertions stay stable.
    as_of: date


__all__ = [
    "DEFAULT_ACTIVITY_DAYS",
    "DIFFICULTY_ORDER",
    "MAX_ACTIVITY_DAYS",
    "MIN_ACTIVITY_DAYS",
    "ActivityDay",
    "AnalyticsOverview",
    "AnalyticsSummaryResponse",
    "DifficultyAnalytics",
    "InterviewAnalytics",
    "InterviewScorePoint",
    "LearningPathAnalytics",
    "LearningPathStageAnalytics",
    "TopicAnalytics",
    "VerdictAnalytics",
]
