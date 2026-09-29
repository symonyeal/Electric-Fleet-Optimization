---
phase: 11-studies-and-publication
plan: 01
subsystem: studies
tags: [experiment-matrix, bundles, provenance]
provides:
  - run_bench.py --run [--missing] [--jobs N]; grid() written row by row, resumable
  - checks/certificate.py host(): processor and toolchain in every bundle's provenance
affects: [phase 3, phase 5, phase 9]
tech-stack:
  added: [matplotlib in requirements.txt]
  patterns: [a bundle names revision and host; prose does not dirty a revision]
key-files:
  created: []
  modified: [run_bench.py, run_case.py, checks/certificate.py, requirements.txt]
key-decisions:
  - "--missing skips a case whose bundle exists: re-running finished cases on a slower machine could overwrite better results"
  - "Prose (*.md) does not mark a revision dirty: run_bench.py rewrites README.md while later cases start"
duration: session
completed: 2026-09-29
status: partial
---

# Phase 11 Plan 01: Matrix runner and bundles

**The runner resumes, runs cases concurrently, and every bundle names its revision and host; 19 of 34 matrix cases and all 11 grid rows are bundled.**

## Status
- Bundled: every transit case; E-n22-k4 and E-n23-k3 (all four models); E-n30-k3 (all four); E-n33-k4 R0; the OA-04 grid.
- Open: 15 routing cases (E-n33-k4 R1, R2; E-n51-k5 to E-n101-k8). The user cannot run multi-hour jobs locally; the proposed route is a probe of exact pricing on E-n51-k5, then CI for what is worth running.

## Task Commits
1. **Runner, host, requirements** - `9c00dc3`
2. **Grid rows where charging binds** - `474149b`
