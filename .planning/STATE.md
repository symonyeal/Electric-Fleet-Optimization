---
gsd_state_version: "1.0"
current_phase: 3
current_phase_name: Exact EVRP MILP
status: executing
stopped_at: Matrix stopped by the user after 19 of 34 cases; OA-04 grid complete; real-data plan A awaiting approval
last_updated: "2026-09-29T16:00:00.000Z"
last_activity: 2026-09-29
last_activity_desc: OA-04 grid rerun where charging binds; stall root-caused; Phase 9 closed
state_head: dd45542e9e51f7bb95c6cd34fe3d19731df110aa
progress:
  total_phases: 11
  completed_phases: 8
  total_plans: 26
  completed_plans: 25
  percent: 73
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-29)

**Core value:** Every reported number is certified: a replayed feasible solution and a valid lower bound, with the gap stated, or an explicit status saying why not.
**Current focus:** Route 100 on sourced parameters (approach A), plan awaiting approval; the open benchmark runs move off the laptop

## Current Position

Phase: 3 of 11 (Exact EVRP MILP), with 5 and 11 also open
Status: Code complete for all 11 phases; Phases 1, 2, 4, 6, 7, 8, 9, 10 verified. Open: 15 routing cases (EVRP-06, RPT-01); Phase 5 criterion 2 fails on E-n30-k3 (the textbook IPM master stops at its iteration limit)
Last activity: 2026-09-29 — grid redesigned and completed at 474149b; matrix stopped by the user at 19 of 34 cases

Progress: [███████░░░] 73%

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Init]: Routing (CEC-2020 EVRP via evrp-python) precedes transit, so the machinery meets external values before real data
- [Init]: R1 uses the station-path multigraph; the report's formulation (R1-TR) is kept for checks only, with the depot split
- [Init]: Benchmark files are fetched from commit 16d3499 and checksummed, not committed, until terms are confirmed
- [2026-09-29]: `run_bench.py --missing` never overwrites a finished bundle; every bundle names its host, since runs now come from two machines
- [2026-09-29]: The OA-04 grid adds a declared 100 kWh battery, because with 250 kWh nothing charges before 06:30; R3/R1 uses six customers, where OA certifies
- [2026-09-29]: The user cannot run multi-hour jobs locally; the next direction is real data (approach A: Route 100 on sourced parameters), not exact-method depth

### Pending Todos

- Probe whether one exact pricing call completes on E-n51-k5 before spending runs on E-n51-k5 to E-n101-k8
- Why the textbook IPM master hits its iteration limit on E-n30-k3 (122 of 156 outer iterations)
- A barrier fallback for degenerate fixed-route R3 points (alpha = 1e-3 grid row)

### Blockers/Concerns

- Long benchmark runs cannot occupy the user's machine: the 15 open cases need a probe first, then CI or another machine
- nrel.gov does not resolve on the office network; NREL fleet evaluations must come from another network or a mirror
- evrp-python's pinned requirements cannot install on Python 3.14; its GSGA runs from an outside checkout with stub modules

## Deferred Items

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| Runs | E-n33-k4 R1, R2; E-n51-k5 to E-n101-k8 (15 cases) | Open | 2026-09-29 | v1 |

## Session Continuity

Last session: 2026-09-29 16:00
Stopped at: Plan file `Claude Func Folder/plans/20260929-efm-route100-real-data.md` (outside the repo) written; A1 source register in progress
Resume file: that plan file
