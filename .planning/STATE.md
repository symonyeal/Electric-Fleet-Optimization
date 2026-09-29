---
gsd_state_version: "1.0"
current_phase: 3
current_phase_name: Exact EVRP MILP
status: executing
stopped_at: Phase 12 tariff model committed (5aec777); its four full-day runs stopped at the user's request, not yet run
last_updated: "2026-09-29T16:00:00.000Z"
last_activity: 2026-09-29
last_activity_desc: BC Hydro tariff and sourced vehicle values modeled and tested; runs open
state_head: dd45542e9e51f7bb95c6cd34fe3d19731df110aa
progress:
  total_phases: 12
  completed_phases: 8
  total_plans: 27
  completed_plans: 25
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-29)

**Core value:** Every reported number is certified: a replayed feasible solution and a valid lower bound, with the gap stated, or an explicit status saying why not.
**Current focus:** Phase 12, Route 100 on sourced parameters: run its four full-day cases (about 30 minutes, three at a time)

## Current Position

Phase: 12 of 12 (Route 100 on sourced parameters), with 3, 5 and 11 also open
Status: Code complete for all 11 phases; Phases 1, 2, 4, 6, 7, 8, 9, 10 verified. Open: 15 routing cases (EVRP-06, RPT-01); Phase 5 criterion 2 fails on E-n30-k3 (the textbook IPM master stops at its iteration limit)
Last activity: 2026-09-29 — tariff terms and sourced scenarios at 5aec777; DATA-04 and TRN-11 complete, TRN-12 open

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

- Phase 12: `python run_case.py transit route100 M1 --scenario rs1640-range --time 1800`, likewise rs1650-range, then rs1640 and rs1650 at 600 s; then `python run_bench.py`
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
Stopped at: Phase 12 A4 (runs) of `Claude Func Folder/plans/20260929-efm-route100-real-data.md` (outside the repo); A1-A3 committed at 5aec777
Resume file: that plan file
