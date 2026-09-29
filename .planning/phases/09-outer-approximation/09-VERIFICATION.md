---
phase: 09-outer-approximation
verified: 2026-09-29T16:00:00Z
status: passed
score: 4/4 must-haves verified
covered_files:
  - ".planning/REQUIREMENTS.md"
  - ".planning/phases/09-outer-approximation/09-01-SUMMARY.md"
  - ".planning/phases/09-outer-approximation/09-02-SUMMARY.md"
  - ".planning/phases/09-outer-approximation/09-03-SUMMARY.md"
  - "methods/oa.py"
  - "models/charge.py"
  - "models/recharge.py"
  - "run_bench.py"
  - "docs/results/grid/grid.json"
  - "tests/test_oa.py"
  - "tests/test_recharge.py"
behavior_unverified: 0
---

# Phase 09: Verification Report

**Phase Goal:** A user can certify the convex MINLPs M2 and R3 and read how much charging physics costs over the integer-only models
**Verified:** 2026-09-29
**Status:** passed

Verified by the orchestrator from executed tests and the grid bundle (not an independent verifier). No `covered_digest`: the GSD digest scheme could not be reproduced outside its tooling, so none is claimed.

## Observable Truths

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Lower bounds are nondecreasing and every upper bound is a replayed solution; the run ends certified, at a limit, or `stall` | ✓ VERIFIED | test_oa.py (known convex MINLP; bounds nondecreasing); grid rows end `optimal` or `stall`, each U from `replay_charge` or the M1 replay |
| 2 | M2-P and R3-P bracket the OA values | ✓ VERIFIED | test_oa.py (M2 inside M2-P), test_recharge.py (scenario R3 inside R3-P) |
| 3 | M2-versus-M1 and R3-versus-R1 comparisons are reported over a declared parameter grid | ✓ VERIFIED | docs/results/README.md "Charging physics (OA-04)", 11 rows, revisions 474149b and 9c00dc3: M2 = M1 at 250 kWh (nothing charges before 06:30); +0.053/+0.107/+0.208 CAD at 100 kWh; R3 routes +3.17 over R1 on six customers at alpha 0-5e-4 |
| 4 | The report states whether any R1 optimum uses a segment with two or more stations | ✓ VERIFIED | Multi-station column of the E-instance table: 0 on E-n23-k3's certified optimum and on the best known routes of E-n22-k4 and E-n30-k3 |

## Measured limits recorded, not defects hidden

- R3 on the eight far customers of E-n22-k4 stalls at alpha = 0 (1,203 s, gap 18.5%): the OA master MILP does not close within 600 s.
- R3 on six customers at alpha = 1e-3 stalls with no incumbent (L = 293.81): the cost-optimal power equals P there, strict complementarity fails, and the textbook barrier reaches its iteration limit; at alpha = 0.99e-3 and 1.01e-3 the same subproblem converges in 0.4 s (docs/VALIDATION.md §4).

## Requirements Coverage

| Requirement | Status |
|---|---|
| OA-01 | ✓ SATISFIED |
| OA-02 | ✓ SATISFIED |
| OA-03 | ✓ SATISFIED |
| OA-04 | ✓ SATISFIED |
