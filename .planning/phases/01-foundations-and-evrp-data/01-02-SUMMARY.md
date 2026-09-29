---
phase: 01-foundations-and-evrp-data
plan: 02
subsystem: data
tags: [evrp, provenance, sha256]
provides:
  - data/evrp.py: read(), load(), fetch(), KEYS
  - data/evrp.sha256: manifest of 41 files at commit 16d3499
affects: [routing models, replay]
tech-stack:
  added: []
  patterns: [instance as dict; node k = file id k+1]
key-files:
  created: [data/evrp.py, data/evrp.sha256, tests/test_evrp_data.py, tests/fixtures/tiny.evrp]
  modified: [docs/SOURCES.md, pyproject.toml]
key-decisions:
  - "OPTIMAL_VALUE parsed as its leading number; 0 and '-' mean unknown"
  - "Benchmark files fetched, not committed; tests needing them are marked `data`"
duration: 15min
completed: 2026-09-28
status: complete
---

# Phase 1 Plan 02: Pinned benchmark and keyword reader

**All 41 files verify against the committed SHA-256 manifest and parse under both header variants.**

## Accomplishments
- OPTIMAL_VALUE appears as `384.678035`, `0`, `-`, `857 (best known)`, `740 (upper bound)`, `344849 (Best Known)`.
- Two 2022 files have a NAME unlike their file name: F-n140-k5-s5 (NAME F-n140-k7-s5), X-n221-k11-s7 (NAME X-n221-k11-s9). Pinned by test.
- DATA-03: Vanderbei's and Beck's chapter numbers agree with the cited ones; Beck does not treat the perspective function.

## Task Commits
1. **Reader, manifest, textbook check** - `9129972`
