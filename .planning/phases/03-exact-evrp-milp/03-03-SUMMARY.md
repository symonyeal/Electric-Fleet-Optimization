---
phase: 03-exact-evrp-milp
plan: 03
subsystem: studies
tags: [baseline, gsga, verdicts]
provides:
  - run_baseline.py: evrp-python's GSGA from an outside checkout, tours replayed
  - run_bench.py verdicts(): per-instance L, U, gap and verdict against the report and evrp-python
affects: [phase 5, phase 11]
tech-stack:
  added: []
  patterns: [inert stub modules for loguru, matplotlib and pandas]
key-files:
  created: [run_baseline.py, docs/results/baseline/, docs/results/evrp/]
  modified: [run_bench.py]
key-decisions:
  - "The verdict table lives in docs/results/README.md, generated from bundles, rather than a hand-written verdicts.md"
duration: 90min
completed: 2026-09-29
status: partial
---

# Phase 3 Plan 03: Baseline and verdicts

**E-n23-k3 is certified optimal at 571.947383 (R1, 211 s), below the report's 573.130948; E-n22-k4 is bracketed at 1.09%; the other five instances are open.**

## Status
- GSGA replayed on E-n22-k4 (3 seeds; best 384.678093) and E-n23-k3 (2 seeds; 571.947383); the remaining instances were stopped by the user.
- R0 and R1 ran on E-n22-k4 and E-n23-k3, R0 on E-n30-k3 (600 s, gap 26.8%); the loops were stopped when the session closed.
- EVRP-06 stays open until E-n30-k3 to E-n101-k8 have runs: `python run_bench.py --run`.

## Task Commits
1. **Baseline runner** - `2196226`
2. **Verdicts and bundles** - `64f6888`, `dd45542`
