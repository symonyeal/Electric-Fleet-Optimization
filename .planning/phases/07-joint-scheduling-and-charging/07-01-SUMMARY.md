---
phase: 07-joint-scheduling-and-charging
plan: 01
subsystem: data
tags: [scenario, provenance]
provides:
  - data/scenario.py: load(), slot()
  - data/scenarios/route100.toml (illustrative throughout), data/scenarios/r3.toml
affects: [M1, M2, R3]
tech-stack:
  added: []
  patterns: [every value {value, unit, source}]
key-files:
  created: [data/scenario.py, data/scenarios/route100.toml, tests/test_scenario.py]
  modified: []
key-decisions:
  - "A value without unit and source is rejected, not defaulted"
duration: 10min
completed: 2026-09-29
status: complete
---

# Phase 7 Plan 01: Scenarios and slots

**Scenario values carry units and sources; the Route 100 scenario is illustrative in every value.**

## Task Commits
1. **Scenario loader** - `6d50037`
