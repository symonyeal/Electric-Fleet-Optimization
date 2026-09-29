---
phase: 03-exact-evrp-milp
plan: 01
subsystem: models
tags: [station-paths, pareto, floyd-warshall]
provides:
  - models/paths.py station_sp(), paths(): P_ij with (l, a, omega) and the node sequence
affects: [phase 3 plan 02, phase 5, phase 8]
tech-stack:
  added: []
  patterns: [Pareto filter over (length, energy at departure, energy at arrival)]
key-files:
  created: [models/paths.py, tests/test_paths.py]
  modified: []
key-decisions:
  - "Station-to-station legs by Floyd-Warshall on the station graph (arcs of energy at most Q), then Pareto filtering per customer pair"
duration: 40min
completed: 2026-09-29
status: complete
---

# Phase 3 Plan 01: Station paths

**E-n22-k4 has 462 ordered pairs with 2,600 Pareto station paths, at most 17 per pair; the kept set equals a brute-force dominance filter.**

## Task Commits
1. **Station graph and Pareto paths** - `9c7234d`
