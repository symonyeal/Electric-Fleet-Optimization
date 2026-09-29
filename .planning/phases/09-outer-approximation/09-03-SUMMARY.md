---
phase: 09-outer-approximation
plan: 03
subsystem: models
tags: [r3, perspective, partial-recharge]
provides:
  - models/recharge.py rows(), loss(), r3(), r3p(), routes_of(); checks/route.py replay_charge()
  - run_bench.py grid() (OA-04)
affects: [phase 11]
tech-stack:
  added: []
  patterns: [charge rows two-sided on used arcs]
key-files:
  created: [models/recharge.py, tests/test_recharge.py, data/scenarios/r3.toml]
  modified: [checks/route.py, run_bench.py]
key-decisions:
  - "The replay found one-sided charge rows letting a battery overfill; rows made equalities"
duration: 60min
completed: 2026-09-29
status: complete
---

# Phase 9 Plan 03: R3

**R3 with free charging equals R1 on three instances; under the declared scenario it is certified, inside R3-P, and replays with partial charges.**

## Task Commits
1. **R3** - `ccfb42a`
