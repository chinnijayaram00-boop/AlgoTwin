"""Tests for the algorithm lab.

Three groups, in the order a failure actually shows up:

* **The registry is real.** Every entry names a function that runs, on an input the
  sample parses as, producing frames in the layout the descriptor claims. This is the
  test that would fail if somebody added a card for an algorithm nobody wrote.
* **The boundary holds.** A capped run says it was capped; an algorithm that does not
  exist is a 404 and not a 500; a disabled deployment answers 503 and starts no
  worker; a malformed input is a 422 naming the format.
* **The comparison tells the truth.** Same input on every side, every requested side
  present in the response, and no measurement invented where none was taken.

The last group is the one the whole feature rests on. A comparison that quietly
dropped a failed side, or rendered an unmeasured figure as zero, would look
identical to a correct one in a screenshot.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.app.algorithms.inputs import (
    GRAMMARS,
    GRID_ALPHABET,
    GRID_GOAL,
    GRID_START,
    InvalidInputError,
    parse,
)
from backend.app.algorithms.registry import (
    ALGORITHM_REGISTRY,
    COMPARABLE_GROUPS,
    REFERENCE_LANGUAGES,
    algorithms_for_problem,
    get_algorithm,
    list_algorithms,
    list_by_category,
    list_comparable,
)
from backend.app.core.config import Settings
from backend.app.schemas.visualization import MAX_INPUT_LENGTH, VisualizationRequestBody
from backend.app.visualization.limits import (
    MAX_COMPARISON_SIDES,
    MIN_COMPARISON_SIDES,
    VisualizationLimits,
)
from backend.app.visualization.runner import VisualizationError, execute
from backend.tests.conftest import TEST_JWT_ALGORITHM, TEST_JWT_SECRET

VISUALIZE = "/api/v1/algorithms/{}/visualize"
COMPARE = "/api/v1/algorithms/compare"
SORT_SAMPLE = "6\n5 2 9 1 7 3"

#: Only a couple of the algorithms run in this file. Each worker spawn is a process,
#: so a test suite that ran all fourteen on every case would be slow for no extra
#: confidence -- and the registry group below already runs every one of them once.
REPRESENTATIVE_IDS = ("bubble-sort", "merge-sort", "binary-search", "coin-change", "word-search")


def auth_headers(client: TestClient) -> dict[str, str]:
    """Register a learner and return a bearer header.

    Each call registers a fresh account so tests do not share one, which is the same
    isolation rule the rest of the suite follows.
    """
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Lab Learner",
            "email": f"lab-{id(client)}-{len(client.cookies)}@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert response.status_code in (201, 409), response.text
    if response.status_code == 409:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": f"lab-{id(client)}-{len(client.cookies)}@example.com",
                "password": "correct-horse-battery-staple",
            },
        )
        assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class _LabClientFactory:
    """Builds a client whose settings and database are both overridden.

    Existing in one small class rather than as a fixture because two tests need it
    and the sequence -- override, use, clear -- is easy to get wrong when it is
    written out at each call site. Clearing is the important part: a settings
    override that leaks would silently change what every later test in the file is
    measuring.
    """

    def __init__(self, db_engine) -> None:
        from backend.app.core.config import get_settings
        from backend.app.db.session import get_db
        from backend.app.main import app

        self._app = app
        self._get_db = get_db
        self._get_settings = get_settings
        self._engine = db_engine

        def override_get_db():
            with Session(db_engine) as session:
                yield session

        self._app.dependency_overrides[self._get_db] = override_get_db
        self._override = override_get_db

    def with_settings(self, **overrides):
        self._app.dependency_overrides[self._get_settings] = lambda: Settings(
            jwt_secret_key=TEST_JWT_SECRET,
            jwt_algorithm=TEST_JWT_ALGORITHM,
            access_token_expire_minutes=60,
            **overrides,
        )
        return self

    def client(self) -> TestClient:
        return TestClient(self._app)

    def close(self) -> None:
        self._app.dependency_overrides.clear()


# ------------------------------------------------------------------- the registry


def test_registry_is_not_empty() -> None:
    assert list_algorithms(), "the lab published no algorithms"


def test_every_entry_names_a_function_that_runs() -> None:
    """No card may point at an algorithm that does not exist.

    This is the test that makes the registry trustworthy. A placeholder entry -- one
    whose implementation is ``None``, or names something that raises -- would show up
    on the picker and only fail once a learner clicked it.
    """
    for descriptor in ALGORITHM_REGISTRY:
        assert callable(descriptor.implementation), descriptor.id

        trace = descriptor.trace()
        frames = list(descriptor.implementation(descriptor.parse_input(descriptor.sample_input), trace))

        assert frames, f"{descriptor.id} produced no frames"
        assert frames[-1].status == "complete", f"{descriptor.id} never finished"
        assert all(frame.kind == descriptor.state_kind for frame in frames), descriptor.id


def test_every_entry_declares_a_grammar_the_platform_implements() -> None:
    for descriptor in ALGORITHM_REGISTRY:
        assert descriptor.input_grammar in GRAMMARS, descriptor.id


def test_every_sample_input_parses_under_its_own_grammar() -> None:
    """The sample a card shows must be an input that card accepts.

    A sample that does not parse is a trap: the learner copies it, presses run, and
    is told their input is wrong.
    """
    for descriptor in ALGORITHM_REGISTRY:
        case = descriptor.parse_input(descriptor.sample_input)
        assert case is not None, descriptor.id


def test_supported_languages_come_from_the_language_registry() -> None:
    for descriptor in ALGORITHM_REGISTRY:
        assert descriptor.supported_languages == REFERENCE_LANGUAGES
        assert REFERENCE_LANGUAGES, "no language ids to publish"


def test_stability_is_stated_only_where_it_is_meaningful() -> None:
    """A sort may claim to be stable; a search may not.

    ``is_stable`` is ``None`` for algorithms the word does not apply to, and the API
    publishes that as ``null`` rather than as ``false`` -- "this algorithm is not
    stable" and "stability is not a property of this algorithm" are different claims.
    """
    for descriptor in ALGORITHM_REGISTRY:
        if descriptor.category == "Sorting":
            assert descriptor.is_stable is not None, descriptor.id
        else:
            assert descriptor.is_stable is None, descriptor.id


def test_ids_are_unique_and_lookups_are_case_insensitive() -> None:
    ids = [descriptor.id for descriptor in ALGORITHM_REGISTRY]
    assert len(ids) == len(set(ids))

    for identifier in ids:
        assert get_algorithm(identifier.upper()) is not None
        assert get_algorithm(f"  {identifier}  ") is not None
    assert get_algorithm("nope") is None
    assert get_algorithm(None) is None


def test_comparables_are_symmetric_and_same_group() -> None:
    """Whatever the detail route offers, the compare route has to accept.

    Symmetry matters because the client reads this list from either side of a
    pairing. If bubble sort offered quick sort and quick sort offered nothing, the
    picker would offer a comparison that 422s.
    """
    for descriptor in ALGORITHM_REGISTRY:
        peers = list_comparable(descriptor.id)
        assert descriptor.id not in [peer.id for peer in peers], descriptor.id
        for peer in peers:
            assert peer.comparison_group == descriptor.comparison_group, descriptor.id
            assert descriptor.id in [other.id for other in list_comparable(peer.id)], peer.id


def test_only_multi_member_groups_are_published_as_comparable() -> None:
    for group in COMPARABLE_GROUPS:
        members = [
            descriptor.id
            for descriptor in ALGORITHM_REGISTRY
            if descriptor.comparison_group == group
        ]
        assert len(members) >= 2, group


def test_categories_partition_the_registry() -> None:
    grouped = list_by_category()
    assert sum(len(members) for members in grouped.values()) == len(ALGORITHM_REGISTRY)
    assert list(grouped) == sorted(grouped)


def test_problem_lookups_come_from_the_registry_itself() -> None:
    """The problem-to-algorithm mapping is not a second hand-written table."""
    for descriptor in ALGORITHM_REGISTRY:
        for slug in descriptor.comparison:
            assert descriptor.id in [
                other.id for other in algorithms_for_problem(slug)
            ], slug


# ------------------------------------------------------------------ the parsers


def test_parsers_reject_a_count_that_does_not_match() -> None:
    with pytest.raises(InvalidInputError) as caught:
        parse("int_list", "3\n5 2")
    assert "2" in str(caught.value)


def test_parsers_reject_non_integers() -> None:
    with pytest.raises(InvalidInputError):
        parse("int_list", "2\n5 two")


def test_parsers_enforce_their_size_ceilings() -> None:
    with pytest.raises(InvalidInputError):
        parse("int_list", f"{200}\n{'1 ' * 200}")
    with pytest.raises(InvalidInputError):
        parse("grid_word", "40 40\n" + "\n".join(["x" * 40] * 40) + "\nword")


def test_path_grid_alphabet_is_validated() -> None:
    """Every ambiguous grid is refused with a message that names the fix.

    A multi-character ``S`` is two cells wide; two starts leave nothing to choose
    between; a letter that is not ``#`` draws as open ground and the traversal walks
    through it. Each of those would produce a confident, wrong answer, so each is
    caught here.
    """
    with pytest.raises(InvalidInputError):
        parse("labelled_grid", "1 2\nSS\n.G")
    with pytest.raises(InvalidInputError):
        parse("labelled_grid", "1 2\n..\n.G")
    with pytest.raises(InvalidInputError):
        parse("labelled_grid", "1 2\n.X\n.G")
    assert parse("labelled_grid", "1 3\nS.G").grid == (("S", ".", "G"),)


def test_unknown_grammar_is_refused_rather_than_defaulted() -> None:
    """An unknown grammar must not fall through to some other algorithm's parser."""
    with pytest.raises(InvalidInputError) as caught:
        parse("not-a-grammar", "1\n1")
    assert "not-a-grammar" in str(caught.value)


# ------------------------------------------------------------- the worker boundary


def test_limits_clamp_rather_than_reject() -> None:
    """A request may lower a ceiling but never raise it.

    Clamping instead of failing is the judge module's rule and this one follows it:
    being asked to show a visualization is not the moment to reject a request over one
    odd field, and a "limit" that a caller could raise is not a limit.
    """
    generous = VisualizationLimits.resolve(max_frames=20_000, repetitions=500, wall_clock_ms=1)
    assert generous.max_frames <= 2_000
    assert generous.repetitions <= 25
    assert generous.wall_clock_ms >= 100

    nonsense = VisualizationLimits.resolve(max_frames="x", repetitions=None, wall_clock_ms=None)
    assert nonsense.max_frames == 2_000
    assert nonsense.repetitions > 0


def test_worker_rejects_an_unknown_algorithm() -> None:
    outcome = execute("no-such-algorithm", "1\n1", VisualizationLimits.resolve(), "run")

    assert outcome.kind == "invalid_request"
    assert not outcome.succeeded


def test_worker_rejects_an_input_the_grammar_refuses() -> None:
    outcome = execute("bubble-sort", "3\n5 2", VisualizationLimits.resolve(), "run")

    assert outcome.kind == "invalid_request"


def test_worker_rejects_an_unknown_mode() -> None:
    with pytest.raises(VisualizationError):
        execute("bubble-sort", SORT_SAMPLE, VisualizationLimits.resolve(), "teleport")


def test_a_capped_run_is_reported_as_capped() -> None:
    """A truncated timeline is shown, and is never presented as the whole run.

    Real execution, capped -- so it is not an error, but the last frame is relabelled
    and the caller is told, because a timeline that stops at frame 4 without saying so
    is a lie about the algorithm's length.
    """
    outcome = execute("bubble-sort", SORT_SAMPLE, VisualizationLimits.resolve(max_frames=4), "run")

    assert outcome.succeeded
    assert outcome.truncated is True
    assert len(outcome.frames) == 4
    assert outcome.frames[-1]["status"] == "truncated"
    assert outcome.result is None, "a capped run has not reached its answer"


def test_a_complete_run_is_not_reported_as_capped() -> None:
    outcome = execute("bubble-sort", SORT_SAMPLE, VisualizationLimits.resolve(max_frames=2_000), "run")

    assert outcome.succeeded
    assert outcome.truncated is False
    assert outcome.frames[-1]["status"] == "complete"
    assert outcome.result is not None


def test_measure_mode_reports_a_median_and_drops_the_frames() -> None:
    outcome = execute("bubble-sort", SORT_SAMPLE, VisualizationLimits.resolve(repetitions=5), "measure")

    assert outcome.succeeded
    assert outcome.frames == (), "a timed run must not ship its frames"
    assert outcome.was_measured
    assert outcome.repetitions == 5
    assert len(outcome.samples_ms) == 5
    assert outcome.runtime_ms is not None
    assert outcome.runtime_ms > 0


def test_counters_survive_a_run_whose_frames_are_thrown_away() -> None:
    """The counts are a property of the algorithm, not of who is watching.

    A comparison discards the frames and still reports the same operation counts as
    the visualization, because the ``Trace`` is written by the algorithm as it goes.
    """
    measured = execute("bubble-sort", SORT_SAMPLE, VisualizationLimits.resolve(), "measure")
    visualized = execute("bubble-sort", SORT_SAMPLE, VisualizationLimits.resolve(), "run")

    assert measured.metrics == visualized.metrics
    assert measured.metrics.get("comparisons", 0) > 0


def test_sort_counters_are_real_operations() -> None:
    """The counters are counted, not estimated.

    Bubble sort on six elements does at most 15 comparisons and these frames show
    fewer, because it stops early once a pass makes no swap. An implementation that
    guessed ``n * n`` would be wrong here in a way a learner would notice.
    """
    outcome = execute("bubble-sort", SORT_SAMPLE, VisualizationLimits.resolve(), "run")

    assert 0 < outcome.metrics["comparisons"] <= 15
    assert outcome.metrics["swaps"] <= 15


# ----------------------------------------------------------------- the API surface


def test_catalog_endpoint_lists_every_algorithm(client: TestClient) -> None:
    response = client.get("/api/v1/algorithms")

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert ids == [descriptor.id for descriptor in ALGORITHM_REGISTRY]


def test_categories_endpoint_groups_the_same_algorithms(client: TestClient) -> None:
    response = client.get("/api/v1/algorithms/categories")

    assert response.status_code == 200
    grouped = response.json()
    assert sum(len(members) for members in grouped.values()) == len(ALGORITHM_REGISTRY)


def test_visualize_returns_a_usable_timeline(client: TestClient) -> None:
    headers = auth_headers(client)

    response = client.post(
        VISUALIZE.format("bubble-sort"), json={"input": SORT_SAMPLE}, headers=headers
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["algorithm"]["id"] == "bubble-sort"
    assert payload["input"] == SORT_SAMPLE
    assert payload["truncated"] is False
    assert payload["result"]

    frames = payload["frames"]
    assert len(frames) > 1
    # Step must equal the index, or a scrubber that seeks to a step shows the wrong
    # state and the whole timeline becomes unreliable.
    assert [frame["step"] for frame in frames] == list(range(len(frames)))
    for frame in frames:
        assert frame["explanation"], f"frame {frame['step']} has no explanation"
        assert frame["state"]["kind"] == "bar_array"
        assert frame["state"]["rows"]


def test_visualize_covers_every_registered_layout(client: TestClient) -> None:
    """One renderer, four layouts -- so all four must arrive intact."""
    headers = auth_headers(client)

    for descriptor in ALGORITHM_REGISTRY:
        response = client.post(
            VISUALIZE.format(descriptor.id),
            json={"input": descriptor.sample_input},
            headers=headers,
        )
        assert response.status_code == 200, f"{descriptor.id}: {response.text}"
        payload = response.json()
        frames = payload["frames"]
        assert frames, descriptor.id
        for frame in frames:
            assert frame["state"]["kind"] == descriptor.state_kind, descriptor.id
            if descriptor.state_kind == "grid":
                assert len(frame["state"]["rows"]) >= 1, descriptor.id
            else:
                assert frame["state"]["rows"], descriptor.id


def test_visualize_respects_a_lower_frame_ceiling(client: TestClient) -> None:
    headers = auth_headers(client)

    response = client.post(
        VISUALIZE.format("bubble-sort"),
        json={"input": SORT_SAMPLE, "max_frames": 3},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["frames"]) == 3
    assert payload["truncated"] is True


def test_visualize_422s_on_an_input_the_grammar_refuses(client: TestClient) -> None:
    headers = auth_headers(client)

    response = client.post(
        VISUALIZE.format("bubble-sort"), json={"input": "3\n5 2"}, headers=headers
    )

    assert response.status_code == 422
    # The message has to name the problem, or a learner cannot act on it.
    assert "input format" in response.json()["detail"].lower()


def test_visualize_rejects_an_empty_input(client: TestClient) -> None:
    headers = auth_headers(client)

    response = client.post(
        VISUALIZE.format("bubble-sort"), json={"input": "   "}, headers=headers
    )

    assert response.status_code == 422


def test_the_input_ceiling_is_a_ceiling_not_a_wall() -> None:
    """Exactly ``MAX_INPUT_LENGTH`` is allowed; one character more is refused.

    This is the schema boundary itself, independent of any grammar -- the point is
    that a body is rejected on its size before a parser ever sees it.
    """
    VisualizationRequestBody(input="x" * MAX_INPUT_LENGTH)

    with pytest.raises(ValidationError):
        VisualizationRequestBody(input="x" * (MAX_INPUT_LENGTH + 1))


def test_visualize_rejects_an_oversized_input(client: TestClient) -> None:
    """An over-long body is a 422, not read in full and then parsed."""
    headers = auth_headers(client)

    response = client.post(
        VISUALIZE.format("bubble-sort"),
        json={"input": "9 " * MAX_INPUT_LENGTH},
        headers=headers,
    )

    assert response.status_code == 422


def test_compare_rejects_an_oversized_input(client: TestClient) -> None:
    headers = auth_headers(client)

    response = client.post(
        COMPARE,
        json={
            "algorithms": [
                {"algorithm_id": "bubble-sort"},
                {"algorithm_id": "quick-sort"},
            ],
            "input": "9 " * MAX_INPUT_LENGTH,
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_visualize_rejects_unknown_fields(client: TestClient) -> None:
    """A typo must be a 422, not a silently-defaulted request."""
    headers = auth_headers(client)

    response = client.post(
        VISUALIZE.format("bubble-sort"),
        json={"input": SORT_SAMPLE, "max_frame": 5},
        headers=headers,
    )

    assert response.status_code == 422


def test_visualize_404s_for_an_unknown_algorithm(client: TestClient) -> None:
    headers = auth_headers(client)

    response = client.post(
        VISUALIZE.format("not-an-algorithm"), json={"input": SORT_SAMPLE}, headers=headers
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Algorithm not found."


def test_visualize_503s_when_the_lab_is_disabled(client: TestClient, db_engine) -> None:
    from database.seed import seed_demo_data

    seed_demo_data(Session(db_engine))
    factory = _LabClientFactory(db_engine)
    try:
        disabled = factory.with_settings(visualization_enabled=False).client()
        token = disabled.post(
            "/api/v1/auth/register",
            json={
                "name": "Off Lab",
                "email": "off.lab@example.com",
                "password": "correct-horse-battery-staple",
            },
        ).json()["access_token"]

        response = disabled.post(
            VISUALIZE.format("bubble-sort"),
            json={"input": SORT_SAMPLE},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 503
        assert "not enabled" in response.json()["detail"].lower()

        # The comparison route shares the switch, and a comparison that ignored it
        # would be a way to run workers on a deployment that asked for no workers.
        compared = disabled.post(
            COMPARE,
            json={
                "algorithms": [{"algorithm_id": "bubble-sort"}, {"algorithm_id": "quick-sort"}],
                "input": SORT_SAMPLE,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert compared.status_code == 503

        # The catalog is public and stays available when the workers are not: knowing
        # what the platform supports is not the same as making it run anything.
        assert disabled.get("/api/v1/algorithms").status_code == 200
    finally:
        factory.close()


# ------------------------------------------------------------------- the comparison


def test_compare_hands_every_side_the_same_input(client: TestClient) -> None:
    """The property the whole feature rests on.

    Not "the service intends to" -- the *response* proves it, because it echoes the
    one input back and each side reports the same result for it.
    """
    headers = auth_headers(client)

    response = client.post(
        COMPARE,
        json={
            "algorithms": [{"algorithm_id": "bubble-sort"}, {"algorithm_id": "quick-sort"}],
            "input": SORT_SAMPLE,
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["input"] == SORT_SAMPLE
    assert payload["comparison_group"] == "sort"
    assert len(payload["sides"]) == 2
    for side in payload["sides"]:
        assert side["status"] == "ok"
        # Both sorts see the same values, so both must arrive at the same answer.
        assert side["result"] == "1 2 3 5 7 9", side["algorithm"]["id"]


def test_compare_keeps_every_requested_side(client: TestClient) -> None:
    headers = auth_headers(client)

    response = client.post(
        COMPARE,
        json={
            "algorithms": [
                {"algorithm_id": "bubble-sort"},
                {"algorithm_id": "merge-sort"},
                {"algorithm_id": "heap-sort"},
            ],
            "input": SORT_SAMPLE,
        },
        headers=headers,
    )

    assert response.status_code == 200
    sides = response.json()["sides"]
    assert [side["algorithm"]["id"] for side in sides] == [
        "bubble-sort",
        "merge-sort",
        "heap-sort",
    ]


def test_compare_refuses_algorithms_that_solve_different_tasks(client: TestClient) -> None:
    """Refusing beats a plausible-looking table of nonsense.

    Bubble sort and Kadane's both take a list of integers, so a naive implementation
    would happily run both and print two runtimes. A learner would read the faster
    one as the better algorithm, which is a false claim rather than an imprecise one.
    """
    headers = auth_headers(client)

    response = client.post(
        COMPARE,
        json={
            "algorithms": [{"algorithm_id": "bubble-sort"}, {"algorithm_id": "kadane-max-subarray"}],
            "input": SORT_SAMPLE,
        },
        headers=headers,
    )

    assert response.status_code == 422
    detail = response.json()["detail"].lower()
    assert "same" in detail and "compare" in detail


def test_compare_needs_at_least_two_algorithms(client: TestClient) -> None:
    headers = auth_headers(client)

    response = client.post(
        COMPARE,
        json={"algorithms": [{"algorithm_id": "bubble-sort"}], "input": SORT_SAMPLE},
        headers=headers,
    )

    assert response.status_code == 422


def test_compare_refuses_more_sides_than_it_can_draw(client: TestClient) -> None:
    """The ceiling is enforced by the request schema, before anything is spawned.

    Six algorithms would mean six workers. Refusing at validation time is what keeps
    the cost of a comparison bounded by the schema rather than by the service's good
    behaviour.
    """
    headers = auth_headers(client)

    response = client.post(
        COMPARE,
        json={
            "algorithms": [
                {"algorithm_id": identifier}
                for identifier in (
                    "bubble-sort",
                    "selection-sort",
                    "insertion-sort",
                    "merge-sort",
                    "quick-sort",
                    "heap-sort",
                )
            ],
            "input": SORT_SAMPLE,
        },
        headers=headers,
    )

    assert response.status_code == 422
    detail = json.dumps(response.json())
    assert str(MAX_COMPARISON_SIDES) in detail


def test_compare_refuses_a_repeated_algorithm(client: TestClient) -> None:
    """Comparing an algorithm with itself would produce two identical columns."""
    headers = auth_headers(client)

    response = client.post(
        COMPARE,
        json={
            "algorithms": [{"algorithm_id": "bubble-sort"}, {"algorithm_id": "Bubble-Sort"}],
            "input": SORT_SAMPLE,
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_compare_404s_for_an_unknown_algorithm(client: TestClient) -> None:
    headers = auth_headers(client)

    response = client.post(
        COMPARE,
        json={
            "algorithms": [{"algorithm_id": "bubble-sort"}, {"algorithm_id": "no-such-thing"}],
            "input": SORT_SAMPLE,
        },
        headers=headers,
    )

    assert response.status_code == 404


def test_compare_never_invents_a_measurement(client: TestClient) -> None:
    """An unmeasured figure stays absent; the UI renders it as "Not measured".

    On a platform without ``getrusage`` -- Windows -- peak memory genuinely cannot be
    read. The field must be ``null``, not ``0.0``: a zero would render as "0 MB",
    which is a claim, and it would sort to the top of a memory column as if it were
    the most efficient algorithm.
    """
    headers = auth_headers(client)

    response = client.post(
        COMPARE,
        json={
            "algorithms": [{"algorithm_id": "bubble-sort"}, {"algorithm_id": "quick-sort"}],
            "input": SORT_SAMPLE,
        },
        headers=headers,
    )

    assert response.status_code == 200
    for side in response.json()["sides"]:
        assert side["peak_memory_mb"] is None or side["peak_memory_mb"] > 0
        assert side["runtime_ms"] is None or side["runtime_ms"] > 0


def test_compare_reports_counters_not_just_a_clock(client: TestClient) -> None:
    """A runtime alone is not a comparison anyone can learn from."""
    headers = auth_headers(client)

    response = client.post(
        COMPARE,
        json={
            "algorithms": [{"algorithm_id": "bubble-sort"}, {"algorithm_id": "merge-sort"}],
            "input": SORT_SAMPLE,
        },
        headers=headers,
    )

    assert response.status_code == 200
    for side in response.json()["sides"]:
        assert side["metrics"], f"{side['algorithm']['id']} reported no operation counts"
        assert side["repetitions"] >= 1
        assert side["frame_count"] >= 1


def test_compare_refuses_an_input_no_side_can_read(client: TestClient) -> None:
    """A grammar mismatch is one 422 for the request, not a failure in every column.

    All the sides share a group and therefore a grammar, so there is nothing a
    per-side failure would add here -- the learner needs to be told what to fix.
    """
    headers = auth_headers(client)

    response = client.post(
        COMPARE,
        json={
            "algorithms": [{"algorithm_id": "bubble-sort"}, {"algorithm_id": "quick-sort"}],
            "input": "9\n1 2 3",
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_compare_side_count_bounds_are_what_the_schema_advertises() -> None:
    assert MIN_COMPARISON_SIDES == 2
    assert MAX_COMPARISON_SIDES == 4


def test_graph_and_grid_markers_are_published_as_single_letters() -> None:
    """The path grid's alphabet is fixed, and the marker set is part of the contract.

    A grid that quietly accepted other letters would render a wall that looks
    walkable, and the traversal would find a path through it.
    """
    descriptor = get_algorithm("bfs-shortest-path")
    assert descriptor is not None
    assert GRID_ALPHABET == {"S", "G", "#", "."}
    case = descriptor.parse_input(descriptor.sample_input)
    assert case.grid[0][0] == GRID_START
    assert case.grid[-1][-1] == GRID_GOAL


def test_every_representative_algorithm_runs_through_the_api(client: TestClient) -> None:
    """One authenticated run per layout, so a worker that cannot start fails loudly."""
    headers = auth_headers(client)

    for identifier in REPRESENTATIVE_IDS:
        descriptor = get_algorithm(identifier)
        assert descriptor is not None
        response = client.post(
            VISUALIZE.format(identifier),
            json={"input": descriptor.sample_input},
            headers=headers,
        )
        assert response.status_code == 200, f"{identifier}: {response.text}"
        assert response.json()["frames"], identifier
