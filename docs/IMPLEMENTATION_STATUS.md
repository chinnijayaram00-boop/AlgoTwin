# Implementation status

Checkpoint written against branch `main` at `57201a8 [origin/main]`. It records
what the working tree contains now, not a roadmap.

## Verified commands

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `python -m pytest` | 343 passed, 3 warnings |
| Backend lint | `python -m ruff check backend database` | All checks passed |
| Frontend tests | `npm run test:frontend` | 176 passed (11 files) |
| Frontend lint | `npm run lint:frontend` | clean |
| Frontend typecheck | `npm run typecheck:frontend` | clean |
| Frontend build | `npm run build:frontend` | succeeds (pre-existing chunk-size warning) |

The judge and the judged-submission path account for 208 of the 343 backend
tests (`test_judge.py` 88, `test_submissions.py` 120); the rest are the auth,
catalog, and progress suites that existed before it.

No browser or live API verification has been done for this work. Every result
above comes from automated tests.

## Complete

**Accounts and auth.** Registration, login, `/auth/me`, and logout, with Argon2id
hashing, JWTs carrying no personal data, and `get_current_user` as the single
guard for every user-specific route.

**Catalog.** `GET /problems`, `GET /problems/{slug}`, and the dashboard summary,
served from a seeded catalog of 12 judge-ready problems (4 Easy, 8 Medium).

**Learner progress.** `GET /progress/me`, `GET /progress/problems`,
`GET|PUT /progress/problems/{problem_id}`,
`POST /progress/problems/{problem_id}/attempt` — scoped to the signed-in learner,
idempotent on write, with legacy labels still readable.

**Judged submissions.** `GET|POST /submissions`, `GET /submissions/{submission_id}`,
and `GET /problems/{problem_id}/submissions`. `POST` runs the judge synchronously
and stores the graded record; described below.

**Judge and code execution.** `GET /judge/languages` and
`POST /problems/{problem_id}/run`, described below.

**Progress UI.** Dashboard panel, per-problem panel, status pills, submission
history with a verdict filter, and a submissions page.

## The runner

The workspace's **Run** button executes the editor's contents in a separate worker
process, once per case, and grades the output against the problem's expected
output.

- Learner code never runs in the API process. `backend/app/judge/runner.py` starts
  `backend/app/judge/worker.py` per case with `python -I -B` or `node`, and the
  parent owns the clock, memory ceiling, and output cap.
- A worker is given the source, the input, and the limits. It is never given the
  expected output.
- Only visible cases are disclosed. Hidden cases run and can decide the verdict,
  but their input, expected output, and actual output are all `null` in the
  response.
- Verdicts come from the `SubmissionStatus` model, so the run vocabulary and the
  submission vocabulary cannot drift.
- A run with a learner-supplied input returns `verdict: null` and `cases_run: 0`.
  It reports the exit code and output without inventing a correctness claim.
- Nothing persists. No submission, no attempt, no progress write.

Settings: `EXECUTION_ENABLED` (kill switch, answers `503`), `EXECUTION_PYTHON`,
`EXECUTION_JAVASCRIPT`, and `MAX_JUDGE_WALL_CLOCK_MS` as the per-request ceiling.

## Judged submissions

`POST /submissions` takes only `problem_id`, `language`, and `source_code`. The
learner sends nothing else, so a request cannot assert its own verdict.

- The submission is stored first, then judged synchronously by the same runner
  the **Run** button uses, over the visible cases *and* the hidden ones.
- The stored row is then updated with the real outcome: `status`, `runtime_ms`,
  `test_cases_passed`, `test_cases_total`, `memory_mb`, `error_message`, and
  `judged_at`. A row therefore always says what actually happened to it.
- Progress advances to **solved** only when the stored row's status is
  `accepted`. The gate reads the persisted row rather than the in-memory
  judgement, so a demotion — an earlier accept re-judged as failing — cannot
  mark a problem solved.
- The verdict vocabulary is the `SubmissionStatus` model, so the run vocabulary
  and the submission vocabulary still cannot drift. Compilation failure is
  `compilation_error`.
- A graded row carries counts, never per-case data, so no hidden input or
  expected output is stored and none can leak through the API.
- The client waits 60s for the POST. The generic client default is 10s, which
  would abandon a submit the server went on to store and grade.
The frontend treats the verdict as the point of the exercise: the workspace
shows it after submitting, the detail view shows the counts and measurements,
and the history can be filtered by verdict. A measurement the judge did not take
(`memory_mb` on Windows) is omitted rather than shown as zero, and a row the
judge never reached reads "Not judged" with no facts attached.

**Unjudged rows are expected.** The `e_judged_submissions` migration adds
`judged_at` without inventing one, so every submission stored before judging
existed keeps its `queued` status and stays unjudged forever. That is the honest
record — nothing ever ran them — and the UI reports them as "Not judged" rather
than guessing. A `queued` row is also what a submit leaves behind if execution
is switched off mid-request (a 503); the switch being off before the request
starts is a 422 and stores nothing.

## Known limits, stated plainly

- **Not a hardened sandbox.** The runner contains the failure modes it is built
  and tested for — hangs, runaway memory, crashes, output floods. It has no
  container, seccomp, cgroup, separate user, or network denial, so it is not a
  boundary against a determined attacker. Untrusted public input needs a
  container, a VM, or Windows Job Objects around the worker.
- **Windows is weaker than Linux.** `RLIMIT_AS` and `RLIMIT_CPU` do not exist
  there, so the memory ceiling is best-effort and `memory_mb` is `null`
  rather than an estimate. Tests assert the weaker contract on Windows.
- **Judging is synchronous.** A submit blocks for the judge to finish. The server's
  budget is `MAX_JUDGE_WALL_CLOCK_MS` (30s by default, capped at 600s) and the
  client waits 60s, so the client is the outer net rather than the usual limit —
  if the server is raised above 60s the client will give up on a submit the
  server went on to store and grade. There is no queue and no background worker,
  so a concurrent batch of submits competes for CPU, and the row's real verdict is
  the one already committed by the time any client stops waiting.
- **Judges Python and JavaScript only.** Java catalog entries were removed rather
  than left as tabs that cannot run.
- **Process startup dominates runtime.** Each case pays interpreter startup, so
  `runtime_ms` is the total judge time, not a clean measure of the learner's
  algorithm.
- The frontend bundle exceeds Vite's 500 kB warning threshold (666 kB), largely
  from Monaco. Code splitting is not done.

## Placeholders

`GET /algorithms` returns a contract with no execution behind it, and
`GET /ai/status` reports a disabled provider. AI explanations, algorithm
visualization, and the interview feature have no implementation. The UI labels
each of them as unavailable rather than simulating a result.

## Test suites

- `backend/tests/test_auth.py` — auth, password policy, tokens, and that
  `password_hash` never reaches the OpenAPI contract
- `backend/tests/test_platform.py` — health, readiness, CORS, and app wiring
- `backend/tests/test_problems.py` — catalog endpoints and problem projection
- `backend/tests/test_progress.py` — progress semantics and migration behavior
- `backend/tests/test_submissions.py` — judged submissions, each verdict, and
  their boundaries
- `backend/tests/test_judge.py` — the runner, its limits, and its honesty
  guarantees
- `frontend/src/features/judge/judge.test.jsx` — result presentation, language
  discovery, and the workspace run affordance
- `frontend/src/features/submissions/submissions.test.jsx` — verdict
  presentation, the verdict filter, and the submit flow
- `frontend/src/features/progress/progress.test.jsx` — progress semantics and the
  claim about what sets a problem solved
