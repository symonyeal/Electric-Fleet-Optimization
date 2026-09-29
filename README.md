# Electric Fleet Model

Exact models for electric-vehicle routing and electric-bus scheduling with charging.
Each result carries a feasible upper bound, a valid lower bound, and an independent check.

**Status: design and plan only, 28 September 2026.** No solver, application code, or
measured optimization result exists. Implementation follows the
[roadmap](.planning/ROADMAP.md).

| Component | Model | Check |
| --- | --- | --- |
| [Routing](docs/ROUTING.md) | EVRP on a station-path multigraph (R1); battery-free bound (R0) | The report's own formulation and brute-force enumeration on sub-instances |
| [Routing bound](docs/ROUTING.md) | Set-partitioning LP by column generation with interior-point duals (R2) | A Lagrangian bound valid at every iteration; replayed published solutions |
| [Partial recharging](docs/ROUTING.md) | Convex MINLP with resistive charging loss (R3) | Tangent and secant MILP bracket; conic cross-check at fixed routes |
| [Transit](docs/MODELS.md) | Battery-free fleet (M0); joint scheduling and charging MILP (M1) | Matching against flow; agency blocks; schedule replay |
| [Charging physics](docs/MODELS.md) | Convex MINLP (M2), nonconvex taper (M3), scenarios (M4) | Outer-approximation bounds; closed-form integration |
| [Algorithms](docs/ALGORITHMS.md) | Primal-dual LP/QP method, branch-and-bound, outer approximation | HiGHS; textbook examples; certificate contract |

[Design](docs/DESIGN.md) states the decisions, [Data](docs/DATA.md) the inputs and their
provenance, [Validation](docs/VALIDATION.md) the checks each phase must pass, and
[Sources](docs/SOURCES.md) what each formulation rests on.

## Background

### The problem

An electric fleet trades range for charging. A delivery EV that cannot reach its
next customer detours to a station; a bus that cannot finish its block needs a
charger, a plug, and grid capacity at the right time. These are integer decisions
coupled to continuous energy, and the coupling is where the cost of electrification
sits.

### What this computes

Two applications share one certificate core.

**Routing.** The IEEE WCCI-2020 competition published an EVRP benchmark whose report
lists values that "could be optimal in some cases but [are] not verified yet". Later
heuristics, among them [evrp-python](https://github.com/NeiH4207/evrp-python), report
shorter routes on six of its seven small instances. No method there reports a lower
bound. This project solves the benchmark's MILP where it can, bounds it by column
generation where it cannot, and states per instance whether a published value is
certified, refuted, or open.

**Transit.** TransLink publishes its timetable as GTFS. Given those trips and declared
battery, charger, and grid parameters, the models determine which buses and chargers
can operate the timetable and at what cost, from a battery-free fleet bound up to a
convex MINLP with charging losses.

The question common to both: what do the battery and charging constraints cost,
relative to the same fleet without them, and can the answer be certified?

### Where interior-point methods enter

They solve continuous problems; integer decisions still need branch-and-bound,
decomposition, or outer approximation. Here they supply LP bounds at inexact
branch-and-bound nodes, well-centered duals for column generation, and barrier
solutions of the convex charging subproblems inside outer approximation. The
mathematics follows Vanderbei, *Linear Programming* (4th ed., 2014), and Beck,
*Introduction to Nonlinear Optimization* (2014).

### Where it stops

Small instances. One depot, homogeneous vehicles, no time windows, no driver duties,
no distribution-network power flow. Benchmark distances are unitless, and engineering
parameters are declared scenarios, not agency data. It does not reproduce TransLink
dispatch, authorize infrastructure, or match the speed of VROOM, PyVRP, or HiGHS.

## Run

Nothing runs yet. The target, on the system Python 3.14 with numpy and scipy:

```text
python -m pytest -q
python -m ruff check .
python run_case.py evrp E-n22-k4 R1
python run_bench.py
```
