---
phase: 03-exact-evrp-milp
plan: 02
subsystem: models
tags: [milp, mtz, highs, enumeration]
provides:
  - models/route.py rows(), r0(), r1(), r1tr(): one row builder for R0 and R1, and the report's formulation with the depot split
  - checks/enum.py route(), enum(): exhaustive optimum on small instances, independent of models/
  - run_case.py evrp: result bundles with replayed routes
affects: [phase 4, phase 5, phase 11]
tech-stack:
  added: []
  patterns: [lifted MTZ rows (Desrochers-Laporte); U is always the replayed length]
key-files:
  created: [models/route.py, checks/enum.py, tests/test_route_models.py, run_case.py]
  modified: [data/evrp.py]
key-decisions:
  - "The report's MILP is infeasible as written at the depot (u_0 = C); R1-TR splits the depot into a source and a sink"
  - "R1 returns infeasible, not an exception, when a customer has no station path"
duration: 90min
completed: 2026-09-29
status: complete
---

# Phase 3 Plan 02: R0, R1, R1-TR and enumeration

**R1, R1-TR and enumeration agree on the fixture, 8 self-made and 3 E-n22-k4 sub-instances; enumeration found a precedence error in R1-TR's load row.**

E-n22-k4 in 600 s: R0 certified at 375.279787; R1 feasible at U = 384.678093 with L = 341.25.

## Deviations
- The random instance generator produced 7 infeasible instances out of 8; fixed so every test instance is feasible.

## Task Commits
1. **R0, R1, R1-TR, enumeration** - `15a7d58`
2. **Rows as data, run_case.py, baseline runner** - `2196226`
