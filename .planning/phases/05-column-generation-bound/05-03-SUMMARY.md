---
phase: 05-column-generation-bound
plan: 03
subsystem: models
tags: [column-generation, bounds, study]
provides:
  - models/colgen.py colgen(), restricted_milp(); run_case.py R2-ipm / R2-simplex
affects: [phase 11]
tech-stack:
  added: []
  patterns: [delta_{k+1} = max(delta_min, min(delta_max, gap_k / D)); dedupe before exact pricing]
key-files:
  created: []
  modified: [models/colgen.py, run_case.py]
key-decisions:
  - "R2's status is optimal only when U - L is certified; a converged LP with open gap is feasible_limit"
duration: 30min
completed: 2026-09-29
status: complete
---

# Phase 5 Plan 03: Loop, bounds, study

**E-n22-k4: R2 bound 380.5005 with interior and simplex duals (agreeing to 2e-9), 9.8 s against 39.3 s; restricted-master U 384.678093; certified gap 1.09%.**

## Accomplishments
- The bound equals the full set-partitioning LP, solved directly from all routes, on three tiny instances with both dual sources.
- Per-instance results for the other E instances are in docs/results (Phase 11 table).

## Task Commits
1. **Loop and bundles** - `e230421`, `9d1f340`, `6d50037`
