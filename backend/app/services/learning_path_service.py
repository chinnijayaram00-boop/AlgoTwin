"""Deterministic learning-path construction.

The path answers one question -- *what should this learner do next?* -- and it
answers it the same way every time. There is no randomisation, no model call,
and no per-user tuning beyond the learner's own stored progress: given the same
published catalog and the same progress rows, :func:`build_learning_path`
returns the same response. :func:`load_learning_path` only fetches those rows.

Two separate decisions
----------------------

**Which stage comes next** is decided by the curriculum, not by a score. Every
published problem is filed under its *primary* topic -- ``topics[0]``, the same
field the catalog audit treats as the category -- and the stages are those
primary topics laid out in :data:`CURRICULUM_ORDER`, a fixed teaching order
chosen from real prerequisite structure in the catalog: sorting before binary
search, heaps before greedy, trees before graphs, recursion-heavy dynamic
programming after trees. The current stage is simply the first one with
unfinished work, so stages fill in curriculum order and a Hard problem later on
the path can never pull a learner past the Easy work they still owe in the
stage they are standing in. A primary topic the curriculum table does not know
yet is appended alphabetically rather than dropped, so a catalog addition can
never disappear from the path.

Nothing is locked. An upcoming stage is discouraged, not hidden: every problem
stays reachable from the catalog, and readiness is reported as advice.

**Which problem inside that stage** is decided by an integer priority built
from named, documented terms:

======================================  =========================================
Term                                    Value
======================================  =========================================
prerequisite readiness                  +50 when the stage is ready
your stage has started                  +60 once this stage has a solve
you already started this problem        +8 when its status is ``attempted``
difficulty (Easy/Medium/Hard)           +60 / +40 / +20
how far the stage has progressed        up to +10, proportional to its solves
how weak the problem's topics are       up to +10, proportional to unsolved
======================================  =========================================

Every candidate comes from the current stage, so the three stage-level terms
readiness, stage-started, and stage-progress are equal across them; they are
kept in the one formula that describes priority end to end, and they are
reported per stage so a client can show them. The terms that actually separate
candidates are difficulty, whether the learner already started the problem, and
how under-done its topics are -- and the weights are chosen so:

* **difficulty dominates.** The 40-point Easy-to-Hard swing is larger than the
  8-point attempt bonus and the 10-point weakness bonus combined, so a stage
  always offers its Easy problems before its Medium ones and its Medium ones
  before its Hard ones: the Easy -> Medium -> Hard progression the path is
  meant to teach.
* **the winner never depends on iteration order.** Candidates are ranked by the
  total order ``(-score, position, problem id)``, so two runs over the same
  rows cannot disagree.

Within a stage, problems are ordered Easy, then Medium, then Hard, and inside a
tier by ``Problem.id`` -- the order the catalog was authored in, which is a
deliberate progression (``two-sum`` before ``single-number`` before
``binary-search``) where an alphabetical order would be arbitrary.

**Recommendation.** The highest-scoring candidate is returned with a reason
chosen by the first matching rule in :func:`_recommend_reason`, so the sentence
a learner reads is derived from the same state that produced the ranking.

What this module never does
---------------------------

It never recommends a solved problem, never invents or edits catalog content,
never reads a test case or a reference solution, and never lets a request
address another learner: the caller's identity comes from the bearer token and
is the only thing used to filter the progress rows it reads.
"""

from dataclasses import dataclass, field

from database.models import Problem, Progress
from database.models.progress import ProgressStatus, normalize_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.schemas.learning_path import (
    MAX_WEAK_TOPICS,
    REASON_ATTEMPTED_PENDING,
    REASON_CONTINUE_STAGE,
    REASON_FIRST_STEP,
    REASON_NEXT_DIFFICULTY,
    REASON_NEXT_STAGE,
    REASON_PREREQUISITE_MET,
    LearningPathProblem,
    LearningPathRecommendation,
    LearningPathResponse,
    LearningPathStage,
)

#: The teaching order of primary topics. Chosen from the prerequisite structure
#: that actually exists in the catalog -- binary search needs sorted input, the
#: graph traversals reuse the stack and queue instincts built earlier, dynamic
#: programming needs the recursive habit trees teach. Extend it when a new
#: primary topic arrives; :func:`_ordered_primary_topics` appends anything
#: missing alphabetically so the path stays total in the meantime.
CURRICULUM_ORDER: tuple[str, ...] = (
    "Arrays",
    "Strings",
    "Stack",
    "Linked Lists",
    "Sorting",
    "Binary Search",
    "Heaps",
    "Greedy",
    "Trees",
    "Graphs",
    "Dynamic Programming",
    "Bit Manipulation",
)

DIFFICULTY_RANK: dict[str, int] = {"Easy": 0, "Medium": 1, "Hard": 2}
#: A difficulty outside the catalog vocabulary ranks below every real one, so a
#: malformed row is recommended last instead of crashing the endpoint.
UNKNOWN_DIFFICULTY_RANK = 3

# --- scoring terms. Each is named because each is asserted in the tests, and
# --- because a reviewer should be able to check the ordering invariant above
# --- against the numbers without reading any scoring code.
SCORE_PREREQUISITE_READY = 50
SCORE_STAGE_STARTED = 60
SCORE_ATTEMPTED = 8
SCORE_BY_DIFFICULTY: dict[int, int] = {0: 60, 1: 40, 2: 20, 3: 0}
MAX_STAGE_PROGRESS_BONUS = 10
MAX_TOPIC_WEAKNESS_BONUS = 10

SOLVED = ProgressStatus.SOLVED.value
ATTEMPTED = ProgressStatus.ATTEMPTED.value


@dataclass
class _Entry:
    """A catalog row plus everything the scorer needs to know about it."""

    problem: Problem
    topics: list[str]
    primary_topic: str
    rank: int
    status: str
    attempts_count: int = 0


@dataclass
class _StageFacts:
    """Per-stage aggregates the scorer and the response builder share."""

    entries: list[_Entry]
    solved: int = 0
    attempted: int = 0
    minimum_rank: int = UNKNOWN_DIFFICULTY_RANK
    prerequisite_ready: bool = False
    problems: list[LearningPathProblem] = field(default_factory=list)


def _topics_of(problem: Problem) -> list[str]:
    """The topic labels of a problem, defensively typed.

    Mirrors the same coercion in :mod:`backend.app.services.progress_service`
    because ``Problem.topics`` is a JSON column: whatever the database holds,
    the path has to make a decision from it rather than raise. Only countable
    scalars survive -- a dict, a ``None``, or a boolean in the column is a dirty
    row, not a topic label.
    """
    topics = problem.topics
    if not isinstance(topics, list):
        return []
    return [
        str(topic)
        for topic in topics
        if isinstance(topic, (str, int, float)) and not isinstance(topic, bool)
    ]


def stage_key(title: str) -> str:
    """A URL-safe handle for a stage title, e.g. ``Binary Search`` -> ``binary-search``."""
    words = "".join(char if char.isalnum() else " " for char in title).lower().split()
    return "-".join(words) or "stage"


def _ordered_primary_topics(entries: list[_Entry]) -> list[str]:
    """Primary topics in curriculum order, unknown ones appended alphabetically."""
    present = {entry.primary_topic for entry in entries}
    known = [topic for topic in CURRICULUM_ORDER if topic in present]
    unknown = sorted(present.difference(CURRICULUM_ORDER))
    return known + unknown


def _entry_for(problem: Problem, progress: Progress | None) -> _Entry:
    topics = _topics_of(problem)
    primary = topics[0] if topics else "Uncategorised"
    rank = DIFFICULTY_RANK.get(problem.difficulty, UNKNOWN_DIFFICULTY_RANK)
    if progress is None:
        return _Entry(
            problem=problem,
            topics=topics,
            primary_topic=primary,
            rank=rank,
            status=ProgressStatus.NOT_STARTED.value,
        )
    return _Entry(
        problem=problem,
        topics=topics,
        primary_topic=primary,
        rank=rank,
        status=normalize_status(progress.status),
        attempts_count=max(int(progress.attempts_count or 0), 0),
    )


def _topic_counts(
    entries: list[_Entry],
) -> tuple[dict[str, int], dict[str, int], dict[str, int], dict[str, int]]:
    """Per-topic totals, unsolved, solved, and attempted counts across the catalog.

    ``unsolved`` drives the priority score; ``solved`` and ``attempted`` together
    describe whether a topic has been *started*, which is what separates a weak
    topic from an untouched one in :func:`_weak_topics`.
    """
    total: dict[str, int] = {}
    unsolved: dict[str, int] = {}
    solved: dict[str, int] = {}
    attempted: dict[str, int] = {}
    for entry in entries:
        for topic in entry.topics:
            total[topic] = total.get(topic, 0) + 1
            if entry.status == SOLVED:
                solved[topic] = solved.get(topic, 0) + 1
            else:
                unsolved[topic] = unsolved.get(topic, 0) + 1
            if entry.status == ATTEMPTED:
                attempted[topic] = attempted.get(topic, 0) + 1
    return total, unsolved, solved, attempted


def _weak_topics(
    topic_total: dict[str, int],
    topic_solved: dict[str, int],
    topic_attempted: dict[str, int],
) -> list[str]:
    """Topics the learner has started but not finished, most outstanding first.

    "Started but not finished" means the learner has *touched* the topic -- at
    least one problem solved **or attempted** -- and has not solved every problem
    in it. A topic with nothing solved and nothing attempted is not weak, it is
    untouched, and a topic that is fully solved is not weak at all. Counting
    attempts matters: a learner who tried a problem and could not finish it has
    started that topic, so reporting it as untouched would understate the work
    owed. Ties break alphabetically so the list is stable.
    """
    started = set(topic_solved) | set(topic_attempted)
    outstanding = [
        (topic_total[topic] - topic_solved.get(topic, 0), topic)
        for topic in started
        if topic_solved.get(topic, 0) < topic_total.get(topic, 0)
    ]
    outstanding.sort(key=lambda item: (-item[0], item[1]))
    return [topic for _remaining, topic in outstanding[:MAX_WEAK_TOPICS]]


def _score(
    entry: _Entry,
    facts: _StageFacts,
    topic_unsolved: dict[str, int],
    topic_total: dict[str, int],
) -> int:
    """The priority of one unsolved problem. See the module docstring for the terms."""
    score = 0
    if facts.prerequisite_ready:
        score += SCORE_PREREQUISITE_READY
    if facts.solved > 0:
        score += SCORE_STAGE_STARTED
    if entry.status == ATTEMPTED:
        score += SCORE_ATTEMPTED
    score += SCORE_BY_DIFFICULTY.get(entry.rank, 0)

    if facts.entries:
        score += int(round(MAX_STAGE_PROGRESS_BONUS * facts.solved / len(facts.entries)))

    # The weakest topic the problem belongs to. A topic that is fully solved
    # contributes nothing, so the bonus really does track *incomplete* work.
    weakness = 0.0
    for topic in entry.topics:
        denominator = topic_total.get(topic, 0)
        if denominator:
            weakness = max(weakness, topic_unsolved.get(topic, 0) / denominator)
    score += int(round(MAX_TOPIC_WEAKNESS_BONUS * weakness))

    return score


def _recommend_reason(
    entry: _Entry,
    facts: _StageFacts,
    stage_title: str,
    solved_before_stage: int,
    solved_total: int,
) -> tuple[str, str]:
    """Pick the explanation for the top-ranked problem, first matching rule wins.

    The rules are ordered from the most specific thing that is true about this
    learner's state to the least, so a learner who both started the problem
    *and* is mid-stage is told about the problem they left open rather than
    being handed a generic nudge.
    """
    title = entry.problem.title

    if entry.status == ATTEMPTED:
        return REASON_ATTEMPTED_PENDING, f"You started {title} but have not solved it yet."

    if solved_total == 0:
        return REASON_FIRST_STEP, f"Start with the {stage_title} fundamentals."

    if facts.solved > 0 and entry.rank > facts.minimum_rank:
        # The easier problems in this stage are done, so the learner has moved
        # up a tier rather than merely moved on.
        return (
            REASON_NEXT_DIFFICULTY,
            f"This is the next {entry.problem.difficulty} problem in your current topic.",
        )

    if facts.solved > 0:
        return REASON_CONTINUE_STAGE, f"Continue your {stage_title} progression."

    if solved_before_stage > 0:
        return REASON_PREREQUISITE_MET, "You completed the prerequisite fundamentals."

    return REASON_NEXT_STAGE, f"Take on {stage_title} next."


def build_learning_path(
    problems: list[Problem],
    progress_by_problem: dict[int, Progress],
) -> LearningPathResponse:
    """Assemble the whole path from already-fetched rows.

    Pure by construction: it reads the catalog and the caller's progress, and
    nothing else. That is what lets the tests drive it with plain objects and
    assert on ordering without a database, an HTTP client, or a token.
    """
    entries = [
        _entry_for(problem, progress_by_problem.get(problem.id)) for problem in problems
    ]
    ordered_topics = _ordered_primary_topics(entries)

    by_stage: dict[str, list[_Entry]] = {topic: [] for topic in ordered_topics}
    for entry in entries:
        by_stage[entry.primary_topic].append(entry)
    for stage_entries in by_stage.values():
        stage_entries.sort(key=lambda item: (item.rank, item.problem.id, item.problem.title))

    topic_total, topic_unsolved, topic_solved, topic_attempted = _topic_counts(entries)

    stages: list[LearningPathStage] = []
    facts_by_topic: dict[str, _StageFacts] = {}
    solved_before_stage = 0
    current_index: int | None = None

    for index, topic in enumerate(ordered_topics):
        stage_entries = by_stage[topic]
        solved = sum(1 for item in stage_entries if item.status == SOLVED)
        attempted = sum(1 for item in stage_entries if item.status == ATTEMPTED)
        # Ready when the learner has demonstrated progress at or before this
        # point. Index 0 is ready by definition, so a fresh learner always has
        # somewhere to start.
        ready = index == 0 or (solved_before_stage + solved) > 0

        facts = _StageFacts(
            entries=stage_entries,
            solved=solved,
            attempted=attempted,
            minimum_rank=min(
                (item.rank for item in stage_entries), default=UNKNOWN_DIFFICULTY_RANK
            ),
            prerequisite_ready=ready,
        )
        facts_by_topic[topic] = facts

        complete = bool(stage_entries) and solved == len(stage_entries)
        if not complete and current_index is None:
            current_index = index

        facts.problems = [
            LearningPathProblem(
                problem_id=item.problem.id,
                slug=item.problem.slug,
                title=item.problem.title,
                summary=item.problem.summary,
                difficulty=item.problem.difficulty,
                topics=list(item.topics),
                primary_topic=item.primary_topic,
                status=item.status,
                attempts_count=item.attempts_count,
                position=position,
            )
            for position, item in enumerate(stage_entries)
        ]

        count = len(stage_entries)
        stages.append(
            LearningPathStage(
                index=index,
                key=stage_key(topic),
                title=topic,
                state=(
                    "complete"
                    if complete
                    else "current"
                    if current_index == index
                    else "upcoming"
                ),
                prerequisite_title=stages[index - 1].title if index > 0 else None,
                prerequisite_ready=ready,
                problem_count=count,
                solved_count=solved,
                attempted_count=attempted,
                completion_percentage=round(solved / count * 100, 2) if count else 0.0,
                problems=facts.problems,
            )
        )
        solved_before_stage += solved

    solved_total = sum(stage.solved_count for stage in stages)
    attempted_total = sum(stage.attempted_count for stage in stages)
    total = len(entries)

    recommendation: LearningPathRecommendation | None = None
    if current_index is not None:
        topic = ordered_topics[current_index]
        facts = facts_by_topic[topic]
        # Only the current stage is ever offered, which is what keeps the
        # highlighted stage and the recommended problem the same thing. The
        # ranking below therefore decides *which* problem, never *which stage*.
        candidates = [
            (-_score(entry, facts, topic_unsolved, topic_total), position, entry.problem.id)
            for position, entry in enumerate(facts.entries)
            if entry.status != SOLVED
        ]
        if candidates:
            _negated, position, _problem_id = min(candidates)
            entry = facts.entries[position]
            reason_code, reason = _recommend_reason(
                entry,
                facts,
                stage_title=topic,
                solved_before_stage=sum(
                    stage.solved_count for stage in stages if stage.index < current_index
                ),
                solved_total=solved_total,
            )
            recommendation = LearningPathRecommendation(
                reason_code=reason_code,
                reason=reason,
                score=-_negated,
                stage_index=current_index,
                stage_title=topic,
                problem=facts.problems[position],
            )

    return LearningPathResponse(
        total_problems=total,
        solved_problems=solved_total,
        attempted_problems=attempted_total,
        completion_percentage=round(solved_total / total * 100, 2) if total else 0.0,
        stages_total=len(stages),
        stages_complete=sum(1 for stage in stages if stage.state == "complete"),
        current_stage_index=current_index,
        current_stage_title=stages[current_index].title if current_index is not None else None,
        weak_topics=_weak_topics(topic_total, topic_solved, topic_attempted),
        recommendation=recommendation,
        stages=stages,
    )


def load_learning_path(session: Session, user_id: int) -> LearningPathResponse:
    """Build the path for one learner from the published catalog.

    The catalog is the denominator and the learner's rows are the only progress
    read, so two learners working side by side get entirely separate paths from
    the same endpoint.
    """
    problems = list(
        session.scalars(
            select(Problem).where(Problem.is_published.is_(True)).order_by(Problem.id)
        )
    )
    progress_by_problem: dict[int, Progress] = {}
    if problems:
        for row in session.scalars(
            select(Progress).where(
                Progress.user_id == user_id,
                Progress.problem_id.in_([problem.id for problem in problems]),
            )
        ):
            progress_by_problem[row.problem_id] = row
    return build_learning_path(problems, progress_by_problem)


__all__ = [
    "CURRICULUM_ORDER",
    "DIFFICULTY_RANK",
    "build_learning_path",
    "load_learning_path",
    "stage_key",
]
