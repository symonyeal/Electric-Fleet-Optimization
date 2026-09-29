---
phase: 08-convex-charging-subproblems
plan: 02
subsystem: models
tags: [perspective, barrier]
provides:
  - models/recharge.py fixed(): fixed-route R3 by the barrier method with Hessian blocks of q^2/tau
affects: [phase 9]
tech-stack:
  added: []
  patterns: [grid energy bounded by Q/eta + alpha Q^2/tau_min so (A5) is finite]
key-files:
  created: [models/recharge.py, tests/test_recharge.py]
  modified: []
key-decisions:
  - "Least dwell tau_min on used stations"
duration: 30min
completed: 2026-09-29
status: complete
---

# Phase 8 Plan 02: R3 at fixed routes

**At the optimal routes the barrier value equals R3's replayed cost and (A5) is within 1e-6 of it.**

## Task Commits
1. **Fixed-route R3** - `ccfb42a`
