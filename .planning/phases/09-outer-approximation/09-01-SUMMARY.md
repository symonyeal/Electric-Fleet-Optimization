---
phase: 09-outer-approximation
plan: 01
subsystem: methods
tags: [outer-approximation, convex-minlp]
provides:
  - methods/oa.py oa(): master MILP + tangent cuts, subproblem, validation, stall status
affects: [M2, R3]
tech-stack:
  added: []
  patterns: [a subproblem failure only adds cuts; no assignment is excluded without proof]
key-files:
  created: [methods/oa.py, tests/test_oa.py]
  modified: []
key-decisions:
  - "L is the master's HiGHS dual bound; U only from validated solutions"
duration: 20min
completed: 2026-09-29
status: complete
---

# Phase 9 Plan 01: OA engine

**Certifies min t, (x - 2.4)^2 <= t, x integer, at x = 2, t = 0.16 with nondecreasing bounds.**

## Task Commits
1. **Engine** - `ccfb42a`
