# Validation

**Status: record of executed checks, revision 2ce4b8b and the changes committed with this file (29 September 2026).** Every
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
| Result contract | Status set; gap only with both bounds; negative gap flagged; solver code, time and provenance required; the revision is fixed at process start and ignores result files | test_certificate.py | Pass |
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
| M1 | Equals path-cover enumeration on 6 tiny timetables; replay finds a removed charge; replay traces start at s0 B, stay above the reserve and sum to the charged energy; tree certifies tiny M1 with priority; Route 100 morning bound and replay; IPM relaxation equals highs-ds | test_fleet.py | Pass |
| M1-Q, M2 subproblems | QP method equals trust-constr; two barrier methods agree to 1e-6; (A5) below the value; derivatives match finite differences | test_charge.py | Pass |
| OA, M2 | Known convex MINLP certified; M2 inside M2-P; z(M2) >= z(M1); bounds nondecreasing | test_oa.py | Pass |
| R3 | Free charging equals R1 (one station per segment); scenario R3 inside R3-P and replays; fixed-route bound tight | test_recharge.py | Pass |
| M3, M4 | (14) against integration; local M3 above the M1 bound; M4 against wait-and-see and worst case, replay per scenario | test_extensions.py | Pass |
| Report | Multi-station segments counted on hand-made routes, the depot excluded | test_bench.py | Pass |

Defects these checks found, each now pinned by a test: the IPM's stopping rule under
large bounds (Phase 2 verifier); standard() mutating its sparse input; a precedence
error in R1-TR's load row; bundle revisions stamped at completion rather than at start; the redundant master bound lam <= 1; a Jacobian written into
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

**4. Scale limits measured so far**

From the bundles in `docs/results` ([Results](results/README.md)):

- R1 with HiGHS certified E-n23-k3 in 211 s and did not close E-n22-k4 in 600 s
  (L = 341.25 against U = 384.68). R0 certified both; on E-n30-k3 it stopped at
  600 s with a 26.8% gap.
- R2 bounded E-n22-k4 at 380.50, well above R1's bound: 9.8 s with interior duals,
  39.3 s with simplex duals. On E-n23-k3 neither dual source finished within the
  session; the runs were stopped.
- M1 certified Route 100 to 08:00 (54 trips) and reached a 0.85% gap to 10:00
  (77 trips, 900 s). For the full day (219 trips) it stopped at 1,800 s with a 36.6%
  gap: the bound stays near the battery-free cost.
- Not yet measured: R0, R1 and R2 on E-n33-k4 to E-n101-k8; the charging-physics grid
  of §3 (`python run_bench.py --grid`).

**5. Acceptance criteria for the first release**

1. Every check in §2 for R0-R3, M0-M2, the IPM, branch-and-bound, and OA passes,
   or its failure is recorded with the revision.
2. For each of the seven 2019 E instances, the report states one of: certified
   optimal, bracketed with a stated gap, or open, with the evidence.
3. The corridor study reports M0, M1, and M2 with bounds and replayed schedules.
4. Every number in the README is regenerated by a committed command and carries
   the revision that produced it.
