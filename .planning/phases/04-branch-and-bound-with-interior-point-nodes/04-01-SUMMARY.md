---
phase: 04-branch-and-bound-with-interior-point-nodes
plan: 01
subsystem: methods
tags: [branch-and-bound, interior-point]
provides:
  - methods/branch.py: bnb(), node(), split()
affects: [phase 7 (tiny M1)]
tech-stack:
  added: []
  patterns: [node bound = max(parent bound, (A3)); pruning reasons recorded]
key-files:
  created: [methods/branch.py, tests/test_branch.py]
  modified: [methods/ipm.py, tests/test_ipm.py]
key-decisions:
  - "Best-first, most-fractional branching, lexicographic ties"
  - "A node the textbook IPM cannot resolve is classified by highs-ds; otherwise it stays open"
duration: 40min
completed: 2026-09-29
status: complete
---

# Phase 4 Plan 01: Tree

**Random 0-1 programs: the tree reaches HiGHS milp's optimum with textbook-IPM and highs-ipm node LPs; the global bound is nondecreasing.**

## Accomplishments
- Found and fixed a Phase 2 defect: standard() compacted the caller's sparse A_ub in place (eliminate_zeros on arrays shared through csr_array), corrupting it for the next node. Symptom: "axis 0 index 1642295925504 exceeds matrix dimension 33". Regression test fails on the old code.

## Task Commits
1. **Tree and fix** - `fdf1e81`
