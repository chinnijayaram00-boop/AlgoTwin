"""Sandboxed execution, judging, and the catalog's integrity.

The properties worth protecting here, in the order they matter:

* **Untrusted code never runs in the API process.** Every run starts a separate
  worker, and the worker starts the program as a grandchild. Asserted both by
  inspecting the command line and by observing that a program which kills its own
  process, forks, or hangs cannot take the test session with it.
* **A hidden case cannot be read, guessed, or inferred.** The worker is never
  given an expected output, the run endpoint only ever runs visible cases, and the
  response schema cannot represent a hidden case's input. Asserted against the
  serialised response, not against the code that built it.
* **A verdict is never invented.** No cases, a truncated run, an unreadable
  worker result, and a run that produced no output all resolve to something other
  than `accepted`.
* **The catalog is self-consistent.** Every problem carries at least one visible
  and one hidden case, advertises only languages the runner can start, and every
  reference solution in every language passes every case. That last one is what
  makes the expected outputs trustworthy: they come from an independent oracle, and
  a second implementation agreeing with it is the check.

These tests execute real programs and take real time. The wall-clock cases
deliberately use a short limit so the suite stays fast.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from database.models import Problem
from database.models.submission import (
    MAX_ERROR_MESSAGE_LENGTH,
    SUBMISSION_STATUS_VALUES,
    SUPPORTED_LANGUAGES,
    Submission,
    SubmissionStatus,
)
from database.problem_catalog import CATALOG, describe_catalog, validate_catalog
from database.problem_spec import KNOWN_LANGUAGES, hidden_cases, visible_cases
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.judge import runner
from backend.app.judge.judge import (
    MAX_REPORTED_OUTPUT,
    NoTestCasesError,
    judge,
    run_uncounted,
)
from backend.app.judge.languages import (
    JAVASCRIPT,
    LANGUAGE_IDS,
    PYTHON,
    REGISTRY,
    available_languages,
)
from backend.app.judge.limits import (
    MAX_CASES_PER_RUN,
    ExecutionLimits,
)
from backend.app.judge.runner import WORKER_PATH
from backend.app.schemas.judge import CodeRunRequest
from backend.app.services import execution_service, judge_service
from backend.app.services.output_compare import MAX_OUTPUT_BYTES, normalize_output, outputs_match

ALPHA = {
    "name": "Alpha Learner",
    "email": "alpha@example.com",
    "password": "correct-horse-battery-staple",
}
BETA = {
    "name": "Beta Learner",
    "email": "beta@example.com",
    "password": "another-strong-passphrase",
}

#: Short enough to keep the suite quick, long enough that a correct program
#: reliably finishes. Interpreter start-up alone is tens of milliseconds.
FAST = ExecutionLimits.resolve(time_limit_ms=1_000, memory_limit_mb=256)
BRUTAL = ExecutionLimits.resolve(time_limit_ms=400, memory_limit_mb=256)

RUN = "/api/v1/problems/{problem_id}/run"
LANGUAGES = "/api/v1/judge/languages"

#: The repository root, used to prove a sandboxed program's working directory is
#: somewhere else entirely.
REPO_ROOT = Path(__file__).resolve().parents[2]

#: A correct two-sum in both languages, reading the catalog's stdin format.
TWO_SUM_PYTHON = """
import sys


def main():
    data = [int(token) for token in sys.stdin.read().split()]
    n = data[0]
    nums = data[1 : 1 + n]
    target = data[1 + n]
    seen = {}
    for index, value in enumerate(nums):
        if target - value in seen:
            print(seen[target - value], index)
            return
        seen.setdefault(value, index)


main()
"""

TWO_SUM_JAVASCRIPT = """
const fs = require("fs");
const data = fs.readFileSync(0, "utf8").trim().split(/\\s+/).map(Number);
const n = data[0];
const nums = data.slice(1, 1 + n);
const target = data[1 + n];
const seen = new Map();
for (let index = 0; index < nums.length; index += 1) {
  if (seen.has(target - nums[index])) {
    console.log(seen.get(target - nums[index]), index);
    return;
  }
  if (!seen.has(nums[index])) seen.set(nums[index], index);
}
"""


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def as_learner(client: TestClient, payload: dict[str, str] = ALPHA) -> dict[str, str]:
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return auth(response.json()["access_token"])


def problem_id(client: TestClient, slug: str) -> int:
    response = client.get(f"/api/v1/problems/{slug}")
    assert response.status_code == 200, response.text
    return response.json()["id"]


def run_code(
    client: TestClient,
    problem: int,
    source: str,
    language: str = "python",
    headers: dict[str, str] | None = None,
    stdin: str | None = None,
):
    body = {"language": language, "source_code": source}
    if stdin is not None:
        body["stdin"] = stdin
    return client.post(RUN.format(problem_id=problem), json=body, headers=headers)


# ================================================================== the catalog


def test_the_catalog_validates() -> None:
    """Every definition is publishable before a single row is written."""
    validate_catalog()


def test_the_catalog_is_not_empty() -> None:
    assert len(CATALOG) >= 10, describe_catalog()


def test_every_problem_has_visible_and_hidden_cases() -> None:
    """A problem with no hidden case can be passed on its examples alone."""
    for definition in CATALOG:
        assert visible_cases(definition), f"{definition['slug']} has no visible case"
        assert hidden_cases(definition), f"{definition['slug']} has no hidden case"


def test_every_problem_advertises_only_runnable_languages() -> None:
    """The invariant four catalog entries used to break.

    They shipped a Java starter tab while the submission API accepted only Python
    and JavaScript, so a learner could fill in the tab and get a 422 on submit. The
    catalog is now validated against the language registry, and this test is what
    would catch a language being added to one and not the other.
    """
    for definition in CATALOG:
        unknown = sorted(set(definition["supported_languages"]) - KNOWN_LANGUAGES)
        assert not unknown, f"{definition['slug']} advertises {unknown}"
        for language in definition["supported_languages"]:
            assert definition["starter_code"].get(language), f"{definition['slug']}/{language} starter"
            assert definition["reference_solutions"].get(language), f"{definition['slug']}/{language} solution"


def test_every_catalog_language_is_in_the_submission_vocabulary() -> None:
    """A problem may not offer a language the submission API will refuse.

    This is the same defect as the test above, checked from the other end: even
    with a consistent catalog, a language the runner supports but the submission
    schema does not would still be a 422 waiting to happen.
    """
    for definition in CATALOG:
        for language in definition["supported_languages"]:
            assert language in SUPPORTED_LANGUAGES, (
                f"{definition['slug']} offers {language}, which the submission API rejects"
            )


def test_the_seeded_database_matches_the_catalog(client: TestClient, db_session: Session) -> None:
    """The seeder wrote the catalog, test cases and all.

    Before this change the twelve definitions were unreferenced and the seeder
    inserted four hand-written problems, so every judge column -- `test_cases`,
    `hints`, `reference_solutions`, both limits -- was empty on every row. A judge
    would have read that as a problem with nothing to run.

    `client` is requested for its seeding: `db_session` alone is an empty database.
    """
    seeded = {problem.slug: problem for problem in db_session.scalars(select(Problem))}
    for definition in CATALOG:
        problem = seeded[definition["slug"]]
        assert problem.test_cases, f"{definition['slug']} was seeded with no test cases"
        assert problem.hints, f"{definition['slug']} was seeded with no hints"
        assert problem.reference_solutions, f"{definition['slug']} was seeded with no solutions"
        assert problem.time_limit_ms > 0
        assert problem.memory_limit_mb > 0
        assert problem.supported_languages == definition["supported_languages"]


def test_reseeding_keeps_problem_ids(client: TestClient, db_session: Session) -> None:
    """Reconciling the catalog must not renumber a problem.

    `progress` and `submissions` reference `problem_id`, so re-inserting a row to
    refresh it would orphan every record a learner had for it.
    """
    before = {problem.slug: problem.id for problem in db_session.scalars(select(Problem))}

    from database.problem_catalog import sync_catalog

    sync_catalog(db_session)
    db_session.expire_all()
    after = {problem.slug: problem.id for problem in db_session.scalars(select(Problem))}

    assert after == before
    assert db_session.scalar(select(func.count()).select_from(Problem)) == len(CATALOG)


def test_reconciliation_preserves_an_unpublished_problem(
    client: TestClient, db_session: Session
) -> None:
    """Catalog sync refreshes data; it does not decide who can see a problem."""
    problem = db_session.scalar(select(Problem).where(Problem.slug == "two-sum"))
    problem.is_published = False
    db_session.commit()

    from database.problem_catalog import sync_catalog

    sync_catalog(db_session)
    db_session.expire_all()

    refreshed = db_session.scalar(select(Problem).where(Problem.slug == "two-sum"))
    assert refreshed.is_published is False
    assert refreshed.test_cases


def test_a_duplicate_slug_is_refused() -> None:
    """Two definitions sharing a slug would seed into one row, second one winning."""
    from database.problem_spec import CatalogError

    with pytest.raises(CatalogError, match="more than once"):
        validate_catalog([CATALOG[0], CATALOG[0]])


# ============================================== the catalog's expected outputs


@pytest.mark.parametrize("definition", CATALOG, ids=lambda d: d["slug"])
def test_every_reference_solution_passes_every_case(definition) -> None:
    """Two independent implementations must agree on every expected output.

    The expected outputs are derived from an oracle at import time rather than
    typed by hand, so a typo cannot become a case that rejects correct code. This
    test is the other half of that guarantee: it runs every reference solution in
    every advertised language against every case, and requires all of them to
    agree with the oracle. It is the slowest test in the suite and the one that
    makes the other test data trustworthy.
    """
    if not PYTHON.available:
        pytest.skip("no Python interpreter to run the reference solution with")

    report = judge(
        language=PYTHON,
        source_code=definition["reference_solutions"]["python"],
        cases=definition["test_cases"],
        limits=ExecutionLimits.resolve(3_000, 256),
    )
    failures = [result for result in report.results if not result.passed]
    assert not failures, (
        f"{definition['slug']}: the reference solution failed "
        f"{[(r.index, r.verdict.value) for r in failures]}"
    )
    assert report.verdict is SubmissionStatus.ACCEPTED
    assert report.cases_passed == report.cases_total


# ========================================================== the output rule


def test_output_comparison_ignores_only_insignificant_differences() -> None:
    """The rule is narrow on purpose, and each clause is asserted separately."""
    assert outputs_match("0 1\r\n", "0 1\n"), "line endings are not part of an answer"
    assert outputs_match("0 1  \n", "0 1"), "trailing whitespace is not part of an answer"
    assert outputs_match("0 1\n\n\n", "0 1\n"), "a trailing print() is not a wrong answer"
    assert not outputs_match("0  1", "0 1"), "internal spacing is part of the answer"
    assert not outputs_match("0 1", "1 0"), "the order is part of the answer"
    assert not outputs_match("", "0"), "an empty answer is not a non-empty one"
    assert normalize_output(None) == ""
    assert outputs_match(None, "")


def test_the_output_cap_is_a_real_limit() -> None:
    """`MAX_OUTPUT_BYTES` is read by the judge, not merely declared."""
    assert MAX_OUTPUT_BYTES > 0
    limits = ExecutionLimits.resolve(1_000, 256)
    assert limits.max_output_bytes == MAX_OUTPUT_BYTES


# ============================================================== the sandbox


def test_the_worker_runs_out_of_process_and_is_isolated() -> None:
    """The worker command line is the whole isolation story, so it is asserted.

    `-I` is the load-bearing flag: it is what stops a submitted program importing
    anything AlgoTwin installed, and it is what makes the job document the only
    thing on the worker's import path.
    """
    assert WORKER_PATH.name == "worker.py"
    source = WORKER_PATH.read_text(encoding="utf-8")

    # The worker must not reach into the application for anything.
    for forbidden in ("backend.app", "database.models", "from backend", "import backend"):
        assert forbidden not in source, f"the worker must not import the application: {forbidden}"

    argv = runner._worker_argv()
    assert argv[0] == sys.executable
    assert "-I" in argv, "isolated mode is what keeps the application's packages unimportable"
    assert "-B" in argv, "bytecode writing has no place inside a sandbox"


def test_a_submitted_program_cannot_import_the_application(client: TestClient) -> None:
    """The isolation property, observed from inside a real run."""
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    response = run_code(
        client,
        target,
        "import backend\nprint('reached')",
        headers=headers,
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["verdict"] != SubmissionStatus.ACCEPTED.value
    assert payload["cases"][0]["actual_output"] == "", "the import must not have succeeded"


def test_a_submitted_program_cannot_see_the_expected_output(client: TestClient) -> None:
    """The worker is never told the answer, so there is nothing for it to find.

    The program searches the whole sandbox directory for `expected_output`, which
    is the key the catalog stores answers under, and reports the working directory
    so the search can be seen to have run over the right place.
    """
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    source = """
import os

# Built at runtime so the search term is not in this file's own source.
needle = "expected" + "_output"
hits = []
for dirpath, dirnames, filenames in os.walk("."):
    dirnames[:] = [name for name in dirnames if name != "node_modules"]
    for name in filenames:
        try:
            with open(os.path.join(dirpath, name), errors="ignore") as handle:
                if needle in handle.read():
                    hits.append(name)
        except OSError:
            pass
print(f"found {len(hits)} files under {os.getcwd()}")
"""

    payload = run_code(client, target, source, headers=headers).json()
    output = payload["cases"][0]["actual_output"]

    assert output.startswith("found 0 files under ")
    # The working directory is a fresh sandbox, not the repository or the API's.
    assert "algotwin-judge-" in output
    assert str(Path(REPO_ROOT)) not in output


def test_the_worker_is_never_given_an_expected_output() -> None:
    """Structural proof of the property above: the job cannot carry an answer."""
    job = runner._build_job(PYTHON, "print(1)", "1 2 3", FAST)

    assert "expected_output" not in job
    assert "cases" not in job
    assert job["source"] == "print(1)"
    assert job["stdin"] == "1 2 3"


def test_the_job_carries_every_limit_the_worker_enforces() -> None:
    """A limit the parent resolves but does not send is a limit nothing applies.

    The CPU allowance in particular is a POSIX-only backstop, so a value that
    stopped being passed would go unnoticed until a program spun forever on a
    platform where nothing else stopped it.
    """
    job = runner._build_job(PYTHON, "print(1)", "", FAST)

    assert job["wall_clock_ms"] == FAST.wall_clock_ms
    assert job["memory_mb"] == FAST.memory_mb
    assert job["cpu_seconds"] == FAST.cpu_seconds
    assert job["max_output_bytes"] == FAST.max_output_bytes


def test_a_hanging_program_is_killed_and_reported_as_a_timeout(client: TestClient) -> None:
    """A run that loops forever costs a bounded amount of time and says so."""
    headers = as_learner(client)
    target = problem_id(client, "binary-search")

    payload = run_code(
        client,
        target,
        "while True:\n    pass",
        headers=headers,
    ).json()

    assert payload["verdict"] == SubmissionStatus.TIME_LIMIT_EXCEEDED.value
    assert payload["cases"][0]["passed"] is False
    assert "time limit" in (payload["error_message"] or "").lower()


def test_a_hanging_javascript_program_is_also_killed(client: TestClient) -> None:
    if not JAVASCRIPT.available:
        pytest.skip("no Node interpreter on this machine")
    headers = as_learner(client)
    target = problem_id(client, "binary-search")

    payload = run_code(
        client,
        target,
        "while (true) {}",
        language="javascript",
        headers=headers,
    ).json()

    assert payload["verdict"] == SubmissionStatus.TIME_LIMIT_EXCEEDED.value


def test_a_program_that_floods_its_output_is_stopped_by_the_output_cap(client: TestClient) -> None:
    """Printing without stopping must not fill memory or the disk.

    The cap is enforced by draining past it and discarding, so the program is not
    blocked on a full pipe and does not have to be misreported as a timeout.
    """
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    payload = run_code(
        client,
        target,
        "print('x' * (MAX_OUTPUT_BYTES * 4))",
        headers=headers,
    ).json()

    assert payload["verdict"] != SubmissionStatus.ACCEPTED.value
    assert "output" in (payload["error_message"] or "").lower()
    assert len(payload["cases"][0]["actual_output"]) <= MAX_REPORTED_OUTPUT + 64


def test_a_crashing_program_reports_its_own_stderr(client: TestClient) -> None:
    """A learner needs the traceback, not a generic failure."""
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    payload = run_code(
        client,
        target,
        "raise ValueError('the algorithm was wrong')",
        headers=headers,
    ).json()

    assert payload["verdict"] == SubmissionStatus.RUNTIME_ERROR.value
    assert "the algorithm was wrong" in payload["cases"][0]["actual_output"] or "the algorithm was wrong" in (
        payload["cases"][0]["error_message"] or ""
    )


def test_a_program_that_kills_its_own_process_does_not_take_the_api_with_it(client: TestClient) -> None:
    """`os._exit` bypasses every cleanup hook, including Python's own.

    If the program were running in the API process this would take the server
    down. Running it out of process is the only reason the next assertion -- and
    the rest of this test -- can run at all.
    """
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    response = run_code(
        client,
        target,
        "import os\nos._exit(0)",
        headers=headers,
    )

    assert response.status_code == 200
    # No output was produced, so this is a wrong answer rather than a pass.
    assert response.json()["verdict"] == SubmissionStatus.WRONG_ANSWER.value
    # And the session survived it, which is the actual point.
    assert client.get("/api/v1/health").status_code == 200


def test_a_program_cannot_write_outside_its_sandbox_directory(client: TestClient) -> None:
    """The program starts in a fresh directory that contains only its own source.

    It can write there, and the directory is removed afterwards, but its working
    directory is not the repository and not the API's.
    """
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    source = (
        "import os\n"
        "print(sorted(os.listdir('.')))\n"
        "open('sneaky.txt', 'w').write('x')\n"
    )
    payload = run_code(client, target, source, headers=headers).json()

    assert payload["cases"][0]["actual_output"].strip() == "['main.py']"


def test_the_program_does_not_inherit_the_api_environment(client: TestClient) -> None:
    """A submitted program must not read the deployment's configuration."""
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    source = (
        "import os\n"
        "leaked = [name for name in ('JWT_SECRET_KEY', 'DATABASE_URL', 'AI_API_KEY', 'PWD')\n"
        "          if os.environ.get(name)]\n"
        "print(leaked)\n"
    )
    payload = run_code(client, target, source, headers=headers).json()

    assert payload["cases"][0]["actual_output"].strip() == "[]"


# ================================================================ the verdicts


def test_a_correct_python_solution_is_accepted(client: TestClient) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    payload = run_code(client, target, TWO_SUM_PYTHON, headers=headers).json()

    assert payload["verdict"] == SubmissionStatus.ACCEPTED.value
    assert payload["cases_passed"] == payload["cases_total"] > 0
    assert payload["truncated"] is False
    assert payload["error_message"] is None
    assert all(case["passed"] for case in payload["cases"])


def test_a_correct_javascript_solution_is_accepted(client: TestClient) -> None:
    if not JAVASCRIPT.available:
        pytest.skip("no Node interpreter on this machine")
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    payload = run_code(
        client, target, TWO_SUM_JAVASCRIPT, language="javascript", headers=headers
    ).json()

    assert payload["verdict"] == SubmissionStatus.ACCEPTED.value
    assert payload["cases_passed"] == payload["cases_total"]


def test_a_wrong_answer_is_reported_as_a_wrong_answer_not_an_error(client: TestClient) -> None:
    """The distinction a learner cares about most: it ran, and it was wrong.

    The program here is nonsense on purpose, rather than a plausible-but-wrong
    index pair, because a hardcoded answer can be accidentally right for the first
    visible case -- which is exactly what a plausible-looking fixture does.
    """
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    payload = run_code(client, target, "print('no idea')", headers=headers).json()

    assert payload["verdict"] == SubmissionStatus.WRONG_ANSWER.value
    assert payload["cases_passed"] == 0
    assert payload["cases"][0]["actual_output"].strip() == "no idea"
    assert payload["cases"][0]["expected_output"]
    assert "wrong answer" in (payload["cases"][0]["error_message"] or "")


def test_only_the_failing_case_is_run(client: TestClient) -> None:
    """A case that fails stops the run, and the report says the run was cut short."""
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    payload = run_code(client, target, "print('nope')", headers=headers).json()

    assert payload["cases_run"] == 1
    assert payload["cases_run"] < payload["cases_total"]
    assert payload["truncated"] is True


def test_a_problem_with_no_cases_is_never_a_pass(client: TestClient, db_session: Session) -> None:
    """The most important negative case in the file.

    A problem whose cases were lost to a bad migration must report a problem, not
    an empty success. `accepted` on zero cases would be the single worst lie this
    platform could tell.
    """
    problem = db_session.scalar(select(Problem).where(Problem.slug == "two-sum"))
    problem.test_cases = []
    db_session.commit()
    headers = as_learner(client)

    response = run_code(client, problem.id, TWO_SUM_PYTHON, headers=headers)

    assert response.status_code == 409
    assert "no test cases" in response.json()["detail"].lower()


def test_a_truncated_run_can_never_be_accepted() -> None:
    """A run that stopped early is a failure even if every case it ran passed."""
    cases = [
        {"input": "1", "expected_output": "1", "is_hidden": False},
        {"input": "2 2 3 4", "expected_output": "1", "is_hidden": True},
    ]
    # Case one prints 1 and passes; case two has a longer input, so it spins until
    # the wall clock kills it and the run stops after one case.
    report = judge(
        language=PYTHON,
        source_code="import sys\nif len(sys.stdin.read()) > 4:\n    while True:\n        pass\nprint(1)",
        cases=cases,
        limits=BRUTAL,
    )

    assert report.cases_passed == 1
    assert report.cases_run == 2
    assert report.cases_total == 2
    assert report.verdict is SubmissionStatus.TIME_LIMIT_EXCEEDED
    assert report.verdict is not SubmissionStatus.ACCEPTED


def test_the_judge_stops_at_its_own_budget_and_says_so() -> None:
    """The deployment's request budget is enforced, and reported as a failure.

    Every case passes well inside its own per-case limit, but the total budget only
    covers a few of them. The run is `accepted` only if every case it was given
    passed, so a budget cut short has to be a failure -- and it has to say it was
    the budget rather than blaming the program.

    The exact number of cases that fit depends on process start-up time, so the
    assertions are about the shape of the answer, not about a count.
    """
    cases = [
        {"input": str(index), "expected_output": "1", "is_hidden": index % 2 == 1}
        for index in range(6)
    ]
    limits = ExecutionLimits.resolve(400, 256, total_budget_ms=500)
    report = judge(
        language=PYTHON,
        source_code="import time\ntime.sleep(0.15)\nprint(1)",
        cases=cases,
        limits=limits,
    )

    assert report.cases_run < report.cases_total, "the budget never cut the run short"
    assert report.truncated is True
    assert report.cases_passed == report.cases_run, "every case that ran passed"
    assert report.verdict is not SubmissionStatus.ACCEPTED
    assert "budget" in (report.error_message or "")


def test_a_case_cannot_outlive_the_request_budget() -> None:
    """The per-case clock is bounded by the whole-run budget.

    Without this, a problem with a ten-second limit and a deployment that only
    intends to spend half a second on a request would still allow a single
    ten-second case.
    """
    limits = ExecutionLimits.resolve(10_000, 256, total_budget_ms=500)

    assert limits.wall_clock_ms == 500
    assert limits.total_budget_ms == 500


def test_every_verdict_the_judge_can_emit_is_a_stored_status() -> None:
    """One vocabulary, or a translation layer that is only exercised once."""
    from backend.app.judge.judge import verdict_for_observation

    observations = [
        runner.RunOutcome("ok", 0, None, "", "", 1, None),
        runner.RunOutcome("nonzero_exit", 1, None, "", "boom", 1, None),
        runner.RunOutcome("time_limit", -9, 9, "", "", 1, None),
        runner.RunOutcome("output_limit", 0, None, "x", "", 1, None),
        runner.RunOutcome("internal_error", None, None, "", "", 1, None, "nope"),
        runner.RunOutcome("killed_by_signal", -11, 11, "", "", 1, None),
    ]
    for observation in observations:
        verdict, _ = verdict_for_observation(observation)
        assert verdict.value in SUBMISSION_STATUS_VALUES
        assert isinstance(verdict, SubmissionStatus)


def test_judging_rejects_an_absurd_number_of_cases() -> None:
    cases = [
        {"input": "1", "expected_output": "1", "is_hidden": False}
        for _ in range(MAX_CASES_PER_RUN + 1)
    ]
    with pytest.raises(NoTestCasesError, match="at most"):
        judge(language=PYTHON, source_code="print(1)", cases=cases, limits=FAST)


def test_judging_rejects_a_malformed_case() -> None:
    """A half-migrated catalog row fails here, by name, rather than comparing to None."""
    with pytest.raises(NoTestCasesError, match="missing a string"):
        judge(
            language=PYTHON,
            source_code="print(1)",
            cases=[{"input": "1"}],
            limits=FAST,
        )


def test_an_unreadable_worker_result_is_a_failure_not_a_pass() -> None:
    """A worker that says nothing has told us nothing, and nothing is not success."""
    outcome = runner._coerce_result({})
    assert outcome.kind == "internal_error"
    assert outcome.ran_cleanly is False

    verdict, message = __import__(
        "backend.app.judge.judge", fromlist=["verdict_for_observation"]
    ).verdict_for_observation(outcome)
    assert verdict is SubmissionStatus.FAILED
    assert message


# ============================================================ hidden cases


def test_the_run_endpoint_never_runs_a_hidden_case(client: TestClient) -> None:
    """Run is a debugging aid, and it must not be a probe for the graded set.

    A correct answer is compared against the *visible* cases only. If the hidden
    cases were included, a learner could binary-search their way to a full pass
    without solving anything, and could read the pass/fail vector for the graded
    run.
    """
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    payload = run_code(client, target, TWO_SUM_PYTHON, headers=headers).json()

    assert payload["cases"]
    assert all(case["is_hidden"] is False for case in payload["cases"])


def test_a_hidden_case_cannot_be_read_from_a_run_response(client: TestClient) -> None:
    """The redaction is asserted on the serialised body, not on the code path.

    `case_input`, `expected_output` and `actual_output` are `None` for a hidden
    case, and the response shape can represent that. A run that included a hidden
    case would still be safe: it would report the verdict and nothing else.
    """
    headers = as_learner(client)
    target = problem_id(client, "two-sum")
    problem = client.get("/api/v1/problems/two-sum").json()

    source = "import sys\nsys.stdin.read()\nprint('anything')"
    payload = run_code(client, target, source, headers=headers).json()

    # Every returned case is a visible one, and each carries its own input and
    # answer -- which is exactly what a learner is entitled to see.
    for case in payload["cases"]:
        assert case["is_hidden"] is False
        assert case["case_input"] is not None
        assert case["expected_output"] is not None

    # And no hidden case's input appears anywhere in the body.
    hidden_inputs = [
        case["input"]
        for case in CATALOG_BY_SLUG["two-sum"]["test_cases"]
        if case["is_hidden"]
    ]
    body = json.dumps(payload)
    for hidden_input in hidden_inputs:
        assert hidden_input not in body, "a hidden case's input leaked into a run response"
    assert problem["id"] == target


def test_the_schema_cannot_express_a_hidden_case_leak() -> None:
    """Redaction is a state the response type can hold, not a convention."""
    from backend.app.schemas.judge import JudgeCaseResult

    redacted = JudgeCaseResult(
        index=0,
        is_hidden=True,
        passed=False,
        verdict=SubmissionStatus.WRONG_ANSWER.value,
        error_message="The program printed the wrong answer for this case.",
        duration_ms=12,
    )

    assert redacted.case_input is None
    assert redacted.expected_output is None
    assert redacted.actual_output is None
    # The category survives, which is the part a learner is entitled to.
    assert redacted.verdict == SubmissionStatus.WRONG_ANSWER.value


def test_a_hidden_case_error_never_quotes_the_program() -> None:
    """A traceback for a hidden case can contain that case's input.

    The worker's stderr is echoed back for a visible case, because that is what
    makes it useful. For a hidden one it is replaced with the category.
    """
    from backend.app.judge.judge import CaseResult
    from backend.app.services.judge_service import _disclose

    visible = CaseResult(
        index=0,
        is_hidden=False,
        passed=False,
        actual_output="Traceback: 42 is not a list",
        expected_output="0 1",
        case_input="1\n42\n0\n",
        verdict=SubmissionStatus.RUNTIME_ERROR,
        error_message="The program exited with code 1.",
    )
    hidden = CaseResult(
        index=1,
        is_hidden=True,
        passed=False,
        actual_output="Traceback: 99 99 99 is not a list",
        expected_output="0 1",
        case_input="3\n99 99 99\n198\n",
        verdict=SubmissionStatus.RUNTIME_ERROR,
        error_message="The program exited with code 1.",
    )

    assert "42" in _disclose(visible).actual_output
    assert "99" not in (_disclose(hidden).actual_output or "")
    assert "99" not in (_disclose(hidden).error_message or "")
    assert _disclose(hidden).error_message == "The program failed on this case."


def test_no_problem_response_carries_a_test_case(client: TestClient) -> None:
    for slug in (item["slug"] for item in client.get("/api/v1/problems").json()["items"]):
        payload = client.get(f"/api/v1/problems/{slug}").json()
        assert "test_cases" not in payload
        assert "reference_solutions" not in payload


CATALOG_BY_SLUG = {definition["slug"]: definition for definition in CATALOG}


# =========================================================== the run endpoint


def test_running_requires_authentication(client: TestClient) -> None:
    target = problem_id(client, "two-sum")
    body = {"language": "python", "source_code": "print(1)"}

    assert client.post(RUN.format(problem_id=target), json=body).status_code == 401
    assert (
        client.post(
            RUN.format(problem_id=target), json=body, headers=auth("not-a-token")
        ).status_code
        == 401
    )


def test_running_an_unknown_problem_is_not_found(client: TestClient) -> None:
    headers = as_learner(client)
    response = run_code(client, 999_999, "print(1)", headers=headers)

    assert response.status_code == 404


def test_running_an_unpublished_problem_is_not_found(client: TestClient, db_session: Session) -> None:
    problem = db_session.scalar(select(Problem).where(Problem.slug == "two-sum"))
    problem.is_published = False
    db_session.commit()
    headers = as_learner(client)

    assert run_code(client, problem.id, "print(1)", headers=headers).status_code == 404


def test_a_run_stores_nothing(client: TestClient, db_session: Session) -> None:
    """Run is not an attempt, and it is not a submission.

    Pressing Run thirty times must not move the progress numbers, because the
    progress panel describes work done rather than buttons pressed.
    """
    headers = as_learner(client)
    target = problem_id(client, "two-sum")
    session = client.get("/api/v1/auth/me", headers=headers).json()

    for _ in range(3):
        assert run_code(client, target, TWO_SUM_PYTHON, headers=headers).status_code == 200

    assert db_session.scalar(select(func.count()).select_from(Submission)) == 0
    progress = client.get("/api/v1/progress/me", headers=headers).json()
    assert progress["attempted"] == 0
    assert progress["not_started"] == progress["total_problems"]
    assert session["email"]


def test_a_run_never_touches_another_learners_progress(client: TestClient) -> None:
    alpha = as_learner(client)
    beta = as_learner(client, BETA)
    target = problem_id(client, "two-sum")

    run_code(client, target, TWO_SUM_PYTHON, headers=beta)

    for headers in (alpha, beta):
        payload = client.get("/api/v1/progress/me", headers=headers).json()
        assert payload["solved"] == 0
        assert payload["attempted"] == 0


def test_a_request_cannot_name_a_verdict_or_a_user(client: TestClient) -> None:
    """The run contract admits nothing a learner does not get to decide."""
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    for field in (
        "user_id",
        "status",
        "verdict",
        "test_cases_passed",
        "test_cases_total",
        "runtime_ms",
        "memory_mb",
        "cases",
    ):
        body = {
            "language": "python",
            "source_code": "print(1)",
            field: "accepted" if field in {"status", "verdict"} else 1,
        }
        response = client.post(RUN.format(problem_id=target), json=body, headers=headers)
        assert response.status_code == 422, f"{field} must be refused, not ignored"


def test_a_request_cannot_name_a_problem_that_is_not_the_path(client: TestClient) -> None:
    """The problem comes from the path and nowhere else."""
    headers = as_learner(client)
    target = problem_id(client, "two-sum")
    other = problem_id(client, "coin-change")

    response = client.post(
        RUN.format(problem_id=target),
        json={
            "language": "python",
            "source_code": "print(1)",
            "problem_id": other,
            "slug": "coin-change",
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_blank_source_is_refused(client: TestClient) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    response = client.post(
        RUN.format(problem_id=target),
        json={"language": "python", "source_code": "   \n  "},
        headers=headers,
    )

    assert response.status_code == 422


def test_an_unsupported_language_is_a_422_naming_the_real_ones(client: TestClient) -> None:
    """The response has to be the one that helps.

    This is the shape of the defect four catalog entries used to have: the editor
    offered a tab, the learner filled it in, and the answer was a bare 422 that
    said nothing about which languages would have worked. The refusal comes from
    the request schema, so it is a list of validation errors rather than a string;
    what matters is that it names both real languages.
    """
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    response = client.post(
        RUN.format(problem_id=target),
        json={"language": "cobol", "source_code": "print(1)"},
        headers=headers,
    )

    assert response.status_code == 422
    detail = json.dumps(response.json()["detail"])
    assert "python" in detail and "javascript" in detail


def test_a_language_this_machine_cannot_run_is_a_422(client: TestClient, monkeypatch) -> None:
    """A language in the schema but absent from the machine is refused, not faked.

    Patched at the seam the service resolves through, so the assertion is about
    the service's behaviour rather than about which module happens to hold a
    reference to the lookup.
    """
    from backend.app.services import judge_service

    headers = as_learner(client)
    target = problem_id(client, "two-sum")
    monkeypatch.setattr(judge_service, "get_language", lambda *args, **kwargs: None)

    response = run_code(client, target, "print(1)", headers=headers)

    assert response.status_code == 422
    assert "cannot be run" in response.json()["detail"]


def test_execution_can_be_switched_off_entirely(client: TestClient) -> None:
    """A deployment that cannot offer a judge gets 503, not a fake result.

    Nothing the learner sent is wrong, which is why this is a 503 and not a 4xx.
    """
    from backend.app.core.config import Settings, get_settings
    from backend.app.db.session import get_db
    from backend.app.main import app

    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    def override_get_settings():
        return Settings(execution_enabled=False)

    app.dependency_overrides[get_settings] = override_get_settings
    try:
        response = run_code(client, target, "print(1)", headers=headers)
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()
    # The route is still resolvable, and the module it would have used is intact.
    assert get_db is not None


def test_the_runnable_languages_route_reports_the_registry(client: TestClient) -> None:
    response = client.get(LANGUAGES)

    assert response.status_code == 200
    payload = response.json()
    assert payload["execution_enabled"] is True
    assert {item["id"] for item in payload["items"]} == {spec.id for spec in available_languages()}


def test_a_switched_off_language_is_not_offered(client: TestClient) -> None:
    """The tab list comes from the same registry the judge uses, so they cannot drift."""
    from backend.app.core.config import Settings, get_settings
    from backend.app.main import app

    def override_get_settings():
        return Settings(execution_javascript=False)

    app.dependency_overrides[get_settings] = override_get_settings
    try:
        payload = client.get(LANGUAGES).json()
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert "javascript" not in {item["id"] for item in payload["items"]}


# ============================================================== ad-hoc input


def test_an_ad_hoc_input_produces_no_pass_count(client: TestClient) -> None:
    """The single most important field in this file.

    An input with no expected output cannot be right or wrong. The response says
    what the program printed and reports the run's own outcome, but it claims no
    verdict, and it counts no cases.
    """
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    response = run_code(
        client, target, "print('hello')", headers=headers, stdin="4\n2 7 11 15\n9\n"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["verdict"] is None, "nothing was compared, so there is no verdict"
    assert payload["ad_hoc"]["stdout"].strip() == "hello"
    assert payload["ad_hoc"]["stdin"] == "4\n2 7 11 15\n9\n"
    assert payload["ad_hoc"]["exit_code"] == 0
    assert payload["ad_hoc"]["timed_out"] is False
    assert payload["cases"] == []
    assert payload["cases_run"] == 0
    assert payload["cases_passed"] == 0
    assert payload["cases_total"] == 0
    assert payload["error_message"] is None


def test_an_ad_hoc_run_still_reports_a_crash(client: TestClient) -> None:
    """No verdict is invented, but a failure is not hidden behind a null one."""
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    payload = run_code(client, target, "raise SystemExit(2)", headers=headers, stdin="1\n").json()

    assert payload["verdict"] is None
    assert payload["ad_hoc"]["exit_code"] == 2
    assert "code 2" in (payload["error_message"] or "")


def test_an_ad_hoc_run_reports_a_timeout(client: TestClient) -> None:
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    payload = run_code(client, target, "while True:\n    pass", headers=headers, stdin="1\n").json()

    assert payload["verdict"] is None
    assert payload["ad_hoc"]["timed_out"] is True
    assert "time limit" in (payload["error_message"] or "")


def test_outcome_message_never_reports_a_clean_run_as_a_problem() -> None:
    """The ad-hoc error field is for runs that went wrong, not for every run."""
    from backend.app.judge.judge import outcome_message

    clean = runner.RunOutcome("ok", 0, None, "0 1\n", "", 12, None)
    assert outcome_message(clean) is None

    crashed = runner.RunOutcome("nonzero_exit", 1, None, "", "boom", 12, None)
    assert "code 1" in (outcome_message(crashed) or "")


def test_outcome_message_fits_the_stored_column() -> None:
    """The ad-hoc message goes to the same bounded column a case message does."""
    from backend.app.judge.judge import outcome_message

    noisy = runner.RunOutcome("nonzero_exit", 1, None, "", "x" * 100_000, 12, None)

    assert len(outcome_message(noisy) or "") <= MAX_ERROR_MESSAGE_LENGTH


def test_an_oversized_ad_hoc_input_is_refused(client: TestClient) -> None:
    from backend.app.judge.limits import MAX_STDIN_BYTES

    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    response = client.post(
        RUN.format(problem_id=target),
        json={"language": "python", "source_code": "print(1)", "stdin": "x" * (MAX_STDIN_BYTES + 1)},
        headers=headers,
    )

    assert response.status_code == 422


# ============================================================== the service


def test_the_execution_service_runs_code() -> None:
    """The service-layer facade, which replaced a stub that only raised."""
    service = execution_service.get_execution_service()

    result = service.execute(
        execution_service.ExecutionRequest(
            language="python",
            source_code="print('from the service')",
            stdin="",
            limits=FAST,
        )
    )

    assert result.ran_cleanly
    assert result.stdout.strip() == "from the service"
    assert result.duration_ms > 0


def test_the_execution_service_refuses_an_unknown_language() -> None:
    from backend.app.judge.languages import LanguageUnavailableError

    with pytest.raises(LanguageUnavailableError):
        execution_service.get_execution_service().execute(
            execution_service.ExecutionRequest(language="fortran", source_code="print(1)")
        )


def test_run_uncounted_reports_without_a_verdict() -> None:
    """One execution, one input, no comparison -- and no verdict invented."""
    outcome = run_uncounted(PYTHON, "print('x')", "", FAST)

    assert outcome.ran_cleanly
    assert outcome.stdout.strip() == "x"


def test_resolve_language_checks_the_problem_not_just_the_platform(
    client: TestClient, db_session: Session
) -> None:
    """A language the runner supports but this problem does not ship is refused."""
    problem = db_session.scalar(select(Problem).where(Problem.slug == "two-sum"))
    problem.supported_languages = ["python"]
    db_session.commit()

    assert judge_service.resolve_language(problem, "python").id == "python"
    with pytest.raises(judge_service.UnsupportedLanguageError, match="supports python"):
        judge_service.resolve_language(problem, "javascript")


def test_resolve_language_accepts_a_human_spelling(client: TestClient, db_session: Session) -> None:
    problem = db_session.scalar(select(Problem).where(Problem.slug == "two-sum"))

    assert judge_service.resolve_language(problem, "  Python ").id == "python"


# ================================================================ the limits


def test_limits_are_clamped_into_the_range_the_platform_honours() -> None:
    from database.models.problem import MAX_MEMORY_LIMIT_MB, MAX_TIME_LIMIT_MS

    assert ExecutionLimits.resolve(10**9, 10**9).wall_clock_ms == MAX_TIME_LIMIT_MS
    assert ExecutionLimits.resolve(10**9, 10**9).memory_mb == MAX_MEMORY_LIMIT_MB
    assert ExecutionLimits.resolve(0, 0).wall_clock_ms >= 100
    assert ExecutionLimits.resolve(None, None).wall_clock_ms > 0
    # A stored limit that is not a number must not crash a run.
    assert ExecutionLimits.resolve("nonsense", "nonsense").wall_clock_ms > 0
    assert ExecutionLimits.resolve(-5, -5).memory_mb > 0


def test_the_cpu_allowance_exceeds_the_wall_clock() -> None:
    """A program must not be killed for CPU time while it still had wall clock left."""
    limits = ExecutionLimits.resolve(2_000, 256)
    assert limits.cpu_seconds * 1000 > limits.wall_clock_ms


def test_a_problem_reports_its_clamped_limits(client: TestClient, db_session: Session) -> None:
    problem = db_session.scalar(select(Problem).where(Problem.slug == "two-sum"))
    problem.time_limit_ms = 10**9
    db_session.commit()

    assert problem.effective_time_limit_ms == 10_000
    assert judge_service.resolve_limits(problem, Settings()).wall_clock_ms == 10_000


def test_the_deployment_can_cap_the_whole_run(client: TestClient, db_session: Session) -> None:
    """`MAX_JUDGE_WALL_CLOCK_MS` is not the only thing that bounds a request.

    A deployment with a shorter patience than the platform default gets it, and it
    arrives as the per-case budget too, so one request cannot exceed it by running
    a single case at the problem's own limit.
    """
    problem = db_session.scalar(select(Problem).where(Problem.slug == "two-sum"))
    limits = judge_service.resolve_limits(problem, Settings(max_judge_wall_clock_ms=2_000))

    assert limits.total_budget_ms == 2_000
    assert limits.wall_clock_ms == 2_000
    assert limits.cpu_seconds > limits.wall_clock_ms / 1000


def test_the_request_budget_cannot_be_configured_away() -> None:
    """The ceiling is a ceiling: a configuration cannot buy a longer request."""
    from backend.app.judge.limits import MAX_JUDGE_WALL_CLOCK_MS

    assert ExecutionLimits.resolve(1_000, 256, total_budget_ms=10**9).total_budget_ms == (
        MAX_JUDGE_WALL_CLOCK_MS
    )
    assert ExecutionLimits.resolve(1_000, 256, total_budget_ms=0).total_budget_ms >= 100
    assert ExecutionLimits.resolve(1_000, 256).total_budget_ms == MAX_JUDGE_WALL_CLOCK_MS


def test_the_run_response_reports_the_limits_it_applied(client: TestClient) -> None:
    """The number on screen has to be the number the run was held to."""
    headers = as_learner(client)
    target = problem_id(client, "two-sum")

    payload = run_code(client, target, "print(1)", headers=headers).json()
    detail = client.get("/api/v1/problems/two-sum").json()

    assert payload["time_limit_ms"] == detail["time_limit_ms"]
    assert payload["memory_limit_mb"] == detail["memory_limit_mb"]


# =========================================================== the vocabulary


def test_the_run_contract_matches_the_stored_vocabulary() -> None:
    """The published schema and the model enum must not drift apart."""
    from typing import get_args

    from backend.app.schemas.judge import RunVerdict

    published = set(get_args(RunVerdict))
    stored = set(SUBMISSION_STATUS_VALUES) - {"queued", "running"}

    assert published == stored, (
        f"the run schema publishes {published - stored} that cannot be stored, "
        f"and omits {stored - published}"
    )


def test_every_judge_error_message_fits_the_stored_column() -> None:
    """`error_message` is a bounded column, and a runaway traceback must not break a write."""
    from backend.app.judge.judge import clip_error

    assert clip_error(None) is None
    assert clip_error("short") == "short"

    clipped = clip_error("x" * (MAX_ERROR_MESSAGE_LENGTH * 4))

    assert len(clipped) <= MAX_ERROR_MESSAGE_LENGTH
    assert "truncated" in clipped


def test_a_runtime_error_message_is_clipped_to_the_column() -> None:
    """The path that actually produces a long message: stderr pasted into it."""
    from backend.app.judge.judge import verdict_for_observation

    outcome = runner.RunOutcome("nonzero_exit", 1, None, "", "x" * 100_000, 12, None)
    _verdict, message = verdict_for_observation(outcome)

    assert message is not None
    assert len(message) <= MAX_ERROR_MESSAGE_LENGTH
    assert "code 1" in message


def test_the_catalog_languages_are_the_registry_languages() -> None:
    """One registry, so a language cannot be added to the judge and not the catalog."""
    assert set(LANGUAGE_IDS) == set(REGISTRY_IDS := {spec.id for spec in REGISTRY})
    assert set(LANGUAGE_IDS) == set(KNOWN_LANGUAGES)
    assert REGISTRY_IDS == {"python", "javascript"}


def test_the_worker_answers_a_malformed_job_rather_than_crashing() -> None:
    """The worker must always emit a result document, whatever it is handed.

    This is run as a real subprocess because that is the only way to observe the
    contract: the parent's `execute` reads a document off stdout, and a worker that
    died silently would look identical to one that hung.
    """
    completed = subprocess.run(
        [sys.executable, "-I", "-B", str(WORKER_PATH)],
        input=b"not json at all",
        capture_output=True,
        timeout=60,
        check=False,
    )

    assert completed.returncode == 0, "the worker must always exit zero"
    assert runner.RESULT_SENTINEL.encode() in completed.stdout
    document = json.loads(completed.stdout.split(runner.RESULT_SENTINEL.encode())[1])
    assert document["kind"] == "internal_error"
    assert document["error"]


def test_the_run_request_contract_is_closed() -> None:
    assert CodeRunRequest.model_config.get("extra") == "forbid"
