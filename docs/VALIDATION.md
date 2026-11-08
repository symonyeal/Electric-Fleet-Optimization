# Validation

This page records the independent replay, formulation, and analytical checks behind each reported routing, vehicle-blocking, and
charging result, and the rule by which a result is admitted.

The gates are `cargo fmt --all -- --check`, `cargo clippy --workspace --all-targets --locked -- -D warnings` and `cargo test
--workspace --locked --release`. Results, with their timings, are in [Results](results/README.md); this page states no measured
values.

**1. What counts as evidence**

A result is accepted when a computation that does not share its code agrees with it: a second formulation, a brute-force
enumeration, a closed form, a textbook example, a second solver, or an independent replay of the returned solution. Agreement of
a model with itself under a second solver method is weaker than agreement with a second formulation, and is labeled so. The
replays and the enumeration oracles are written from the rules of the problem, not from the formulations they check.

Tolerances are stated with each check. Unless stated otherwise: objective agreement within 1e-6 relative, feasibility within
1e-7 in original units, and a gap claim only under the contract of [Algorithms](ALGORITHMS.md) §6.

**2. Checks by component**

| Component | Check |
| --- | --- |
| Result contract (`cert.rs`) | Two-sided gap rule: U = 100, L = 100.5 is `invalid_bound`, never certified, with a defect; a 1e-5 crossing within tolerance is certified and reported raw; the stored public fields are what the rule derives |
| Scenarios | Every committed scenario loads; an out-of-domain efficiency, a reserve above s0, a bare number, half a billing window and a stop owned by two sites are each refused; the billing window wraps past midnight |
| EVRP reader, route replay | The tiny fixture reads as written; each defect kind is named on hand-made routes; the enumerated optimum replays at its length |
| Stored R3 decisions | Negative and non-finite energy/dwell, malformed keys and keys outside station visits are refused; zero and positive charges still replay; report collection admits the original pinned bundle and refuses its negative-charge mutation |
| Bundle publication | Repeated publication preserves the original bytes; two concurrent writers to one unused path have exactly one winner and leave a complete readable bundle |
| Kernel | A textbook LP by the normal equations; a convex row against its closed-form optimum; the quasi-definite LDL' solve; duplicate entries summed and mirrored |
| Barrier wrapper | A row side tight on the box becomes an equality, not a slack in [0, 0] (that slack made every M2 subproblem on Route 100 numerical) |
| Station paths | Path counts equal those of the previous implementation on 5 fixtures |
| R1 | Equals exhaustive enumeration on 5 fixtures; a battery too short for any customer is infeasible for both |
| R2 | Exact pricing equals brute force over all elementary routes on 3 fixtures; on 5 fixtures the run converges, L lies below and U above the enumerated optimum, and the status is `optimal` only when the gap is closed |
| R3 | With free charging equals R1 when R1's routes pass at most one station per segment, and is never below it; under the declared scenario it certifies and its replayed length is at most its cost |
| M0 | 16 buses on Route 100 (21041 compatible pairs, 23 blocks, 0 violations), certified by the replay |
| M1 | Equals tiny-timetable enumeration on 6 seeds, and the free model equals the previous implementation; base load: a site too dear to open stays closed whether L fits its capacity or not; an open site bills L x peak price even when no slot of its billing window can charge, by M1, the enumeration and the replay alike |
| M2, OA | At fixed integers the barrier equals the HiGHS LP at alpha = 0 and is at least it at alpha > 0; M2 by OA equals the previous implementation on two tiny seeds; OA certifies the integer minimum of a convex bowl and stops as `numerical` when a replay under-reports U |

The certificate and base-load tests pin defects found in an audit of an earlier revision: a one-sided certificate that
certified L above U, and base load entering only the rows with charging variables.

**3. How results are admitted**

A result is a bundle, a JSON file at `docs/results/<track>/<stem>.json`, holding the record of the result contract, the case
(track, instance, model, options), the code commit and a flag for whether the code differed from it, the host (processor and
thread count; elapsed times compare only on one host), the SHA-256 of every input file, and the command line. `efo report`
regenerates `docs/results/README.md` and the README block from the admitted bundles. A bundle is admitted when:

1. its code is committed; the CLI refuses to write a bundle from a tree whose code differs from its commit;
2. the record is self-consistent under the two-sided rule of [Algorithms](ALGORITHMS.md) §6;
3. its formulation version is the current one (`R1/1`, `R2-RCC/1`, `R3/1`, `M0/2`, `M1/2`, `M2/2`);
4. its input digests match the inputs on disk;
5. the replay reproduces U.

An upper bound needs no further provenance: a route set or schedule that the replay accepts certifies its own cost.

**4. Scale limits**

Stated qualitatively, as observed in the Python implementation (revision 89e967d); the measured values of the Rust build are in
[Results](results/README.md).

Measured scaling of the Rust build, read from the committed bundles (one run each, 1800 s limit, one thread, AMD Ryzen 7 PRO
6850U, revision 8f07c5c recorded in every bundle; `efo` reports `elapsed` and `host` in the bundle). `n` is the customer count.

| Model | Instance | n | Status | Time (s) | Gap |
|---|---|---:|---|---:|---:|
| R2 | E-n22-k4 | 21 | optimal | 1.3 | 0 |
| R2 | E-n23-k3 | 22 | optimal | 21.2 | 0 |
| R2 | E-n30-k3 | 29 | optimal | 14.7 | 0 |
| R2 | E-n33-k4 | 32 | optimal | 67.7 | 0 |
| R2 | E-n51-k5 | 50 | feasible_limit | 13.9 | 24.6% |
| R2 | E-n76-k7 | 75 | feasible_limit | 43.4 | 28.3% |
| R2 | E-n101-k8 | 100 | feasible_limit | 283.7 | 33.0% |
| R3 (alpha 0) | E-n22-k4, 6 farthest customers | 6 | optimal | 84.3 | 0 |
| R3 (alpha 0) | E-n22-k4, 8 farthest customers | 8 | stall | 1200.5 | 20.3% |

Time does not grow smoothly with n: R2 stops when its relaxation converges and the restricted MILP over the generated columns
ends, so the larger instances finish early with a gap that only branching would close. Pricing is O(R n^2) per call for R
labels (`completion`, `price.rs`), and R3 adds one outer-approximation iteration per violated cut, so eight customers already
exhaust the time limit. Instances 10 times larger than E-n101-k8 (1000 customers) and R3 beyond eight customers are not measured
and are not claimed. R2 refuses more than 128 customers (the ng-sets are `u128` masks).

- R1 with HiGHS closes the smallest benchmark instances and leaves a gap on the larger E instances inside a time limit.
- R2 with cuts and exact pricing certifies the smallest instances. On the larger ones the relaxation converges to a valid bound
  that lies below the published values, and the restricted MILP over the generated columns gives an incumbent above it. The
  remaining gap belongs to the relaxation and the incumbent, which only branching would close, not to pricing time.
- M1 certifies Route 100 for a morning window. For the full day the bound stays near the battery-free cost within the time
  limit, and a gap remains.
- A fixed-route barrier subproblem of R3 fails to converge when the cost-optimal charging power lies exactly on the power limit
  with a zero multiplier, where strict complementarity fails (observed in the Python implementation, revision 89e967d). Such a
  grid point is kept as a measured limit of the barrier method, not moved.
