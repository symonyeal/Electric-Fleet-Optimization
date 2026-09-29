# Roadmap: Electric Fleet Model

## Overview

The build runs from certificates to applications. Phase 1 lays the result
contract, the EVRP data, and the independent route replay, so that nothing later
is judged by its own code. Phase 2 builds the textbook interior-point method.
Phases 3-5 take the routing benchmark, where published values exist, from an
exact MILP through an interior-point branch-and-bound to a column-generation
bound, and end with a per-instance verdict on those values. Phases 6-7 carry the
validated machinery to the TransLink timetable. Phases 8-9 add the convex
charging physics shared by both tracks and certify it by outer approximation.
Phase 10 adds the nonconvex and scenario extensions; Phase 11 regenerates every
published number from committed commands.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundations and EVRP data** - Result contract, pinned benchmark files, keyword reader, independent route replay, toolchain facts (completed 2026-09-28)
- [x] **Phase 2: Interior-point core** - Textbook primal-dual LP/QP method with bound (A3) and early-terminated duals (completed 2026-09-29)
- [ ] **Phase 3: Exact EVRP MILP** - Station-path multigraph, R0/R1/R1-TR, first verdicts on the published values
- [x] **Phase 4: Branch-and-bound with interior-point nodes** - Educational tree with certified pruning on tiny R1 instances (completed 2026-09-29)
- [ ] **Phase 5: Column-generation bound** - R2 with interior versus simplex duals; bounds for the 2019 E set
- [x] **Phase 6: Transit data and battery-free fleet** - Pinned GTFS snapshot, trip DAG, M0 by matching and flow (completed 2026-09-29)
- [x] **Phase 7: Joint scheduling and charging** - Time-space graph, M1, schedule replay, scenario files (completed 2026-09-29)
- [x] **Phase 8: Convex charging subproblems** - Fixed-integer M1-Q, M2, R3 by interior-point and barrier methods with (A5) (completed 2026-09-29)
- [ ] **Phase 9: Outer approximation** - OA for M2 and R3 with M2-P and R3-P brackets
- [x] **Phase 10: Nonconvex and scenario extensions** - M3 local solutions, M4 scenario fleet (completed 2026-09-29)
- [ ] **Phase 11: Studies and publication** - Experiment matrix, figures, regenerated README, executed validation record

## Phase Details

### Phase 1: Foundations and EVRP data

**Goal**: A user can fetch the benchmark, read any instance, and replay any route file with a verdict that shares no code with any solver
**Depends on**: Nothing (first phase)
**Requirements**: FND-01, FND-02, FND-03, FND-04, DATA-01, DATA-02, DATA-03, CHK-01, CHK-02
**Design refs**: docs/DATA.md §1; docs/ROUTING.md §1, §9; docs/ALGORITHMS.md §8; docs/VALIDATION.md §2
**Success Criteria** (what must be TRUE):

  1. `pytest`, `ruff check`, and `pip check` pass on the system Python 3.14, locally and in GitHub Actions
  2. All 41 instance files fetch from commit 16d3499, parse, and match their recorded SHA-256
  3. The route validator names each defect in the hand-built fixtures (missing customer, repeat, overload, empty battery on a depot leg) and accepts the valid ones at their hand-computed lengths
  4. The toolchain note states the SciPy/HiGHS versions and whether `highs-ipm` exposes duals before crossover

**Plans**: 3 plans

Plans:

- [x] 01-01: Repository skeleton, requirements, ruff, pytest, CI, result record and status taxonomy
- [x] 01-02: Pinned fetch with manifest, keyword reader for both header variants, textbook contents check
- [x] 01-03: Independent route validator, exchange format, evrp-python tour adapter, toolchain note

### Phase 2: Interior-point core

**Goal**: A user can solve LPs and convex QPs with a readable primal-dual method whose every iterate carries a valid bound
**Depends on**: Phase 1
**Requirements**: IPM-01, IPM-02, IPM-03, IPM-04, IPM-05, IPM-06
**Design refs**: docs/ALGORITHMS.md §2-§3; Vanderbei Ch. 17-20, 24
**Success Criteria** (what must be TRUE):

  1. Optimal values agree with `highs-ds` on Vanderbei's worked examples and on random feasible bounded LPs
  2. The bound (A3) never exceeds the `highs-ds` optimum at any iterate
  3. Infeasible and unbounded constructions end with status `numerical` or `limit`, never `optimal`
  4. Stopped at relative gap delta, the method returns interior duals and the gap it reached

**Plans**: 3 plans

Plans:

- [x] 02-01: Standard-form LP method (A1)-(A2), presolve of fixed variables, residual reporting
- [x] 02-02: Bound (A3), status classification, early termination, factorization statistics
- [x] 02-03: Convex QP extension and tests on Vanderbei Ch. 24 examples

### Phase 3: Exact EVRP MILP

**Goal**: A user can solve the small benchmark instances exactly and learn, per instance, whether the published values are certified, refuted, or open
**Depends on**: Phase 1
**Requirements**: EVRP-01, EVRP-02, EVRP-03, EVRP-04, EVRP-05, EVRP-06
**Design refs**: docs/ROUTING.md §2-§4, §8-§9
**Success Criteria** (what must be TRUE):

  1. R1, R1-TR, and enumeration agree on every sub-instance of at most six customers
  2. Every R1 solution returned passes the independent replay, with z(R0) <= z(R1)
  3. E-n22-k4's published 384.678035 is certified, refuted, or bracketed with a stated gap
  4. Each of the seven 2019 E instances has a status against the report's value and evrp-python's, replayed or labeled unreplayed

**Plans**: 3 plans

Plans:

- [ ] 03-01: Station graph, Floyd-Warshall, Pareto station paths, counts per instance
- [ ] 03-02: R0, R1, R1-TR rows; HiGHS solves; enumeration on sub-instances
- [ ] 03-03: evrp-python baseline run and replay; per-instance verdict table

### Phase 4: Branch-and-bound with interior-point nodes

**Goal**: A user can watch an interior-point LP bound drive an integer search and see why each node was pruned
**Depends on**: Phase 2, Phase 3
**Requirements**: BNB-01, BNB-02, BNB-03
**Design refs**: docs/ALGORITHMS.md §4; Vanderbei Ch. 23
**Success Criteria** (what must be TRUE):

  1. On tiny R1 instances the tree reaches the HiGHS optimum
  2. The global lower bound is nondecreasing, and every pruned node records a certified bound or certified infeasibility
  3. An integral LP point becomes an incumbent only after the continuous re-solve and replay

**Plans**: 2 plans

Plans:

- [x] 04-01: Tree, node LP by textbook IPM or `highs-ipm`, bound (A3), pruning rules
- [x] 04-02: Incumbent validation, trajectories, comparison with HiGHS on tiny R1

### Phase 5: Column-generation bound

**Goal**: A user can bound instances R1 cannot close, and measure whether interior duals shorten column generation
**Depends on**: Phase 2, Phase 3
**Requirements**: CG-01, CG-02, CG-03, CG-04, CG-05
**Design refs**: docs/ROUTING.md §5
**Success Criteria** (what must be TRUE):

  1. The bound (R2.2) with exact pricing is reported at every iteration and never exceeds a replayed feasible length
  2. Interior and simplex duals reach the same master value; outer iterations, pricing calls, and time are reported for both
  3. The per-instance verdict table of Phase 3 is updated with R2's lower bounds and restricted-master upper bounds

**Plans**: 3 plans

Plans:

- [ ] 05-01: Restricted master with both dual sources; initial columns from replayed solutions
- [ ] 05-02: Exact ng-route labeling pricing with load and battery resources; dominance tests
- [ ] 05-03: Bound tracking, restricted-master MILP, dual comparison study on the 2019 E set

### Phase 6: Transit data and battery-free fleet

**Goal**: A user can turn a pinned TransLink snapshot into a corridor instance and read its minimum battery-free fleet
**Depends on**: Phase 1
**Requirements**: TRN-01, TRN-02, TRN-03, TRN-04
**Design refs**: docs/DATA.md §2; docs/MODELS.md §1-§2; Vanderbei Ch. 14-15
**Success Criteria** (what must be TRUE):

  1. The snapshot's URL, date, version, SHA-256, and terms are recorded, and trips after midnight are kept
  2. Matching LP and min-cost flow give the same fleet on the corridor
  3. Duties come from an integral extreme point, never from rounding an interior point
  4. Where `block_id` exists, the M0 fleet is at most the agency's block count for the same trips

**Plans**: 2 plans

Plans:

- [x] 06-01: GTFS adapter, service-day and corridor selection, provenance
- [x] 06-02: Trip compatibility DAG, M0 matching and flow, block comparison

### Phase 7: Joint scheduling and charging

**Goal**: A user can decide which buses and chargers operate a corridor under declared equipment assumptions, with a bound and a replayed schedule
**Depends on**: Phase 4, Phase 6
**Requirements**: TRN-05, TRN-06, TRN-07, TRN-08, TRN-09, TRN-10
**Design refs**: docs/MODELS.md §1, §3; docs/DATA.md §3
**Success Criteria** (what must be TRUE):

  1. Every M1 schedule passes the independent replay: each trip once, time-connected paths, energy and plugs within bounds
  2. Scenario files carry a unit and a source or `illustrative` for every value
  3. The corridor study reports M1 against M0 in buses, deadhead, and cost, with bounds
  4. On tiny M1 instances the educational tree reaches the HiGHS optimum

**Plans**: 3 plans

Plans:

- [x] 07-01: Time-space graph and slot convention; scenario files
- [x] 07-02: M1 rows assembled once; HiGHS and IPM relaxation; tree on tiny M1
- [x] 07-03: Schedule replay and the M1-versus-M0 study

### Phase 8: Convex charging subproblems

**Goal**: A user can solve the fixed-integer charging problems of M1-Q, M2, and R3 by interior-point and barrier methods, each with a valid bound
**Depends on**: Phase 2, Phase 3, Phase 7
**Requirements**: NLP-01, NLP-02, NLP-03, NLP-04
**Design refs**: docs/MODELS.md §4; docs/ROUTING.md §6; docs/ALGORITHMS.md §5; Beck Ch. 7-8, 10-12; Vanderbei Ch. 24-25
**Success Criteria** (what must be TRUE):

  1. Analytic gradients and Hessians agree with finite differences for M1-Q, M2, and R3
  2. The bound (A5) never exceeds the fixed-integer value, and KKT residuals are reported
  3. Fixed-zero faces are eliminated before any barrier solve; no log barrier acts on a variable fixed at zero

**Plans**: 2 plans

Plans:

- [x] 08-01: M1-Q by the textbook QP method; M2 by `trust-constr` with analytic derivatives
- [x] 08-02: R3 fixed-route problem with the closed perspective; bound (A5) and residual checks

### Phase 9: Outer approximation

**Goal**: A user can certify the convex MINLPs M2 and R3 and read how much charging physics costs over the integer-only models
**Depends on**: Phase 8
**Requirements**: OA-01, OA-02, OA-03, OA-04
**Design refs**: docs/ALGORITHMS.md §6; docs/MODELS.md §5; docs/ROUTING.md §6
**Success Criteria** (what must be TRUE):

  1. Lower bounds are nondecreasing and every upper bound is a replayed solution; the run ends certified, at a limit, or `stall`
  2. M2-P and R3-P bracket the OA values: lower MILP bound <= OA value <= reconstructed upper value
  3. M2-versus-M1 and R3-versus-R1 comparisons are reported over a declared parameter grid
  4. The report states whether any R1 optimum uses a segment with two or more stations

**Plans**: 3 plans

Plans:

- [ ] 09-01: OA engine: master, cuts (A6) and (R3.4), restoration, stall handling
- [ ] 09-02: M2 with the M2-P bracket on the corridor
- [ ] 09-03: R3 with the R3-P bracket on small E instances; parameter-grid comparisons

### Phase 10: Nonconvex and scenario extensions

**Goal**: A user can see what the conservative taper envelope omits and which fleet survives every enumerated energy scenario
**Depends on**: Phase 9
**Requirements**: EXT-01, EXT-02
**Design refs**: docs/MODELS.md §6-§7
**Success Criteria** (what must be TRUE):

  1. M3's closed form (14) agrees with numerical integration of (13), and results from several starts are labeled local
  2. The aligned M1 optimistic bound accompanies every M3 result
  3. M4's common decisions replay as feasible in every enumerated scenario, in expected-cost and worst-case form

**Plans**: 2 plans

Plans:

- [x] 10-01: M3 charging law, fixed-schedule multi-start, integration check
- [x] 10-02: M4 scenario model and replay

### Phase 11: Studies and publication

**Goal**: A reader can regenerate every number in the README from committed commands and trace each to an executed check
**Depends on**: Phase 5, Phase 9, Phase 10
**Requirements**: RPT-01, RPT-02, RPT-03
**Design refs**: docs/VALIDATION.md §3, §5; docs/DESIGN.md §10
**Success Criteria** (what must be TRUE):

  1. `python run_bench.py` reproduces the experiment matrix and writes bundles carrying the revision
  2. Route maps, timelines, traces, and gap-versus-time plots render as static files
  3. `docs/VALIDATION.md` records every executed check with its revision, and every README number is regenerated

**Plans**: 2 plans

Plans:

- [ ] 11-01: Experiment matrix runner and result bundles
- [ ] 11-02: Figures, README results, validation record

## Progress

**Execution Order:**
Phases execute in numeric order. Phases 2, 3, and 6 depend only on Phase 1, so any of them may run in parallel after it.

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundations and EVRP data | 3/3 | Complete    | 2026-09-28 |
| 2. Interior-point core | 3/3 | Complete    | 2026-09-29 |
| 3. Exact EVRP MILP | 0/3 | Not started | - |
| 4. Branch-and-bound with interior-point nodes | 2/2 | Complete    | 2026-09-29 |
| 5. Column-generation bound | 0/3 | Not started | - |
| 6. Transit data and battery-free fleet | 2/2 | Complete    | 2026-09-29 |
| 7. Joint scheduling and charging | 3/3 | Complete    | 2026-09-29 |
| 8. Convex charging subproblems | 2/2 | Complete    | 2026-09-29 |
| 9. Outer approximation | 0/3 | Not started | - |
| 10. Nonconvex and scenario extensions | 2/2 | Complete    | 2026-09-29 |
| 11. Studies and publication | 0/2 | Not started | - |
