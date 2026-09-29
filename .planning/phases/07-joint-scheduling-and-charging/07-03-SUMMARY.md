---
phase: 07-joint-scheduling-and-charging
plan: 03
subsystem: studies
tags: [m0, m1, route-100, translink]
provides:
  - docs/results/transit/: M0 and M1 bundles for Route 100 to 08:00, to 10:00 and the full day
  - run_bench.py: M1 against M0 in buses, deadhead and cost, M0's duties replayed with the battery
affects: [phase 11]
tech-stack:
  added: []
  patterns: [every table value recomputed by the independent replay]
key-files:
  created: [docs/results/transit/]
  modified: [run_case.py, run_bench.py, checks/schedule.py]
key-decisions:
  - "M0's duties are replayed with the battery and no charging, so M0 and M1 are compared by the same code"
duration: 60min
completed: 2026-09-29
status: complete
---

# Phase 7 Plan 03: Route 100 study

**To 08:00 M1 is certified at 7,046.57 with M0's 16 buses; over the full day all 16 M0 duties fall below the reserve, and M1 at its 1,800 s limit uses 21 buses at 11,157.24 against the bound 7,070.54 (gap 36.6%).**

## Findings
- To 08:00 (54 trips) and to 10:00 (77 trips) no bus needs to charge; M0's duties cost exactly M1's incumbent.
- The full-day bound stays near the 16-bus cost: the relaxation of the energy rows is weak, so the gap measures the bound as much as the schedule. The incumbent keeps an unused site open, so it is not optimal.

## Task Commits
1. **Study and comparison** - `e0468c3`, `dd45542`
