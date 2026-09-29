---
phase: 09-outer-approximation
plan: 02
subsystem: models
tags: [m2, bracket]
provides:
  - models/charge.py m2(), m2p(), loss_cons()
  - checks/schedule.py replay_energy(loss=True): losses and taper in the replay
affects: [phase 11]
tech-stack:
  added: []
  patterns: [M2-P lower = tangents, upper = maximum of secants]
key-files:
  created: []
  modified: [models/charge.py, checks/schedule.py]
key-decisions:
  - "M2 MINLP runs with gamma = 0 (loss alone); stress studied at fixed integers"
duration: 30min
completed: 2026-09-29
status: complete
---

# Phase 9 Plan 02: M2

**On three tiny instances M2 is certified, lies within its M2-P bracket, and costs at least M1.**

## Task Commits
1. **M2 and M2-P** - `ccfb42a`
