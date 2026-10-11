# Dependency vulnerability scanning

Algotwin scans its dependencies for known vulnerabilities on every push to
`main` and every pull request, in the `security` job of
`.github/workflows/ci.yml`. The job is independent of the `backend` and
`frontend` jobs so a scan failure cannot mask, or be masked by, a test result.

This document covers the two scanners, how to run them locally, the severity
policy, and what to do when a finding appears. It is not a claim that the
project is vulnerability-free; it is the process for finding and handling
advisories.

## The two scans

| Ecosystem | Tool | Input | Advisories from |
| --- | --- | --- | --- |
| Python | [`pip-audit`](https://github.com/pypa/pip-audit) 2.10.1 | `backend/requirements.txt` | [OSV](https://osv.dev/) |
| Node.js | `npm audit` (via `scripts/audit-npm.mjs`) | `package-lock.json` | GitHub Advisory Database |

The Node.js scan runs against the committed `package-lock.json`, the same
lockfile `npm ci` installs from in the `frontend` job, so the audit sees exactly
the dependency tree CI builds. The Python scan resolves the compatibility ranges
in `backend/requirements.txt` against PyPI (see
[Resolution and reproducibility](#resolution-and-reproducibility)).

## Run the scans locally

From the repository root.

Python:

```powershell
python -m pip install pip-audit==2.10.1
python -m pip_audit -r backend/requirements.txt --vulnerability-service osv
```

Node.js:

```powershell
npm ci
node scripts/audit-npm.mjs --threshold=high
```

`scripts/audit-npm.mjs` wraps `npm audit` because `npm audit` exits non-zero as
soon as *any* advisory exists and therefore cannot express a severity threshold
on its own. The wrapper fails when an advisory at or above `--threshold`
(default `high`) is not explicitly accepted, and it prints every advisory it saw,
including the ones below the threshold and the ones that were accepted.

## Resolution and reproducibility

- **Node.js** is reproducible today: `package-lock.json` is committed and `npm
  ci` installs the pinned tree, so the same lockfile produces the same audit on
  any machine. The repository root `.npmrc` sets `legacy-peer-deps=true` to work
  around an npm 10 arborist crash on vitest's optional peer set (see
  [Current standing](#current-standing)).
- **Python** is not yet fully pinned. `backend/requirements.txt` declares direct
  dependencies as ranges (`fastapi>=0.115,<1`, `pytest>=8.3,<9`, ...) and the
  transitive tree is resolved by pip at install and at audit time. The scan is
  therefore reproducible only up to the versions pip resolves from PyPI on the
  day it runs. Pinning the tree (`pip-compile` / `uv pip compile` with hashes) is
  the follow-up that would make the Python audit as reproducible as the Node
  one; it is not done here, on purpose, so this change does not introduce a lock
  file that could drift out of sync with `requirements.txt`.

## Severity policy

- **`pip-audit` fails on any advisory.** pip-audit 2.x has no severity filter:
  the finding list is whatever the advisory source returns, so the gate is
  "clean or explained". Python dependencies here are the runtime and test
  surface, which is small enough to keep at that bar.
- **`npm audit` fails at `high`** (`--threshold=high`). The Node tree is much
  larger and mostly build/test tooling (`vite`, `vitest`, `esbuild`). An advisory
  below `high` is still **printed** on every run; it simply does not block the
  build. Raise or lower this by editing the `--threshold` value in the workflow.

An advisory is **never silenced by a config toggle**. Accepting one is an
explicit, reviewed decision: add an `--ignore=<id>@<severity>#<reason>` argument
to the `npm audit` step. The reason is free text, and the accepted advisories are
printed on every run, so the acceptance is visible in the CI log rather than
hidden. For Python, use `pip-audit --ignore-vuln <ID>` with a comment explaining
why, and a link to the tracking issue or fix version.

Because a clean scan only means "no advisory in the databases the tool queried
today", a passing job is never treated as proof the project is vulnerability-free.

## Current standing

Both scans are clean on the current `main`. The findings that were present are
recorded below with the change that cleared each one, so the resolution is
reviewable rather than implied by a green job. This is a snapshot; re-run the
scans for the live list.

Python (`pip-audit`, as resolved on the current `main`):

| Package | Advisory | Was | Fix | Notes |
| --- | --- | --- | --- | --- |
| `pytest` | `PYSEC-2026-1845` / `CVE-2025-71176` / `GHSA-6w46-j5rx-g56g` | 8.4.2 | 9.0.3+ | Development dependency, never imported by the running API. `backend/requirements.txt` now declares `pytest>=9.0.3,<10`; the advisory affects every release before 9.0.3. |

`pytest-asyncio` was moved from `>=0.25,<1` to `>=1.4,<2` in the same change,
because its 0.x releases cap `pytest<9` and would otherwise pin the audit back
to the vulnerable pytest. The suite has no async tests, so the plugin bump is
behavior-neutral here.

Node.js (`npm audit`, 0 of the former 11 advisories remain):

| Package | Severity | Was | Fix |
| --- | --- | --- | --- |
| `vitest` | critical | 2.1.9 | 4.1.11 |
| `@vitest/mocker` | moderate | 2.1.9 | 4.1.11 (transitive) |
| `tinypool` | critical | 1.1.1 | removed: vitest 4 no longer depends on it |
| `vite` (nested) | high | 5.4.21 | deduped to the app's `vite` 6.4.3 |
| `vite-node` | moderate | 2.1.9 | removed: vitest 4 no longer depends on it |
| `esbuild` (nested) | moderate | 0.21.5 | deduped to the app's `esbuild` 0.25.12 |
| `react-router` / `react-router-dom` | moderate | 6.30.6 | 7.18.4 |
| `dompurify` | low | 3.4.15 | 3.4.16 (overridden under `monaco-editor`) |
| `monaco-editor` | low | 0.57.0 | kept at 0.57.0; the advisory was only its pinned `dompurify` |
| `source-map-js` | high | 1.2.1 | 1.2.2 |

Decisions worth reviewing:

- **`vitest` was taken to `4.1.11`, not the `5.0.3` that `npm audit` suggests.**
  4.1.11 is the first release that clears the `vitest` and `@vitest/mocker`
  advisories, it drops the vulnerable `tinypool`/`vite-node` chain entirely, and
  -- unlike vitest 5 -- it still supports Node 20, which the `frontend` and
  `security` CI jobs and the README pin. vitest 5 requires Node >= 22.12.
- **`dompurify` is pinned exactly (`3.4.15`) by `monaco-editor@0.57.0`**, so the
  patched `3.4.16` is forced with an `overrides` entry in the root
  `package.json` instead of changing the editor version.
- **The repository root `.npmrc` sets `legacy-peer-deps=true`.** npm 10's
  arborist crashes ("Cannot read properties of null (reading 'edgesOut')")
  while building the peer set for vitest's optional peers, so a from-scratch
  resolution cannot complete without it. `npm ci` and `npm install` both work
  from the committed lockfile with this setting. Because it turns off automatic
  peer installation, peers the app actually uses (`@testing-library/dom`) are
  declared directly in `frontend/package.json`.

## When a finding appears

1. Read the advisory and the affected path. Confirm whether the package is in
   the shipped runtime or only in build/test tooling.
2. Prefer a fix: upgrade the package (`npm audit fix` for a non-breaking Node
   bump, or raise the range in `backend/requirements.txt` for Python) and run the
   `backend` and `frontend` jobs to confirm nothing regressed.
3. If a fix does not yet exist, or the upgrade is a breaking major that needs its
   own change, accept it only with an entry that records the advisory id, the
   severity, a reason, and a tracking pointer. For Node.js, add it to the
   `--ignore` list in the workflow; for Python, add `--ignore-vuln <ID>` with a
   comment.
4. Re-check accepted advisories whenever the dependency is next upgraded.
