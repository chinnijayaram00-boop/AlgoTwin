"""Sandboxed code execution and judging.

The untrusted program in this platform is a learner's submission, so every rule
in this package exists to keep that program away from the web process:

* a learner's code is **never** executed inside the FastAPI process. Each run
  happens in a fresh worker process (:mod:`backend.app.judge.worker`), which in
  turn runs the learner's program as a grandchild with its own resource limits.
  A crash, a fork bomb, or a `sys.exit` in submitted code therefore cannot take
  the API down;
* the worker is started with `python -I`, and imports nothing from this
  repository, so the submitted program cannot reach AlgoTwin's settings,
  database URL, or JWT secret even if it can read files;
* the worker is given **one test case's stdin at a time** and is never told the
  expected output for any case. Comparison happens in the parent, which is the
  only process that holds both the hidden cases and the answers;
* a run is bounded in wall-clock time, CPU time, address space (where the
  runtime supports it) and output size, and a run that exceeds any bound is
  killed rather than reported as a slow success.

The platform-wide limits live in :mod:`backend.app.judge.limits`, the
per-language invocation details in :mod:`backend.app.judge.languages`, the
parent-side process supervision in :mod:`backend.app.judge.runner`, and the
verdict logic in :mod:`backend.app.judge.judge`.
"""
