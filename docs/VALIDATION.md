# Validation

**Status: record of executed checks, revision 6b2b737 (29 September 2026).** Every
row below names the test that executes it; `python -m pytest -q` runs all of them
(`-m "not slow"` skips the four marked slow, `-m "not data"` those needing the fetched
benchmark or feed). Locally all pass on Python 3.14.7, numpy 2.5.3, SciPy 1.18.1.
GitHub Actions runs the suite without `data` and `slow` on every push.

**1. What counts as evidence**

A result is accepted when a computation that does not share its code agrees with
it: a second formulation, a brute-force enumeration, a closed form, a textbook
example, a second solver, or an independent replay of the returned solution.
Agreement of a model with itself under a second solver method is weaker than
agreement with a second formulation, and is labeled so.

Tolerances are stated with each check. Unless stated otherwise: objective
agreement within 1e-6 relative, feasibility within 1e-7 in original units, and a
gap claim only under the contract of [Algorithms](ALGORITHMS.md) §8.

**2. Checks by component**

| Component | Check | Test (tests/...) | Result |
| --- | --- | --- | --- |
| Result contract | Status set; gap only with both bounds; negative gap flagged; solver code, time and provenance required | test_certificate.py | Pass |
| EVRP reader | 41 files verify SHA-256 and parse; both header variants; two NAME mismatches pinned | test_evrp_data.py | Pass |
| Route replay | Each defect of the hand fixtures named; valid routes at hand-computed lengths; evrp-python tours convert and replay | test_route_replay.py | Pass |
| Toolchain | milp dual bound; highs-ipm interior points, no early duals; trust-constr accuracy follows its barrier parameter | test_toolchain.py | Pass |
| Primal-dual LP | Vanderbei (2.1) and ex. 3.1; 20 random LPs and 11 further cases against highs-ds; nonzero lower bounds | test_ipm.py | Pass |
| Primal-dual LP | (A3) at every iterate below the optimum; infeasible and unbounded examples never optimal; early stop gives interior duals; large-bound counterexamples of the Phase 2 verification | test_ipm.py | Pass |
| Primal-dual LP | Normal equations agree with the quasi-definite system; standard() leaves its input untouched | test_ipm.py | Pass |
| Primal-dual QP | 10 random convex QPs against exact active-set enumeration | test_ipm.py | Pass |
| Convex constraints | Disc: closed-form optimum and multiplier; separable loss rows inside a 200-piece tangent/secant bracket | test_ipm.py | Pass |
| Station paths | Hand-computed Pareto set; brute-force dominance on E-n22-k4 | test_paths.py | Pass |
| R1, R1-TR | Agree with exhaustive enumeration on the fixture, 8 self-made and 3 E-n22-k4 sub-instances; every solution replays; z(R0) <= z(R1); infeasibility detected | test_route_models.py | Pass |
| Branch-and-bound | 0-1 programs and tiny R1 reach HiGHS's optimum with textbook, early-stopped and highs-ipm nodes; bounds nondecreasing; each early-stopped node's bound below its exact LP; validation required for incumbents | test_branch.py | Pass |
| R2 | Exact pricing equals brute force over all elementary routes; converged bound within tolerance of the full set-partitioning LP with both dual sources; bound below R1 at every iteration; status optimal only when certified | test_colgen.py | Pass |
| GTFS | Times past midnight; calendar then exceptions; Route 100 on 2026-10-07: 219 trips, 23 blocks; holiday runs Sunday service; fixture equals the snapshot | test_gtfs.py | Pass |
| M0 | Matching LP, min-cost flow and Hopcroft-Karp agree; Dilworth on 10 timetables; IPM midpoint not rounded; Route 100 fleet 16 <= 23 blocks | test_network.py | Pass |
| Scenarios | Values need unit and source | test_scenario.py | Pass |
| M1 | Equals path-cover enumeration on 6 tiny timetables; replay finds a removed charge; tree certifies tiny M1 with priority; Route 100 morning bound and replay; IPM relaxation equals highs-ds | test_fleet.py | Pass |
| M1-Q, M2 subproblems | QP method equals trust-constr; two barrier methods agree to 1e-6; (A5) below the value; derivatives match finite differences | test_charge.py | Pass |
| OA, M2 | Known convex MINLP certified; M2 inside M2-P; z(M2) >= z(M1); bounds nondecreasing | test_oa.py | Pass |
| R3 | Free charging equals R1 (one station per segment); scenario R3 inside R3-P and replays; fixed-route bound tight | test_recharge.py | Pass |
| M3, M4 | (14) against integration; local M3 above the M1 bound; M4 against wait-and-see and worst case, replay per scenario | test_extensions.py | Pass |

Defects these checks found, each now pinned by a test: the IPM's stopping rule under
large bounds (Phase 2 verifier); standard() mutating its sparse input; a precedence
error in R1-TR's load row; the redundant master bound lam <= 1; a Jacobian written into
CSR data in coordinate order; R3's one-sided charge rows; the tree's node budget on M1
without branching priority.

**3. Experiments**

| Experiment | Instances | Measures |
| --- | --- | --- |
| Certify the benchmark | 2019 E set | R1 status and gap per instance; R2 bound; comparison with the report and evrp-python |
| Price of the battery, routing | 2019 E set | z(R1)-z(R0), absolute and relative |
| Interior versus simplex duals | 2019 E set, ascending size | Outer iterations, pricing calls, time, final bound |
| IPM nodes in branch-and-bound | Tiny R1 and M1 | Nodes, bound quality at inexact nodes, time against HiGHS |
| Price of the battery, transit | One TransLink corridor | M1 against M0: buses, deadhead, cost |
| Price of charging physics | Corridor; 2019 E set | M2 against M1; R3 against R1 over a parameter grid |
| Scale | Corridor subsets of increasing size | Where each method stops returning a certificate |

**4. Scale limits to expect**

No limit below is measured. R1 with HiGHS is expected to certify the smallest
2019 instances and not the X set. R2 bounds are expected to reach further than
R1, limited by pricing. The textbook IPM is expected to be slower than HiGHS on
every instance; its purpose is interior duals and exposure of the method. Each
expectation is replaced by a measurement or removed.

**5. Acceptance criteria for the first release**

1. Every check in §2 for R0-R3, M0-M2, the IPM, branch-and-bound, and OA passes,
   or its failure is recorded with the revision.
2. For each of the seven 2019 E instances, the report states one of: certified
   optimal, bracketed with a stated gap, or open, with the evidence.
3. The corridor study reports M0, M1, and M2 with bounds and replayed schedules.
4. Every number in the README is regenerated by a committed command and carries
   the revision that produced it.
