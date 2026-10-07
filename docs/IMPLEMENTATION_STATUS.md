# Implementation status

Checkpoint written against branch `main` at `cbdd1ef [origin/main]`, working tree
clean. It records what the repository contains now, not a roadmap.

## Verified commands

| Check | Command | Result |
| --- | --- | --- |
| Backend tests | `python -m pytest` | 683 passed, 8 warnings (181–270s depending on machine load) |
| Backend lint | `python -m ruff check backend database` | All checks passed |
| Frontend tests | `npm run test:frontend` | 233 passed (13 files) |
| Frontend lint | `npm run lint:frontend` | 0 errors, 2 warnings |
| Frontend typecheck | `npm run typecheck:frontend` | clean |
| Frontend build | `npm run build:frontend` | succeeds (chunk-size warning) |
| Whitespace | `git diff --check` | clean |

The judge and the judged-submission path account for 343 of the 683 backend
tests (`test_judge.py` 223, `test_submissions.py` 120); AI and visualization
account for a further 169 (`test_ai.py` 121, `test_visualization.py` 48); the
rest are auth, catalog, progress, migration, and platform suites.

| Suite | Tests |
| --- | --- |
| `test_judge.py` | 223 |
| `test_ai.py` | 121 |
| `test_submissions.py` | 120 |
| `test_progress.py` | 71 |
| `test_auth.py` | 57 |
| `test_visualization.py` | 48 |
| `test_migrations.py` | 19 |
| `test_schema.py` | 10 |
| `test_platform.py` | 6 |
| `test_problems.py` | 6 |
| `test_health.py` | 2 |

The two frontend lint warnings are pre-existing `react-refresh/only-export-components`
notes in `InsightBody.jsx` and `FrameRenderer.jsx`; they are warnings, not errors,
and ESLint exits 0.

No browser or live API verification has been done for this work. Every result
above comes from automated tests.

## Complete

**Accounts and auth.** Registration, login, `/auth/me`, and logout, with Argon2id
hashing, JWTs carrying no personal data, and `get_current_user` as the single
guard for every user-specific route.

**Catalog.** `GET /problems`, `GET /problems/{slug}`, and the dashboard summary,
served from a seeded catalog of 50 judge-ready problems — 10 Easy, 27 Medium,
13 Hard, across 12 primary topics.

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

**Algorithm visualization.** `GET /algorithms`, `GET /algorithms/categories`,
`GET /algorithms/problems/{slug}/algorithms`, `GET /algorithms/{algorithm_id}`,
`POST /algorithms/{algorithm_id}/visualize`, and `POST /algorithms/compare`,
backing the Visualizer and Compare pages with a real frame-by-frame trace.

**Grounded AI coach.** `POST /problems/{problem_id}/explanation`,
`POST /submissions/{submission_id}/diagnose`, and `POST /code/complexity`, with
`ExplanationPanel`, `DiagnosisPanel`, and `ComplexityPanel` in the workspace and
the submission detail. They fail closed without a provider credential rather
than returning canned prose.

## The problem catalog

Audited against the committed tree: 50 definitions, 50 slugs, no validation
errors, no duplicate slugs, no orphan definitions.

| | |
| --- | --- |
| Problems | 50 |
| Cases | 399 (197 visible, 202 hidden) |
| Cases per problem | 6 min, 10 max, 8.0 average |
| Examples | 74 |
| Hints | exactly 5 on every problem |
| Languages | python 50, javascript 50, java 36 (136 pairs) |
| Judge registry | `java`, `javascript`, `python` — identical to the advertised set |
| Time limits | 2000, 3000, 4000, or 5000 ms |
| Memory limit | 256 MB on every problem |
| Distinct topics | 44 |

Difficulty: Easy 10, Medium 27, Hard 13.

Primary topic: Arrays 10, Graphs 10, Dynamic Programming 4, Linked Lists 4,
Sorting 4, Trees 4, Binary Search 3, Bit Manipulation 3, Greedy 3, Heaps 3,
Stack 1, Strings 1.

Integrity: `test_every_reference_solution_passes_every_case` runs all 136
reference solutions against every case their problem defines — 136 passed. The
test fans those combinations out over a thread pool and judges each in its own
process, so the whole file is 223 tests in about a minute and a half rather than
a serial sweep that took three.

Leakage: a standalone probe fetched 61 responses (list, detail, and summary for
all 50 problems, plus the dashboard, algorithm registry, judge languages,
progress, run, submit, submission detail, and submission list) and confirmed no
hidden case input or expected output appears in any of them. The run endpoint
executes visible cases only, and no response object ever carries a hidden case
flag.

## The runner

The workspace's **Run** button executes the editor's contents in a separate worker
process, once per case, and grades the output against the problem's expected
output.

- Learner code never runs in the API process. `backend/app/judge/runner.py` starts
  `backend/app/judge/worker.py` per case with `python -I -B`, `node`, or
  `javac` followed by `java`, and the parent owns the clock, memory ceiling, and
  output cap. The worker inherits an explicit environment allow-list, so `TEMP`
  and `TMP` reach it and the JVM picks a writable `java.io.tmpdir` instead of
  falling back to `C:\Windows\` and paying a second of startup per case.
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
`EXECUTION_JAVASCRIPT`, `EXECUTION_JAVA`, and `MAX_JUDGE_WALL_CLOCK_MS` as the
per-request ceiling.

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
- **Judges Python, JavaScript, and Java.** Python and JavaScript are advertised
  for all 50 problems, Java for the 36 that ship a Java reference solution, and
  the advertised set is asserted against the judge registry so a language tab
  can never offer something the runner cannot execute.
- **Process startup dominates runtime.** Each case pays interpreter startup, so
  `runtime_ms` is the total judge time, not a clean measure of the learner's
  algorithm. This was worse for Java before `runner.py` passed an explicit
  environment to the worker: `TEMP` was dropped, `java.io.tmpdir` fell back to
  `C:\Windows\`, and every JVM start — each case's run and every `javac` — paid
  roughly a second of directory probing. Passing the allow-listed environment
  cut a worker-plus-JVM start from about 1500 ms to 275 ms and a `javac` from
  about 2270 ms to 960 ms.
- The frontend bundle exceeds Vite's 500 kB warning threshold (4,830 kB, 1,272 kB
  gzipped), largely from Monaco and the editor's language modes. Code splitting
  is not done.

## What is still a placeholder

**The interview feature.** `InterviewsPage` renders the intended four-stage loop
and states that session persistence and evaluation are not built. No interview
route, model, service, or state exists, and the page links to `/problems` rather
than pretending to start a session.

**AI without a credential.** The three AI routes are implemented but the default
deployment resolves to a disabled provider, so they answer `503` and
`GET /ai/status` reports why. The workspace labels the panels unavailable instead
of showing a generated-looking answer nobody generated.

Everything else listed as real above — catalog, progress, judging, submissions,
visualization, comparison — executes and is covered by the tests below.

## Test suites

Backend (683 tests):

- `test_judge.py` (223) — the runner, its limits, its honesty guarantees, and
  the catalog integrity sweep that judges every reference solution against every
  case
- `test_ai.py` (121) — provider resolution, fail-closed behaviour, and that no
  endpoint response carries hidden test data
- `test_submissions.py` (120) — judged submissions, each verdict, and their
  boundaries
- `test_progress.py` (71) — progress semantics and migration behavior
- `test_auth.py` (57) — auth, password policy, tokens, and that `password_hash`
  never reaches the OpenAPI contract
- `test_visualization.py` (48) — the algorithm registry, grammar, frame
  generation, and comparison
- `test_migrations.py` (19) — Alembic upgrade and downgrade behavior
- `test_schema.py` (10) — model and constraint shape
- `test_platform.py` (6) — health, readiness, CORS, and app wiring
- `test_problems.py` (6) — catalog endpoints and problem projection
- `test_health.py` (2) — liveness and readiness

Frontend (233 tests across 13 files):

- `features/judge/judge.test.jsx` — result presentation, language discovery, and
  the workspace run affordance
- `features/submissions/submissions.test.jsx` — verdict presentation, the
  verdict filter, and the submit flow
- `features/progress/progress.test.jsx` — progress semantics and the claim about
  what sets a problem solved
- `features/visualization/visualization.test.jsx` — trace frames, timeline
  controls, and comparison
- `features/auth/*` — the login and register flows, session restoration, and
  the password policy
- `features/problems/CodeEditor.test.jsx`, `ProblemCard.test.jsx` — the editor's
  language tabs and the catalog card
- `services/apiClient.test.js`, `features/submissions/submissionService.test.js`
  — the HTTP client and its token handling
- `components/layout/Topbar.test.jsx`, `components/ui/Feedback.test.jsx` — shared
  chrome
