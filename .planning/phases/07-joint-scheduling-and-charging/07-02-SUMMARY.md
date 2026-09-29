---
phase: 07-joint-scheduling-and-charging
plan: 02
subsystem: models
tags: [m1, milp, replay, enumeration]
provides:
  - models/fleet.py: instance(), rows(), solution(), m1(), priority()
  - checks/schedule.py: replay_energy() (slot-by-slot energy, plugs, grid, cost)
  - checks/enum_transit.py: enum_m1() over path covers with their own charging MILP
affects: [phase 8, phase 9]
tech-stack:
  added: []
  patterns: [connection form without bus index (Models §3a)]
key-files:
  created: [models/fleet.py, checks/enum_transit.py, tests/test_fleet.py]
  modified: [checks/schedule.py, docs/MODELS.md, methods/branch.py]
key-decisions:
  - "Connection form instead of the per-bus time-space form: no symmetry; restrictions stated in Models §3a"
  - "Branch-and-bound dives until the first incumbent and branches scheduling arcs first"
duration: 90min
completed: 2026-09-29
status: complete
---

# Phase 7 Plan 02: M1

**M1 equals exhaustive enumeration on six tiny one-site timetables; every returned schedule replays; the IPM relaxation equals highs-ds; the educational tree certifies tiny M1 with scheduling-first priority.**

## Accomplishments
- Most-fractional branching reached its 10,000-node limit on 4- and 5-trip M1 instances; scheduling-first priority certified them in 105 and 193 nodes.
