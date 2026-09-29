---
phase: 01-foundations-and-evrp-data
plan: 01
subsystem: foundations
tags: [packaging, ci, result-contract]
provides:
  - pyproject/requirements/CI on Python 3.14
  - checks/certificate.py: STATUS taxonomy, record(), certified()
affects: [every model and method]
tech-stack:
  added: []
  patterns: [results as JSON-serializable dicts]
key-files:
  created: [pyproject.toml, requirements.txt, .github/workflows/ci.yml, checks/certificate.py, tests/test_certificate.py]
  modified: []
key-decisions:
  - "STATUS is Algorithms §8's set plus `limit` for a continuous solve at its budget"
  - "ruff ignores C408: dict(k=v) is the record form"
duration: 10min
completed: 2026-09-28
status: complete
---

# Phase 1 Plan 01: Packaging and result contract

**`record()` states U, L and a gap only when both bounds are finite, and flags a negative gap as a defect.**

## Accomplishments
- Packaging mirrors Electricity-Market-Model; CI runs pytest (not data, not slow), ruff, pip check on 3.14.
- Five tests pin the status set, the missing-bound rule, the certification rule and the negative-gap flag.

## Task Commits
1. **Packaging, CI, result contract** - `20ce8e8`
