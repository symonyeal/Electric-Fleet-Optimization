---
phase: 02-interior-point-core
plan: 01
subsystem: methods
tags: [interior-point, lp]
provides:
  - methods/ipm.py: ipm(), standard(), bound()
affects: [branch-and-bound, column generation, convex subproblems]
tech-stack:
  added: []
  patterns: [quasi-definite augmented system solved by sparse LU]
key-files:
  created: [methods/ipm.py, tests/test_ipm.py]
  modified: []
key-decisions:
  - "Augmented (quasi-definite) system rather than normal equations: one code path for LP and QP"
  - "standard() gives slacks upper bounds implied by the box, so (A3) is finite"
duration: 25min
completed: 2026-09-29
status: complete
---

# Phase 2 Plan 01: Primal-dual LP method

**Solves Vanderbei (2.1) to 13 at (2, 0, 1) and agrees with highs-ds on 20 random bounded LPs.**

## Accomplishments
- Fixed variables are eliminated before the barrier acts.
- A regression found while refactoring: shifted variables were restored as x instead of l + x. Five tests with nonzero lower bounds now fail on that defect and pass on the fix.

## Task Commits
1. **Method and tests** - `9def26e` (LP method, fix and QP committed together)
