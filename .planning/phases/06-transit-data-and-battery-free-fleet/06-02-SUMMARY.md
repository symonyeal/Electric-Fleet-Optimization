---
phase: 06-transit-data-and-battery-free-fleet
plan: 02
subsystem: models
tags: [m0, matching, min-cost-flow, interior-point]
provides:
  - models/network.py: compat(), m0()
  - checks/schedule.py: independent duty replay
  - methods/ipm.py: normal equations for LPs
affects: [phase 7]
tech-stack:
  added: []
  patterns: [three independent computations of one number]
key-files:
  created: [models/network.py, checks/schedule.py, tests/test_network.py]
  modified: [methods/ipm.py, tests/test_ipm.py]
key-decisions:
  - "Deadhead = 1.3 x great-circle km at 25 km/h, layover 5 min: illustrative"
  - "IPM uses dense normal equations for LPs with m <= 3000"
duration: 30min
completed: 2026-09-29
status: complete
---

# Phase 6 Plan 02: M0

**Route 100's battery-free fleet is 16 by matching LP, min-cost flow and Hopcroft-Karp; the 23 agency blocks are all feasible under the same deadhead model.**

## Accomplishments
- Dilworth check on ten random single-terminal timetables.
- On two tied matchings the IPM ends at their midpoint (four entries of 0.5); duties come from the vertex.
- Normal equations cut the Route 100 IPM solve from over five minutes to about one second.

## Task Commits
1. **M0 and normal equations** - `a4b8819`
