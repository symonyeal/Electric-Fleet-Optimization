---
phase: 10-nonconvex-and-scenario-extensions
plan: 01
subsystem: models
tags: [nonconvex, taper, local]
provides:
  - models/taper.py law(), integrate(), m3_fixed()
affects: []
tech-stack:
  added: []
  patterns: [energies by forward simulation of (14); status local]
key-files:
  created: [models/taper.py, tests/test_extensions.py]
  modified: []
key-decisions:
  - "The fixed-integer M1 LP is the optimistic bound"
duration: 30min
completed: 2026-09-29
status: complete
---

# Phase 10 Plan 01: M3

**On three tiny schedules every local M3 solution lies above the M1 optimistic bound; (14) matches integration to 1e-8.**

## Task Commits
1. **M3** - `c98f16f`
