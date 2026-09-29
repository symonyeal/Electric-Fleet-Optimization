---
phase: 01-foundations-and-evrp-data
verified: 2026-09-29T07:10:00Z
status: passed
score: 9/9 must-haves verified
covered_files:
  - ".github/workflows/ci.yml"
  - ".planning/REQUIREMENTS.md"
  - ".planning/phases/01-foundations-and-evrp-data/01-01-PLAN.md"
  - ".planning/phases/01-foundations-and-evrp-data/01-01-SUMMARY.md"
  - ".planning/phases/01-foundations-and-evrp-data/01-02-PLAN.md"
  - ".planning/phases/01-foundations-and-evrp-data/01-02-SUMMARY.md"
  - ".planning/phases/01-foundations-and-evrp-data/01-03-PLAN.md"
  - ".planning/phases/01-foundations-and-evrp-data/01-03-SUMMARY.md"
  - "checks/certificate.py"
  - "checks/route.py"
  - "data/evrp.py"
  - "data/evrp.sha256"
  - "docs/SOURCES.md"
  - "docs/TOOLCHAIN.md"
  - "pyproject.toml"
  - "requirements.txt"
  - "tests/fixtures/tiny.evrp"
  - "tests/test_certificate.py"
  - "tests/test_evrp_data.py"
  - "tests/test_route_replay.py"
  - "tests/test_toolchain.py"
covered_digest: "v1:sha256:6ec969bcb621ebd3458f2406f48149585e2cff72149ca48cda753f4198129dbe"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "The toolchain note states the SciPy/HiGHS versions and whether highs-ipm exposes duals before crossover"
    status: partial
    reason: "docs/TOOLCHAIN.md states SciPy 1.18.1 'with its bundled HiGHS' but no HiGHS version. The version is readable: scipy.optimize._highspy._core.HIGHS_VERSION_{MAJOR,MINOR,PATCH} = 1.12.0. The duals clause is answered only for early termination; the note is silent on the fact, measured here, that a converged solve with run_crossover='off' does return interior marginals."
    artifacts:
      - path: "docs/TOOLCHAIN.md"
        issue: "HiGHS version absent; converged crossover-off duals not stated"
      - path: "tests/test_toolchain.py"
        issue: "No test pins the HiGHS version or the presence of marginals on a converged crossover-off solve"
    missing:
      - "State 'HiGHS 1.12.0' in the measured-environment line of docs/TOOLCHAIN.md"
      - "State that a converged highs-ipm solve with run_crossover='off' returns ineqlin.marginals (measured: [-0.99999999, -1.8e-9] on the note's LP), and that an early-stopped one returns none"
      - "Optionally pin both in tests/test_toolchain.py"
human_verification:
  - test: "Push main to origin and read the 'checks' workflow run"
    expected: "setup-python 3.14 resolves; pytest -m 'not data and not slow' (31 tests), ruff check and pip check all exit 0 on ubuntu-latest"
    why_human: "main is 4 commits ahead of origin/main; the workflow has never run on these commits. The toolchain tests pin numerical behavior of trust-constr and HiGHS measured on Windows and may differ on Linux or on a newer SciPy that CI installs (requirements pin scipy>=1.14 only)."
---

# Phase 1: Foundations and EVRP data Verification Report

**Phase Goal:** A user can fetch the benchmark, read any instance, and replay any route file with a verdict that shares no code with any solver
**Verified:** 2026-09-29T07:10:00Z
**Status:** gaps_found
**Re-verification:** No, initial verification

The substance of the goal holds: all 41 files fetch fresh from 16d3499 and match the manifest, every instance parses, and the replay is stdlib-only and recomputes lengths from coordinates. One success criterion is partly unmet (the HiGHS version is not stated), and the GitHub Actions half of SC1 is unverified because the workflow has not run.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | SC1: pytest, ruff check, pip check pass on system Python 3.14, locally and in GitHub Actions | ? UNCERTAIN | Local: `py -3.14 -m pytest -q` exit 0 (34 passed); `-m data` 3 passed; `-m "not data and not slow"` (CI selection) 31 passed; `ruff check .` "All checks passed!"; `pip check` "No broken requirements found." Python 3.14.7. GitHub Actions: never run on these commits (`git rev-list --count origin/main..main` = 4). |
| 2 | SC2: all 41 instance files fetch from 16d3499, parse, and match their SHA-256 | ✓ VERIFIED | Independent fresh fetch via `data.evrp.fetch(KEYS, <scratch dir>)`: 41 files, 0 hash mismatches, 41 `load()` calls parse; byte-identical to `data/fetched/`. Manifest has 41 lines; COMMIT = 16d3499799ab7aa7bc3f11a5eaf8604947389462. |
| 3 | SC3: the validator names each defect in the hand-built fixtures and accepts the valid ones at hand-computed lengths | ✓ VERIFIED | `tests/test_route_replay.py` passes: missing, repeat, overload, battery on leg 3->1 into the depot, endpoint, unknown_node. Recomputed by hand on tiny.evrp: A = 5+3+4+4+sqrt(52), B = 10, total 26+sqrt(52); least battery 2 and 0; loads 7 and 5. All match the assertions. |
| 4 | SC4: toolchain note states SciPy/HiGHS versions and whether highs-ipm exposes duals before crossover | ✗ FAILED (partial) | SciPy 1.18.1 stated; HiGHS version absent (measured 1.12.0). Early-stop behavior stated and pinned (status 1/4, x = None, no duals). Converged crossover-off solve returns marginals; not stated. |
| 5 | record() gives a gap only when U and L are both finite and keeps a negative gap visible | ✓ VERIFIED | `checks/certificate.py` `_fin`, `g = None if U is None or L is None`; `defect="negative gap"` beyond tolerance; 5 tests pass. |
| 6 | Both header variants parse by keyword; section counts are checked | ✓ VERIFIED | Keys upper-cased from `k:v` lines; EDGE_WEIGHT_TYPE or EDGE_WEIGHT_FORMAT; DIMENSION, STATIONS, depot count, demand coverage checked; rejection tests for GEO, DIMENSION, STATIONS, missing demand pass; all 17 2019 and 24 2022 files parse. |
| 7 | evrp-python printed tours convert to the exchange format and replay | ✓ VERIFIED | Format checked against the pinned source: `objects/solution.py.__repr__` prints `Tour {i}: a -> b` and `objects/problem.py` stores `id = int(id) - 1` (0-based). `from_evrp_python` adds 1 and closes at the depot; test passes; on E-n22-k4, 21 printed tours round-trip exactly. No genuine GSGA output was replayed (that is EVRP-05, Phase 3). |
| 8 | checks/route.py imports nothing from models/ or methods/ | ✓ VERIFIED | Imports: `math`, `itertools.pairwise`, `re`. `checks/certificate.py` imports `math` only. Length recomputed with `math.hypot` from `p["X"]`, not the reader's `p["D"]`. `models/` and `methods/` hold empty `__init__.py`. |
| 9 | load(name) = fetch if absent, verify SHA-256, read | ✓ VERIFIED | `data/evrp.py` `load`; `test_checksum_mismatch` (one appended byte) raises "SHA-256"; fresh-fetch run above exercised the fetch branch. |

**Score:** 7/9 truths verified (0 present, behavior-unverified; 1 uncertain, 1 failed)

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `pyproject.toml` | pytest markers, ruff config | ✓ VERIFIED | markers `data`, `slow`; line length 100; ignores E741, I001, C408 |
| `requirements.txt` | numpy, scipy, pytest, ruff | ✓ VERIFIED | `ruff==0.16.7` matches installed |
| `.github/workflows/ci.yml` | 3.14; pytest, ruff, pip check on push to main | ✓ VERIFIED (not run) | Present and correct; no run exists |
| `checks/certificate.py` | STATUS, record, certified | ✓ VERIFIED | 38 lines, substantive; no callers yet (no solves exist in Phase 1) |
| `data/evrp.py` | read, fetch, load, KEYS | ✓ VERIFIED | Used by tests and by replay tests |
| `data/evrp.sha256` | 41 lines | ✓ VERIFIED | 41 lines, 17 in evrp-2019 |
| `checks/route.py` | replay, read/write_routes, from_evrp_python | ✓ VERIFIED | stdlib only |
| `docs/TOOLCHAIN.md` | versions and capability probes | ⚠️ PARTIAL | HiGHS version missing (gap) |
| `docs/SOURCES.md` | textbook re-check recorded | ⚠️ VERIFIED, encoding defect | Record present; file is no longer valid UTF-8 (see anti-patterns) |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `checks/route.py` | `models/`, `methods/` | must not import | ✓ WIRED (absent, as required) | grep finds only stdlib imports |
| `data.evrp.load` | `data/evrp.sha256` | hash check before read | ✓ WIRED | `SHA` dict built at import from the manifest |
| every model | `checks.certificate.record` | return value | N/A | No model exists in Phase 1; first applies in Phase 2 |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Fresh fetch at pinned commit matches manifest | `fetch(KEYS, scratch)`; hash each | 41 fetched, 0 mismatches, 41 parse | ✓ PASS |
| Replay a route file on a real instance | E-n22-k4, 21 out-and-back routes, write/read/replay | length 1165.5084865610368 vs sum 2 D[o,i] = 1165.5084865610365; defects: battery only (Q/h = 78.3 is short of the long round trips) | ✓ PASS |
| Defects named on a real instance | drop customer 2, repeat customer 4 | `missing customer 2`, `repeat customer 4 visited 2 times` | ✓ PASS |
| highs-ipm duals with crossover off, converged | `linprog(..., method="highs-ipm", run_crossover="off")` | status 0, x = (0.5, 0.5, 0.41), marginals (-0.99999999, -1.8e-9) | ✓ PASS (fact absent from note) |
| HiGHS version | `scipy.optimize._highspy._core.HIGHS_VERSION_*` | 1.12.0 | ✓ PASS (fact absent from note) |

### Probe Execution

No probes declared; no `scripts/*/tests/probe-*.sh`. Step 7c: SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| FND-01 | 01-01 | Install into system 3.14; pytest, ruff, pip check pass | ✓ SATISFIED | Local run above |
| FND-02 | 01-03 | Toolchain note: SciPy/HiGHS versions; milp, highs-ipm (duals before crossover), trust-constr | ✗ PARTIAL | HiGHS version absent; converged crossover-off duals unstated |
| FND-03 | 01-01 | Result record with Algorithms §8 taxonomy, U, L, gap only when both valid, solver code/message, residuals, time, provenance | ✓ SATISFIED (contract) | Taxonomy and gap rule enforced; code, message, residuals, time, provenance accepted through `**kw` but not required |
| FND-04 | 01-01 | GitHub Actions runs pytest and ruff on push to main | ? NEEDS HUMAN | Workflow correct; never run |
| DATA-01 | 01-02 | Fetch 41 files from pinned commit; every read verifies SHA-256 | ✓ SATISFIED | Fresh fetch; `load` verifies. `read(path)` alone does not hash, by design; `load` is the entry point |
| DATA-02 | 01-02 | Both header variants by keyword; section counts; reject other edge-weight types | ✓ SATISFIED | Truth 6 |
| DATA-03 | 01-02 | Textbook chapter references checked against both tables of contents | ✓ SATISFIED | Recorded in SOURCES.md. The PDFs are not on disk for the verifier; the cited chapters agree with the published tables of contents (Vanderbei 4th ed. Ch. 5, 12, 14-15, 17-20, 22-25; Beck 2014 Ch. 3-5, 7-8, 10-12) |
| CHK-01 | 01-03 | Replay: coverage, load, battery with depot legs, station and depot resets, route count, length from coordinates | ✓ SATISFIED | Resets are applied (y = Q at F or depot) but not listed in the output; coverage via missing/repeat |
| CHK-02 | 01-03 | Convert evrp-python printed tours and replay | ✓ SATISFIED | Truth 7 |

No orphaned requirements: REQUIREMENTS.md maps exactly these nine IDs to Phase 1, and all nine appear in plan frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `docs/SOURCES.md` | 14 | Byte 0xA7 (cp1252 section sign) written into a UTF-8 file; the file no longer decodes as UTF-8 and renders `�7.4` | ⚠️ Warning | Introduced by 9129972; the original at f784f5e was valid UTF-8. Replace the byte with `§` (C2 A7). |
| `docs/TOOLCHAIN.md` | 22-24 | Refers to evrp-python's "runner" supplying stub modules; no runner exists in the repository | ⚠️ Warning | States an unshipped artifact as present; belongs to EVRP-05 (Phase 3) |
| `checks/route.py` | 26-28 | A route with an unknown node is skipped whole, so its customers are also reported missing | ℹ️ Info | Extra defects, verdict still correct (not ok) |
| `data/list.txt` | - | Untracked stray file listing the 41 keys | ℹ️ Info | Delete or ignore before commit |

No TBD, FIXME, XXX, TODO or HACK markers in any phase file.

### Human Verification Required

### 1. First GitHub Actions run

**Test:** Push `main` to origin and open the `checks` workflow run.
**Expected:** Python 3.14 resolves on ubuntu-latest; 31 tests pass under `-m "not data and not slow"`; ruff and pip check exit 0.
**Why human:** The workflow has never run on these commits. The toolchain tests pin numerical behavior measured on Windows with SciPy 1.18.1, while CI installs the newest SciPy allowed by `scipy>=1.14`.

### Gaps Summary

One gap, documentation only: `docs/TOOLCHAIN.md` does not name the HiGHS version (1.12.0), which SC4 and FND-02 require, and it answers the duals question only for early termination; a converged crossover-off solve does return interior marginals. Both are one-line additions. Separately, SC1's GitHub Actions clause is unverified until the first push, and `docs/SOURCES.md` carries an invalid UTF-8 byte introduced in this phase. Everything the goal sentence names (fetch, read any instance, independent replay) is demonstrated.

---

_Verified: 2026-09-29T07:10:00Z_
_Verifier: Claude (gsd-verifier)_


## Gap Closure (2026-09-29, commit bb83948)

Re-checked by the orchestrator after the fixes; the independent verifier's findings above are
kept as written.

| Gap | Fix | Evidence |
|-----|-----|----------|
| TOOLCHAIN.md lacks the HiGHS version | States HiGHS 1.12.0 (from `scipy.optimize._highspy._core.HIGHS_VERSION_*`) | `docs/TOOLCHAIN.md` line 4 |
| Duals of a completed crossover-off solve not stated | Stated, and pinned: `test_highs_ipm_without_crossover_stops_inside_the_optimal_face` asserts `ineqlin.marginals is not None` | 86 passed locally |
| GitHub Actions never ran (FND-04, criterion 1) | Pushed `main` | Run 36533808267, workflow `checks`, Python 3.14: completed, success |
| SOURCES.md not UTF-8 | The single cp1252 byte replaced; every tracked file now decodes as UTF-8 | Checked over `git ls-files` |
| FND-03 fields optional | `record()` requires `solver`, `elapsed`, `provenance` (keyword-only) | `test_record_requires_solver_time_and_provenance` |
| Stub runner not in repo | TOOLCHAIN.md now says it arrives in Phase 3 (EVRP-05) | - |

**Status after closure:** passed, 9/9.
