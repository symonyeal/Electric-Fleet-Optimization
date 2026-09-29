---
phase: 02-interior-point-core
plan: 02
subsystem: methods
tags: [interior-point, bounds, early-termination]
provides:
  - bound() = (A3) for LPs, (A5) for convex QPs, at any iterate
  - delta early stop with status feasible_limit; per-iterate trace; factorization statistics
affects: [branch-and-bound, column generation]
tech-stack:
  added: []
  patterns: [mutation checks for tests written after the code they guard]
key-files:
  created: []
  modified: [methods/ipm.py, tests/test_ipm.py]
key-decisions:
  - "Failure to converge is `limit` or `numerical`, never `infeasible` (Algorithms §3)"
duration: 15min
completed: 2026-09-29
status: complete
---

# Phase 2 Plan 02: Bound, status, early stop, statistics

**(A3) never exceeds the highs-ds optimum at any iterate on 10 LPs; stopped at gap 1e-2 the method returns interior duals.**

## Accomplishments
- Vanderbei's §1.1 infeasible and unbounded examples end `numerical` or `limit`.
- These features were written before their tests. Each test was checked against a mutant of the code it guards: bound with max for min, delta ignored, limit reported as optimal, fixed variables kept. Every mutant fails its test.

## Task Commits
1. **Bound, statuses, early stop, statistics** - `9def26e`
