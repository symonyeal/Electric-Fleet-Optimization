---
phase: 05-column-generation-bound
plan: 02
subsystem: models
tags: [pricing, labeling, ng-routes]
provides:
  - models/colgen.py price(), ng_sets(); checks/enum.py route()
affects: []
tech-stack:
  added: []
  patterns: [labels (cbar, load, charge, ng-memory) on the station-path multigraph]
key-files:
  created: []
  modified: [models/colgen.py, checks/enum.py]
key-decisions:
  - "Heuristic pricing caps labels per node and never produces a bound"
duration: 20min
completed: 2026-09-29
status: complete
---

# Phase 5 Plan 02: Pricing

**Exact pricing equals brute-force least reduced cost over every elementary route on four random dual vectors.**

## Task Commits
1. **Pricing** - `e230421`
