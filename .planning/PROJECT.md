# Electric Fleet Model

## What This Is

A research code base, runnable on a Windows laptop with the system Python 3.14,
numpy, and scipy, that solves electric-fleet routing and scheduling problems as
MILPs and MINLPs and attaches to every result a feasible upper bound, a valid
lower bound, and an independent replay. It has two applications: the CEC-2020
EVRP benchmark (as distributed by evrp-python), whose published values are
unverified, and electric-bus scheduling on TransLink's public GTFS timetable. It
is for the author, a mathematician learning optimization by building, and for
readers who want certified numbers rather than heuristic ones.

## Core Value

Every reported number is certified: a replayed feasible solution and a valid
lower bound, with the gap stated, or an explicit status saying why not.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Routing: certify, refute, or bound the published values of the seven 2019 E instances (R0, R1, R2)
- [ ] Interior-point methods used where they carry a testable claim: textbook LP/QP method, inexact branch-and-bound nodes, early-terminated column-generation duals, barrier subproblems in outer approximation
- [ ] Transit: battery-free fleet (M0), joint scheduling and charging (M1), convex charging losses (M1-Q, M2, M2-P) on a TransLink corridor
- [ ] Partial recharging with resistive loss as a convex MINLP (R3, R3-P)
- [ ] Nonconvex taper (M3) and energy scenarios (M4) as specified extensions
- [ ] Reproducible studies: committed commands regenerate every README number

### Out of Scope

- Driver rostering and labor rules — separate data and modeling obligations; schedules are never presented as duties
- Distribution-network power flow, vehicle-to-grid, solar — each needs its own physical model and data
- Time windows, multi-depot, heterogeneous fleets in v1 — the benchmark and the first corridor need none
- Commercial solvers, modeling layers, online optimization services — no measurement shows a need
- A second Python environment or interpreter — the user's single-environment rule; baselines with incompatible pins run from outside checkouts
- A web application — results are static files usable without a server
- Branch-and-price — R2 delivers bounds; full branch-and-price is v2 at the earliest

## Context

- Design documents, written before this plan: `docs/DESIGN.md`, `docs/ROUTING.md`,
  `docs/MODELS.md`, `docs/ALGORITHMS.md`, `docs/DATA.md`, `docs/VALIDATION.md`,
  `docs/SOURCES.md`. They are the research input for every phase; the formulation
  numbers (R1.3, A3, (10), ...) used in requirements refer to them.
- Mathematical basis: Vanderbei, *Linear Programming*, 4th ed. (2014), and Beck,
  *Introduction to Nonlinear Optimization* (2014), from the user's local PDFs.
- Style reference: the user's Electricity-Market-Model (exact models, independent
  formulations, published cases, certificates, provenance).
- evrp-python (commit 16d3499) supplies instance files and a heuristic baseline.
  Its validator, fleet rule, and README table have documented defects
  (`docs/ROUTING.md` §9).
- The competition report's MILP is infeasible as written at the depot; R1-TR
  splits the depot (`docs/ROUTING.md` §2).
- The first design session ran in a Codex sandbox whose folder
  (`Transit-Fleet-Model`) is owned by another account; this project supersedes it.

## Constraints

- **Tech stack**: system Python 3.14, numpy, scipy (HiGHS via `milp`/`linprog`), stdlib; matplotlib at the reporting phase — user's single-environment rule
- **Hardware**: AMD Ryzen 7 PRO 6850U, 24 GB RAM, no NVIDIA GPU — CUDA solvers unavailable; instance sizes chosen to fit. The 29 September 2026 benchmark runs used a second machine, an Intel Core i5-1335U with 16 GB; bundles name their host
- **Rust/PyO3**: only for a kernel profiling identifies; R2 pricing is the first candidate
- **Data**: third-party files fetched by pinned URL with SHA-256, committed only when terms permit
- **Code style**: math-style skill; symbol names from the documents; algorithm boxes; no defensive clutter
- **Evidence**: no claim without an executed check recorded in `docs/VALIDATION.md`

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Two tracks: EVRP benchmark and TransLink transit | Benchmark has external values but no operations; GTFS has operations but no optimum; methods validated on the first are applied to the second | — Pending |
| Routing phases before transit phases | External values validate the MILP, B&B, and bound machinery before it meets real data | — Pending |
| R1 on a station-path multigraph, R1-TR only for checks | Report formulation needs 2n copies per station (336 nodes for E-n22-k4) and is infeasible as written at the depot | — Pending |
| Free fleet; no separate vehicle-cap model | The report defines VEHICLES as a minimum; evrp-python caps vehicles that may make several trips, which restricts nothing without time | — Pending |
| Own primal-dual IPM for column generation duals | Early-terminated interior duals are the tested claim; SciPy may not expose pre-crossover duals (Phase 1 check) | — Pending |
| Rename from Transit-Fleet-Model to Electric-Fleet-Model | The project now covers routing as well as transit | ✓ Good |
| Fetch benchmark files instead of committing them | The set states no license; citation requested | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-28 after initialization*
