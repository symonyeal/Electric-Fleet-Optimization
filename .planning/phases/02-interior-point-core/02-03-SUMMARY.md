---
phase: 02-interior-point-core
plan: 03
subsystem: methods
tags: [interior-point, qp]
provides:
  - convex QP through the same ipm() with Q in the (1,1) block
affects: [M1-Q, convex subproblems]
tech-stack:
  added: []
  patterns: [exact active-set enumeration as independent check]
key-files:
  created: []
  modified: [tests/test_ipm.py]
key-decisions:
  - "Independent check is exact enumeration of active sets, not a Vanderbei Ch. 24 example"
duration: 10min
completed: 2026-09-29
status: complete
---

# Phase 2 Plan 03: Convex QP

**Ten random strictly convex box QPs agree with exact active-set enumeration to 1e-7; KKT residuals below 1e-8.**

## Task Commits
1. **QP tests** - `9def26e`
