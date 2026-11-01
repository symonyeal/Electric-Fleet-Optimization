# Working contract

Read before changing anything. [README](README.md) states what the models are and how to run
them; [Validation](docs/VALIDATION.md) states what must be, and has been, checked. This file
states the rules a change must not break. Codex reads it as its fallback project file.

## Always on

| Rule | Reason |
| --- | --- |
| Report no solve outcome that was not read back from the result that produced it. | A requested tolerance is not a result. HiGHS stops at the relative MIP gap it is given. |
| Build a lower bound only from HiGHS's dual bound, (R2.4) after exact pricing, or an outer-approximation master's dual bound; never from an incumbent. | An incumbent is an upper bound. (R2.4) is valid for any duals only when pricing was exact. |
| Name a failed solve by its status: infeasible, limit, unbounded, numerical, stall. | Malformed data and an instance no schedule can serve both end in a failed solve. Only the second is an infeasibility. |
| Treat a published value, from the report or evrp-python, as an input to replay. | [Routing](docs/ROUTING.md) records why their numbers are not results until replayed. |
| Cite only what [Sources](docs/SOURCES.md) records, and add the entry in the change that uses it. | A formulation is validated by the paper it implements, not by the solver that ran it. |
| Add a dependency or a model only with a consumer that needs it; keep no reference implementation. | Every kept line is maintained; alternates are archived outside the repository. |
| State what was measured and what was not. | "Not measured" is a finding. A projection from row counts is not a runtime. |

## The feasible set is written once

Each model's rows live in one module (`evrp/r1.rs`, `r2.rs`, `r3.rs`, `transit/fleet.rs`), and
every method reaches them there: the MILP, the fixed-integer barrier subproblem, and the outer
approximation master. The replays (`evrp/replay.rs`, `transit/replay.rs`) and the test oracles
(`evrp/enumerate.rs`, `transit/enumerate.rs`) never import a formulation: they recompute routes,
schedules and costs from the instance and the returned decisions alone.

## Layout

`crates/efo-kernels` holds the numerical kernels without domain knowledge: ng-route pricing and
the interior-point method with its sparse factorization. `crates/efo` holds the formulations,
the HiGHS calls, the replays, the result contract, bundles, the report and the `efo` command.

## Code

Code transcribes the mathematics: symbol names from the documents (`A, b, c, x, y, u, pi, lam,
eps`), the problem stated in each public doc comment, loops whose condition is the stopping rule,
comments that cite the source. Mathematical outcomes are return values, not panics.

## Before a change is finished

```text
cargo fmt --all -- --check
cargo clippy --workspace --all-targets --locked -- -D warnings
cargo test --workspace --locked --release
cargo run --release -p efo -- report     # needs data/fetched; the report must not change
```

HiGHS is built from source: CMake and libclang must be found (`CMAKE`, `LIBCLANG_PATH`). A
behavioral change states its effect in numbers, with the instance and revision. Result bundles
are written only from committed code and carry the commit that produced them.
