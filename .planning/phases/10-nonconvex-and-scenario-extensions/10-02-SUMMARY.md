---
phase: 10-nonconvex-and-scenario-extensions
plan: 02
subsystem: models
tags: [scenarios, robust, two-stage]
provides:
  - models/scenario.py join(), m4()
affects: []
tech-stack:
  added: []
  patterns: [M1 rows once per scenario, common columns shared]
key-files:
  created: [models/scenario.py]
  modified: []
key-decisions:
  - "Recourse after revelation is an information assumption, stated in the module"
duration: 20min
completed: 2026-09-29
status: complete
---

# Phase 10 Plan 02: M4

**Expected cost >= wait-and-see; worst case >= every scenario optimum and >= expected; every scenario's plan replays.**

## Task Commits
1. **M4** - `c98f16f`
