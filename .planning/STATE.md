---
gsd_state_version: "1.0"
current_phase: 3
current_phase_name: Exact EVRP MILP
status: executing
stopped_at: Session closed; long benchmark runs pending (Phases 3, 5, 9, 11)
last_updated: "2026-09-29T15:51:59.746Z"
last_activity: 2026-09-29
last_activity_desc: Results recorded; benchmark loops stopped at session close
state_head: dd45542e9e51f7bb95c6cd34fe3d19731df110aa
progress:
  total_phases: 11
  completed_phases: 7
  total_plans: 26
  completed_plans: 25
  percent: 64
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-09-28)

**Core value:** Every reported number is certified: a replayed feasible solution and a valid lower bound, with the gap stated, or an explicit status saying why not.
**Current focus:** Finish the experiment matrix: `python run_bench.py --run`, then `--grid`

## Current Position

Phase: 3 of 11 (Exact EVRP MILP)
Plan: 03-03 partial (EVRP-06 open for E-n30-k3 to E-n101-k8)
Status: Code complete for all 11 phases; Phases 1, 2, 4, 6, 7, 8, 10 verified. Pending runs: R0/R1/R2 on five E instances (Phases 3, 5), the OA-04 grid (Phase 9), RPT-01 (Phase 11)
Last activity: 2026-09-29 — results recorded, loops stopped at session close

Progress: [██████░░░░] 64%

## Performance Metrics

**Velocity:**

- Total plans completed: 17
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 3 | - | - |
| 2 | 3 | - | - |
| 4 | 2 | - | - |
| 6 | 2 | - | - |
| 8 | 2 | - | - |
| 10 | 2 | - | - |
| 7 | 3 | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Init]: Routing (CEC-2020 EVRP via evrp-python) precedes transit, so the machinery meets external values before real data
- [Init]: R1 uses the station-path multigraph; the report's formulation (R1-TR) is kept for checks only, with the depot split
- [Init]: Benchmark files are fetched from commit 16d3499 and checksummed, not committed, until terms are confirmed

### Pending Todos

None yet.

### Blockers/Concerns

- Whether SciPy's `highs-ipm` exposes duals before crossover is unknown; it decides whether CG-01's interior variant needs the project's own IPM only (Phase 1 check, FND-02)
- evrp-python's pinned requirements cannot install on Python 3.14; its GSGA may not run against current numpy (EVRP-05 has a labeled fallback)
- The TransLink feed URL and checksum were not recorded by the first design session (Phase 6)
- The superseded folder `Transit-Fleet-Model` and a stray empty `.git` in the parent folder need manual removal

## Deferred Items

Items acknowledged and deferred at milestone close, most recent first:

| Category | Item | Status | Deferred At | Milestone |
|----------|------|--------|-------------|-----------|
| *(none)* | | | | |

## Session Continuity

Last session: 2026-09-28 23:40
Stopped at: Phase 7 complete, ready to plan Phase 3
Resume file: None
