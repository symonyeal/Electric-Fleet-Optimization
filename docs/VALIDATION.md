# Validation

**Status: no check has been executed.** This file specifies the evidence each
phase must produce. It becomes a record of executed checks, with the revision
that ran them, as phases complete.

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

| Component | Check | Pass criterion |
| --- | --- | --- |
| EVRP reader | Parse all 41 files of both sets | Counts match every section; SHA-256 matches the manifest |
| Route validator | Hand-built fixtures: missing customer, repeated customer, overload, empty battery on a depot leg, station reset, depot reset | Each defect reported by name; each valid fixture accepted with its hand-computed length |
| Route validator | Replay of the report's E-n22-k4 value | A replayed solution of length 384.678035 exists, or the discrepancy is recorded |
| Primal-dual LP | Vanderbei's worked examples; random feasible bounded LPs | Optimal values agree with `highs-ds`; residuals satisfy (A2) |
| Primal-dual LP | Bound (A3) at every iterate, on the same LPs | Never exceeds the `highs-ds` optimum by more than tolerance |
| Primal-dual LP | Infeasible and unbounded constructions | Status `numerical` or `limit`, never `optimal` |
| Primal-dual QP | Random strictly convex box QPs with one equality | KKT residuals below tolerance; objective agrees with exact active-set enumeration |
| Station paths | Pareto filter on small instances | Every discarded path is dominated by a kept one, checked pairwise |
| R1 | Sub-instances of at most 6 customers | R1, R1-TR, and brute-force enumeration agree on the optimal value |
| R1 | Every returned solution | Passes the route validator; length recomputed from coordinates agrees |
| R0, R1, R2 | Ordering on every instance | bound(R2) <= z(R1) and z(R0) <= z(R1), within tolerance |
| R2 | Bound (R2.2) with exact pricing | Never above any replayed feasible length; a violation is a defect |
| R2 | Interior versus simplex duals | Both reach the same master value; iteration counts reported, not asserted |
| Branch-and-bound | Tiny R1 and M1 instances | Same optimum as HiGHS; global lower bound nondecreasing; no node pruned on an uncertified bound |
| M0 | Matching LP, min-cost flow, and agency blocks | Matching and flow fleets agree; fleet at most the number of agency blocks for the same trips |
| M1 | Every returned schedule | Replay: each trip once, paths connected in time, energy within bounds, plugs within capacity |
| M1-Q, M2, R3 | Derivatives | Analytic gradients and Hessians agree with finite differences |
| M1-Q, M2, R3 | Fixed-integer subproblems | Bound (A5) <= subproblem value; optional conic solve agrees |
| OA | M2 and R3 | Lower bounds nondecreasing; final bracket within tolerance or status `stall` |
| M2-P, R3-P | Brackets | Lower MILP bound <= OA value <= reconstructed upper value |
| M3 | Charging law | Closed form (14) agrees with independent numerical integration of (13) |
| M3 | Local solutions | Several feasible starts; KKT residuals reported; never labeled global |
| M4 | Scenario feasibility | Common decisions replay as feasible in every enumerated scenario |

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
