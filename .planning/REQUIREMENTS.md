# Requirements: Electric Fleet Optimization

**Defined:** 2026-09-28
**Core Value:** Every reported number is certified: a replayed feasible solution and a valid lower bound, with the gap stated, or an explicit status saying why not.

Formulation labels (R1.3, (A3), (7), ...) refer to `docs/ROUTING.md`, `docs/MODELS.md`, and `docs/ALGORITHMS.md`.

## v1 Requirements

### Foundations

- [x] **FND-01**: User can install the project into the system Python 3.14 from `requirements.txt` and get `pytest`, `ruff check`, and `pip check` passing
- [x] **FND-02**: User can read a toolchain note stating the installed SciPy/HiGHS versions and whether `milp`, `highs-ipm` (including duals before crossover), and `trust-constr` behave as documented on Python 3.14/Windows
- [x] **FND-03**: Every solve returns a result record with the status taxonomy of Algorithms §8, the solver's own code and message, U, L, a gap only when both are valid, residuals, elapsed time, and provenance
- [x] **FND-04**: A GitHub Actions workflow runs `pytest` and `ruff` on committed fixtures for every push to `main`

### Data

- [x] **DATA-01**: User can fetch the 41 EVRP files from the pinned evrp-python commit, and every read verifies the file's SHA-256 against the committed manifest
- [x] **DATA-02**: The EVRP reader parses both header variants by keyword, checks every section count, and rejects any other edge-weight type
- [x] **DATA-03**: The textbook chapter references in `docs/SOURCES.md` are checked against both tables of contents and corrected where they differ

### Checks

- [x] **CHK-01**: User can replay any route file against an instance and receive coverage, load, battery (depot legs included), station and depot resets, the route count, and the length recomputed from coordinates
- [x] **CHK-02**: User can convert evrp-python's printed tours (0-based identifiers) into the exchange format and replay them

### Interior-point core

- [x] **IPM-01**: User can solve a standard-form LP with the textbook primal-dual method (A1), fraction-to-boundary steps, and stopping rule (A2), receiving x, y, s, and a status
- [x] **IPM-02**: The method's optimal values agree with `highs-ds` on Vanderbei's worked examples and on random feasible bounded LPs
- [x] **IPM-03**: For boxed LPs, the method reports the bound (A3) at every iterate, and it never exceeds the `highs-ds` optimum beyond tolerance
- [x] **IPM-04**: User can solve a convex QP by the same method (Vanderbei Ch. 24), with KKT residuals below tolerance
- [x] **IPM-05**: User can stop the method at a prescribed relative gap delta and receive the interior duals
- [x] **IPM-06**: Each solve reports matrix dimensions, factor nonzeros, factorization and solve times, and any regularization, with residuals against the unregularized equations

### Routing models

- [x] **EVRP-01**: User can build the station graph and the Pareto station paths P_ij for any instance and read the filtered path counts
- [x] **EVRP-02**: User can solve R1 (free fleet, capacity bound on the route count) with HiGHS, and every returned solution passes the replay of CHK-01
- [x] **EVRP-03**: User can solve R0 on the same instance and read z(R1)-z(R0)
- [x] **EVRP-04**: On sub-instances of at most six customers, R1, R1-TR (depot split), and brute-force enumeration agree on the optimal value
- [x] **EVRP-05**: User can run evrp-python's GSGA from an outside checkout and replay its solutions, or the comparison labels its published values as unreplayed
- [ ] **EVRP-06**: For each of the seven 2019 E instances, a result states certified optimal, bracketed with gap, or open, against the report's value and evrp-python's

### Branch-and-bound

- [x] **BNB-01**: User can run the educational branch-and-bound on a bounded MILP with LP nodes solved by the textbook IPM or `highs-ipm`, most-fractional branching, and pruning only on certified bounds (A3)
- [x] **BNB-02**: On tiny R1 instances the tree reaches the HiGHS optimum and reports nodes, the global bound trajectory, and the bounds obtained at inexactly solved nodes
- [x] **BNB-03**: The tree accepts an incumbent only after fixing integers, re-solving the continuous variables, and passing replay

### Column generation

- [x] **CG-01**: User can solve R2's restricted master by the early-terminated textbook IPM and by HiGHS simplex, reading duals from each
- [x] **CG-02**: User can price exactly over ng-routes with load and battery resources on the station-path multigraph; heuristic pricing is labeled and never produces a bound
- [x] **CG-03**: The bound (R2.2) is evaluated at every iteration with exact pricing and never exceeds a replayed feasible length
- [x] **CG-04**: User can compare interior and simplex duals by outer iterations, pricing calls, time, and final bound on the 2019 E set
- [x] **CG-05**: The restricted master solved as a MILP over generated columns yields a replayed upper bound, and EVRP-06's statuses are updated with R2's bounds

### Transit models

- [x] **TRN-01**: User can build a service-day instance from a pinned TransLink GTFS snapshot, including trips after midnight, and extract a corridor
- [x] **TRN-02**: User can build the trip compatibility DAG with deadhead and turnaround times, pruned by reachability from and to the depot
- [x] **TRN-03**: User can solve M0 as a matching LP and as a min-cost flow; the fleet sizes agree and duties are extracted without rounding an interior point
- [x] **TRN-04**: Where the feed has `block_id`, the M0 fleet is compared with the agency's block count for the same trips
- [x] **TRN-05**: User can build the time-space graph with the slot convention of Models §1 from a corridor and a declared Delta
- [x] **TRN-06**: User can solve M1, rows (1)-(8) assembled once, with HiGHS, and its LP relaxation with the textbook IPM
- [x] **TRN-07**: Every M1 schedule passes an independent replay: each trip once, time-connected paths, energy within bounds, plugs within capacity
- [x] **TRN-08**: Engineering parameters come from TOML scenario files in which every value has a unit and a source or the flag `illustrative`
- [x] **TRN-09**: User can compare M1 with M0 on the corridor: buses, deadhead, and cost
- [x] **TRN-10**: On tiny M1 instances the branch-and-bound of BNB-01 reaches the HiGHS optimum

### Convex subproblems

- [x] **NLP-01**: User can solve M1-Q's fixed-integer QP by the textbook QP method, agreeing with an independent solve
- [x] **NLP-02**: User can solve M2's fixed-integer NLP by `trust-constr` with analytic gradients and Hessians that agree with finite differences
- [x] **NLP-03**: User can solve R3's fixed-route problem with the closed perspective, eliminating fixed-zero faces before the barrier solve
- [x] **NLP-04**: Each fixed-integer solve reports the bound (A5) and KKT residuals, and (A5) never exceeds the subproblem value

### Outer approximation

- [x] **OA-01**: User can run OA (A6) with the master dual bound as L, only replayed solutions as U, restoration for suspected infeasible assignments, and status `stall` when no violated cut is found
- [x] **OA-02**: User can solve M2 by OA on the corridor and read the M2-P bracket around it
- [x] **OA-03**: User can solve R3 by OA on small E instances under a declared scenario, read the R3-P bracket, and learn whether any R1 optimum uses a segment with two or more stations
- [x] **OA-04**: User can compare M2 with M1 and R3 with R1 over a declared parameter grid

### Extensions

- [x] **EXT-01**: User can solve M3 at fixed schedules from several feasible starts, with (14) checked against numerical integration, and read the aligned M1 optimistic bound; no M3 result is labeled global
- [x] **EXT-02**: User can solve M4 in expected-cost and worst-case form over an enumerated scenario set, with common decisions replayed in every scenario

### Studies and reporting

- [ ] **RPT-01**: `python run_bench.py` reproduces the experiment matrix of Validation §3 and writes result bundles carrying the revision
- [x] **RPT-02**: User can view static route maps, vehicle and charging timelines, power and state-of-charge traces, and gap-versus-time plots
- [x] **RPT-03**: Every number in the README is regenerated by a committed command, and `docs/VALIDATION.md` records each executed check with its revision

### Sourced parameters

- [x] **DATA-04**: Each engineering value of the Route 100 scenario is traced to a primary source recorded in `docs/SOURCES.md`, or labeled `illustrative`, and `docs/DATA.md` §3 states which
- [x] **TRN-11**: A scenario can declare a utility tariff (billing-demand window, riders, basic charge); M1, M3, the replay and the enumeration price it, and a scenario without it prices as before
- [ ] **TRN-12**: User can read Route 100's full day under BC Hydro's Overnight and Demand Transition rates and two pack sizes, against TransLink's 19 battery-electric buses

## v2 Requirements

### Models

- **V2-01**: R4, nonlinear charging functions on the Montoya instances
- **V2-02**: Time windows, multi-depot, heterogeneous fleets
- **V2-03**: Multi-day transit with energy carried between days
- **V2-04**: The 2022 set and the X instances, once the 2022 distance convention is established by replay

### Methods

- **V2-05**: Branch-and-price on R2
- **V2-06**: Homogeneous self-dual and predictor-corrector variants of the textbook IPM
- **V2-07**: Conic (SOCP) cross-check of M2 and R3 at fixed integers
- **V2-08**: Ipopt cross-check, if it installs on Python 3.14/Windows without a second environment
- **V2-09**: Rust/PyO3 kernel for R2 pricing, if profiling shows pricing dominates

## Out of Scope

| Feature | Reason |
|---------|--------|
| Driver rostering, labor agreements | Independent data and rules; vehicle schedules are not duties |
| Power flow, vehicle-to-grid, solar | Each needs its own physical model and data |
| Commercial solvers, modeling layers | No measurement shows a need |
| Second Python environment | The user's single-environment rule |
| Predictive ML, CVaR, distributionally robust models | No data or decision question justifies them yet (Models §7) |
| Web application | Results are static files |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FND-01 | Phase 1 | Complete |
| FND-02 | Phase 1 | Complete |
| FND-03 | Phase 1 | Complete |
| FND-04 | Phase 1 | Complete |
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| CHK-01 | Phase 1 | Complete |
| CHK-02 | Phase 1 | Complete |
| IPM-01 | Phase 2 | Complete |
| IPM-02 | Phase 2 | Complete |
| IPM-03 | Phase 2 | Complete |
| IPM-04 | Phase 2 | Complete |
| IPM-05 | Phase 2 | Complete |
| IPM-06 | Phase 2 | Complete |
| EVRP-01 | Phase 3 | Complete |
| EVRP-02 | Phase 3 | Complete |
| EVRP-03 | Phase 3 | Complete |
| EVRP-04 | Phase 3 | Complete |
| EVRP-05 | Phase 3 | Complete |
| EVRP-06 | Phase 3 | Pending |
| BNB-01 | Phase 4 | Complete |
| BNB-02 | Phase 4 | Complete |
| BNB-03 | Phase 4 | Complete |
| CG-01 | Phase 5 | Complete |
| CG-02 | Phase 5 | Complete |
| CG-03 | Phase 5 | Complete |
| CG-04 | Phase 5 | Complete |
| CG-05 | Phase 5 | Complete |
| TRN-01 | Phase 6 | Complete |
| TRN-02 | Phase 6 | Complete |
| TRN-03 | Phase 6 | Complete |
| TRN-04 | Phase 6 | Complete |
| TRN-05 | Phase 7 | Complete |
| TRN-06 | Phase 7 | Complete |
| TRN-07 | Phase 7 | Complete |
| TRN-08 | Phase 7 | Complete |
| TRN-09 | Phase 7 | Complete |
| TRN-10 | Phase 7 | Complete |
| NLP-01 | Phase 8 | Complete |
| NLP-02 | Phase 8 | Complete |
| NLP-03 | Phase 8 | Complete |
| NLP-04 | Phase 8 | Complete |
| OA-01 | Phase 9 | Complete |
| OA-02 | Phase 9 | Complete |
| OA-03 | Phase 9 | Complete |
| OA-04 | Phase 9 | Complete |
| EXT-01 | Phase 10 | Complete |
| EXT-02 | Phase 10 | Complete |
| RPT-01 | Phase 11 | Pending |
| RPT-02 | Phase 11 | Complete |
| RPT-03 | Phase 11 | Complete |
| DATA-04 | Phase 12 | Complete |
| TRN-11 | Phase 12 | Complete |
| TRN-12 | Phase 12 | Pending |

**Coverage:**

- v1 requirements: 55 total
- Mapped to phases: 55
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-28*
*Last updated: 2026-09-29 after the OA-04 grid*
