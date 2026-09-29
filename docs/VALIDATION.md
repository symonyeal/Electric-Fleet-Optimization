# Validation

**Status: record of executed checks, revision 474149b and the changes committed with this file (29 September 2026).** Every
row below names the test that executes it; `python -m pytest -q` runs all of them
(`-m "not slow"` skips the four marked slow, `-m "not data"` those needing the fetched
benchmark or feed). Locally all pass on Python 3.14.7, numpy 2.5.3, SciPy 1.18.1, and the fast suite
(253 tests) on 29 September 2026 on Python 3.14.3, numpy 2.4.4, SciPy 1.17.1.
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
| Result contract | Status set; gap only with both bounds; negative gap flagged; solver code, time and provenance required; the revision is fixed at process start and ignores result files, planning notes and prose; provenance names the host | test_certificate.py | Pass |
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
| Tariff | Without tariff keys M1's rows and costs are unchanged; with BC Hydro RS 1640 riders, basic charge and a demand window from 06:00 or 07:30, M1, the enumeration and the replay agree on 6 tiny timetables; the 07:30 window moves charging and lowers the optimum; rider and basic charge by hand; a window without charging bills no demand | test_fleet.py | Pass |
| M1 | Equals path-cover enumeration on 6 tiny timetables; replay finds a removed charge; replay traces start at s0 B, stay above the reserve and sum to the charged energy; tree certifies tiny M1 with priority; Route 100 morning bound and replay; IPM relaxation equals highs-ds | test_fleet.py | Pass |
| M1-Q, M2 subproblems | QP method equals trust-constr; two barrier methods agree to 1e-6; (A5) below the value; derivatives match finite differences | test_charge.py | Pass |
| OA, M2 | Known convex MINLP certified; M2 inside M2-P; z(M2) >= z(M1); bounds nondecreasing | test_oa.py | Pass |
| R3 | Free charging equals R1 (one station per segment); scenario R3 inside R3-P and replays; fixed-route bound tight | test_recharge.py | Pass |
| M3, M4 | (14) against integration; local M3 above the M1 bound; M4 against wait-and-see and worst case, replay per scenario | test_extensions.py | Pass |
| Report | Multi-station segments counted on hand-made routes, the depot excluded | test_bench.py | Pass |

Defects these checks found, each now pinned by a test: the IPM's stopping rule under
large bounds (Phase 2 verifier); standard() mutating its sparse input; a precedence
error in R1-TR's load row; bundle revisions stamped at completion rather than at start, and marked dirty by
run_bench.py's own rewrite of README.md; the redundant master bound lam <= 1; a Jacobian written into
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
| Route 100 on sourced parameters | Route 100, full day | M1 under BC Hydro RS 1640 and RS 1650 with two pack sizes: fleet, plugs, on-route energy, billed demand, electricity cost, against TransLink's 19 buses |
| Scale | Corridor subsets of increasing size | Where each method stops returning a certificate |

**4. Scale limits measured so far**

From the bundles in `docs/results` ([Results](results/README.md)):

- R1 with HiGHS certified E-n23-k3 in 211 s and did not close E-n22-k4 in 600 s
  (L = 341.25 against U = 384.68). R0 certified both; on E-n30-k3 it stopped at
  600 s with a 26.8% gap.
- R2 bounded E-n22-k4 at 380.50, well above R1's bound: 9.8 s with interior duals,
  39.3 s with simplex duals (the first machine; its bundles record no host).
- From 29 September 2026 the runs used a second machine (Intel Core i5-1335U, SciPy 1.17.1,
  the same HiGHS 1.12.0), two cases at a time; each bundle names its host
  ([Toolchain](TOOLCHAIN.md)). On E-n23-k3 both dual sources converged to the LP bound
  561.7179, interior duals in 197.6 s and simplex duals in 416.5 s; R1's certified optimum
  571.9474 lies 1.8% above it. On E-n30-k3 simplex duals converged to 484.5677 in 849.8 s,
  while the textbook IPM master stopped at its iteration limit in 122 of 156 outer
  iterations and the run ended at its 1,800 s limit with bound 417.97. Interior duals are
  therefore not uniformly faster: they won on the two smallest instances and failed on the
  third. Why the master stops there is not yet investigated.
- E-n30-k3 is bracketed at [484.5677, 527.2049] (R2's bound, R1's incumbent at 600 s; gap
  8.09%). The report's 511.2539 lies inside the bracket, so it is neither certified nor
  refuted. R0 on E-n33-k4 stopped at 600 s with L = 662.12.
- M1 certified Route 100 to 08:00 (54 trips) and reached a 0.85% gap to 10:00
  (77 trips, 900 s). For the full day (219 trips) it stopped at 1,800 s with a 36.6%
  gap: the bound stays near the battery-free cost.
- The charging-physics grid (OA-04) was run twice. The first design compared M2 with M1 on
  Route 100 before 06:30 with the declared 250 kWh battery, where no bus charges (least
  energy 135.6 kWh against a 50 kWh reserve), so M2 = M1 at every alpha: true, and empty.
  The grid now adds a declared 100 kWh battery, with which the window charges and loss costs
  0.053, 0.107 and 0.208 CAD at the three alphas, each certified by OA. R3 on the eight far
  customers of E-n22-k4 stalled at alpha = 0 after 1,203 s with an 18.5% gap: the loss row is
  linear there, so the OA master MILP itself did not close within 600 s. On six customers R3
  is certified at alpha 0, 2.5e-4 and 5e-4, with routes 3.17 (1.2%) longer than R1's at every
  alpha. At alpha = 1e-3 it stalls with no incumbent, L = 293.81: the fixed-route barrier
  subproblem reached its iteration limit on all three assignments. That alpha puts the
  cost-optimal power sqrt(c_tau / (c_e alpha)) at exactly P = 100, so the optimum lies on
  q <= P tau with a zero multiplier, where strict complementarity fails. On the certified
  alpha = 5e-4 routes the same subproblem converges in 0.4 s at alpha = 0.99e-3 (293.791) and
  1.01e-3 (293.838) and fails only at 1e-3. The grid point is kept as a measured limit of the
  textbook barrier, not moved.
- Route 100 on sourced parameters ([Data](DATA.md) §3) is not yet measured: the four
  full-day runs (`python run_case.py transit route100 M1 --scenario rs1640-range --time 1800`,
  likewise `rs1650-range`, and `rs1640`, `rs1650` at 600 s) were stopped at the user's request
  4.5 minutes in, and wrote no bundle. One probe, not a bundle and run before the tariff terms
  existed, set the 594 kWh pack, 1.429 kWh/km, eta 0.90 and 5 plugs per loop in the
  illustrative scenario: in 300 s M1 found a replayed full-day schedule on 16 buses with no
  on-route charging (U = 7,539.60, L = 7,052.19), though 6 of M0's 16 battery-free duties fall
  below the reserve with that pack. That is why the `-range` files exist.
- Not yet measured: R1 and R2 on E-n33-k4; R0, R1 and R2 on E-n51-k5 to E-n101-k8
  (15 cases; `python run_bench.py --run --missing`).

**5. Acceptance criteria for the first release**

1. Every check in §2 for R0-R3, M0-M2, the IPM, branch-and-bound, and OA passes,
   or its failure is recorded with the revision.
2. For each of the seven 2019 E instances, the report states one of: certified
   optimal, bracketed with a stated gap, or open, with the evidence.
3. The corridor study reports M0, M1, and M2 with bounds and replayed schedules.
4. Every number in the README is regenerated by a committed command and carries
   the revision that produced it.
