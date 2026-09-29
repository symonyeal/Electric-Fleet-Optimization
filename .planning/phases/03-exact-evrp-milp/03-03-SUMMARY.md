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

**E-n23-k3 is certified optimal at 571.947383 (R1, 211 s), below the report's 573.130948; E-n22-k4 is bracketed at 1.09% and E-n30-k3 at 8.09%; the other four instances are open.**

## Status
- GSGA replayed on E-n22-k4 (3 seeds; best 384.678093) and E-n23-k3 (2 seeds; 571.947383); the remaining instances were stopped by the user.
- R0 and R1 ran on E-n22-k4 and E-n23-k3, R0 on E-n30-k3 (600 s, gap 26.8%).
- 2026-09-29, second machine (i5-1335U), `run_bench.py --run --missing --jobs 2` at 9c00dc3: E-n23-k3 R2 (both duals), E-n30-k3 R1 and R2 (both), E-n33-k4 R0. E-n30-k3 is now bracketed at [484.5677, 527.2049], gap 8.09%, with the report's 511.2539 inside. The user stopped the matrix after these: long runs cannot occupy the machine.
- EVRP-06 stays open for 15 cases (E-n33-k4 R1, R2; E-n51-k5 to E-n101-k8): `python run_bench.py --run --missing`, probing first whether exact pricing completes on E-n51-k5.

## Task Commits
1. **Baseline runner** - `2196226`
2. **Verdicts and bundles** - `64f6888`, `dd45542`
