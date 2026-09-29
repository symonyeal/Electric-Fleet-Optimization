---
phase: 08-convex-charging-subproblems
plan: 01
subsystem: models
tags: [qp, barrier, convex-programming]
provides:
  - methods/ipm.py ipm(h, Jh, Hh): convex constraints (Vanderbei Ch. 25)
  - models/charge.py m1q_fixed(), m2_fixed(), m2_trust(), grad_check()
affects: [phase 9]
tech-stack:
  added: []
  patterns: [two independent barrier solves per subproblem]
key-files:
  created: [models/charge.py, tests/test_charge.py]
  modified: [methods/ipm.py, tests/test_ipm.py]
key-decisions:
  - "The project's own barrier method solves the fixed-integer M2; trust-constr is the cross-check"
duration: 60min
completed: 2026-09-29
status: complete
---

# Phase 8 Plan 01: M1-Q and M2 at fixed integers

**Textbook QP method and trust-constr agree on M1-Q; textbook barrier and trust-constr agree to 1e-6 on M2, with a tight (A5) bound.**

## Accomplishments
- The finite-difference test caught a Jacobian written into CSR data in coordinate order; that bug, not SciPy, had made trust-constr fail.
- The IPM solves min -x1 - x2 on the unit disc to (1, 1)/sqrt(2) with multiplier 2^-1/2.

## Task Commits
1. **Subproblems** - `ccfb42a`
