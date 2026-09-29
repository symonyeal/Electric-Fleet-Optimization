---
phase: 01-foundations-and-evrp-data
plan: 03
subsystem: checks
tags: [replay, toolchain]
provides:
  - checks/route.py: replay(), read_routes(), write_routes(), from_evrp_python()
  - docs/TOOLCHAIN.md and tests/test_toolchain.py
affects: [phase 3, phase 5, phase 8]
tech-stack:
  added: []
  patterns: [validator recomputes distances from coordinates]
key-files:
  created: [checks/route.py, tests/test_route_replay.py, tests/test_toolchain.py, docs/TOOLCHAIN.md]
  modified: []
key-decisions:
  - "Interior depot visits split routes; the route count is reported, vehicles are not a model quantity"
  - "evrp-python runs with stub modules for loguru, matplotlib, pandas"
duration: 20min
completed: 2026-09-28
status: complete
---

# Phase 1 Plan 03: Replay, evrp-python adapter, toolchain

**The replay names every defect of the hand-built fixtures, including an empty battery on the leg into the depot; SciPy's HiGHS IPM gives no early duals.**

## Accomplishments
- highs-ipm with run_crossover off and presolve off returns a point inside the optimal face; stopped early it returns neither point nor duals.
- trust-constr's accuracy follows its barrier parameter: 2e-4 at defaults on a two-variable QP, within 1e-9 when started at mu = 1e-8.

## Task Commits
1. **Replay, adapter, toolchain note** - `b34fe1b`
