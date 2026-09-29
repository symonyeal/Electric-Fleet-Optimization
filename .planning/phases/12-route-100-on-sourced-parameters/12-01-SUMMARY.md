---
phase: 12-route-100-on-sourced-parameters
plan: 01
subsystem: data, models, checks
tags: [tariff, bc-hydro, translink, sourced-parameters]
provides:
  - data/scenarios/route100-rs1640.toml, route100-rs1650.toml, and their -range variants
  - models/fleet.py tariff(): billing-demand window, rider, basic charge (also models/taper.py)
  - checks/schedule.py and checks/enum_transit.py price the tariff independently
  - run_case.py --scenario; run_bench.py sourced section, CASES and figures
affects: [phase 11]
tech-stack:
  added: []
  patterns: [absent tariff keys give the rows of before; a derived value names its derivation]
key-files:
  created: [data/scenarios/route100-rs1640.toml, data/scenarios/route100-rs1650.toml,
            data/scenarios/route100-rs1640-range.toml, data/scenarios/route100-rs1650-range.toml]
  modified: [models/fleet.py, models/taper.py, checks/schedule.py, checks/enum_transit.py,
             run_case.py, run_bench.py, tests/test_fleet.py, tests/test_bench.py,
             docs/SOURCES.md, docs/DATA.md, docs/MODELS.md]
key-decisions:
  - "Both BC Hydro rates are modeled: TransLink's rate is not public"
  - "The depot is on RS 1640 in both files and charges 22:00-06:00, so it bears no demand charge"
  - "Two packs: Nova's 594 kWh and 285.8 kWh, the smallest for which TransLink's 'over 150 km' holds, because a probe ran the day at 594 kWh without on-route charging"
duration: session
completed: null
status: partial
---

# Phase 12 Plan 01: Route 100 on sourced parameters

**The tariff and the sourced values are in, tested against two independent computations; the four full-day runs have not run.**

## Done
- Source register: BC Hydro Electric Tariff RS 1640/1650/1901/1904 read directly; TransLink's 19 buses and 10 on-route chargers; Nova's 594 kWh; CARB 2018's measured consumption and charging efficiency (docs/SOURCES.md, docs/DATA.md §3).
- Tariff terms in M1 and M3, priced separately by the replay and the enumeration. On 6 tiny timetables all three agree under the RS 1640 terms with windows from 06:00 and 07:30; the 07:30 window lowers the optimum (seed 1: demand charge 60.22 to 13.38). Without tariff keys the rows are identical (tested). Fast suite 270 passed at 5aec777.

## Open
- TRN-12: the four full-day runs, stopped at the user's request 4.5 minutes in, no bundle written:
  `python run_case.py transit route100 M1 --scenario rs1640-range --time 1800`, the same for
  `rs1650-range`, and `rs1640`, `rs1650` with `--time 600`; then `python run_bench.py`.
- Open sources: charger power, the depot, the 594 vs 564 kWh and 150 km conflict, the sign of RS 1901.

## Task Commits
1. **Tariff model, scenarios, sources** - `5aec777`
