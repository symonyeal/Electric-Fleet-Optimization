# Working contract

Read before changing anything. [README](README.md) states what the models are;
[Design](docs/DESIGN.md) states why they are that way; [Validation](docs/VALIDATION.md)
states what must be, and has been, checked. This file states the rules a change must
not break. Codex reads the same file through [AGENTS.md](AGENTS.md).

## Always on

| Rule | Reason |
| --- | --- |
| Report no solve outcome that was not read back from the result that produced it. | A requested tolerance is not a result. HiGHS stops at its default relative MIP gap unless told otherwise. |
| Build a lower bound only from a solver dual bound, (A3), (A5), or (R2.2), never from an incumbent. | An incumbent is an upper bound. A bound from inexact duals is valid only through those constructions. |
| Name a failed solve by its status: infeasible, limit, unbounded, numerical, stall. | Malformed data and an instance no schedule can serve both end in a failed solve. Only the second is an infeasibility. |
| Treat a published value, from the report or evrp-python, as an input to replay. | [Routing](docs/ROUTING.md) §9 records why their numbers are not results until replayed. |
| Cite only what [Sources](docs/SOURCES.md) records, and add the entry in the change that uses it. | A formulation is validated by the paper it implements, not by the solver that ran it. |
| Add a dependency only after measurement. Use the system Python 3.14; no virtual environment. | numpy, scipy, and HiGHS solve every planned model. |
| State what was measured and what was not. | "Not measured" is a finding. A projection from row counts is not a runtime. |

## The feasible set is written once

Each model's rows live in one module under `models/`, and every method reaches them
there: the LP relaxation, the MILP, branch-and-bound, the fixed-integer subproblem,
and the OA master. `checks/` never imports `models/`: the validators reconstruct
routes and schedules from instance files and returned solutions alone. R1-TR and the
enumeration in `checks/enum.py` are independent formulations by design; a second
copy of R1's rows would destroy the agreement they test.

## Code

Code transcribes the mathematics: symbol names from the documents (`A, b, c, x, y,
u, pi, lam, eps`), the problem stated in each public docstring, loops whose condition
is the stopping rule, comments that cite the source. Mathematical outcomes are return
values, not exceptions.

## Planning

Work follows the GSD roadmap in `.planning/`. A phase is complete when its success
criteria are demonstrated, not when its tasks are done.

## Before a change is finished

```text
python -m pytest -q
python -m ruff check .
python -m pip check
```

A behavioral change states its effect in numbers, with the instance and revision.
Committed result bundles carry the revision that produced them.
