---
phase: 04-branch-and-bound-with-interior-point-nodes
plan: 02
subsystem: methods
tags: [branch-and-bound, R1, validation]
provides:
  - validated incumbents via routes_of + checks.route.replay; early-stopped node LPs
affects: [phase 7]
tech-stack:
  added: []
  patterns: [inexact nodes carry their box so each bound is checkable]
key-files:
  created: []
  modified: [methods/branch.py, tests/test_branch.py, models/route.py]
key-decisions:
  - "A node bound need not lie below the global optimum; it is checked against its own node's exact LP"
  - "Status no_incumbent, not infeasible, when a validator rejected candidates"
duration: 20min
completed: 2026-09-29
status: complete
---

# Phase 4 Plan 02: R1 through the tree

**On the fixture and self-made R1 instances the tree reaches r1()'s optimum with exact, early-stopped (delta = 1e-2) and highs-ipm node LPs; every early-stopped node's bound is at most that node's exact LP value.**

## Accomplishments
- models/route.rows() exposes R1's rows once; r1() and bnb() both read them.
- The 4-customer instance rand4 takes 130 s through the tree and is marked slow.

## Task Commits
1. **R1 through the tree** - `fdf1e81`
