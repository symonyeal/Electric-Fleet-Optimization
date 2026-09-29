# Toolchain

Measured 28 September 2026 on the system Python 3.14.7 (Windows 10, AMD64): numpy 2.5.3,
SciPy 1.18.1 with its bundled HiGHS, pytest 9.1.1, ruff 0.16.7. Each statement below is
pinned by a test in `tests/test_toolchain.py`; a SciPy upgrade that changes one fails there.

| Capability | Finding | Consequence |
| --- | --- | --- |
| `milp` | Returns `mip_dual_bound`, `mip_gap`, `mip_node_count` with the incumbent | Lower bounds come from `mip_dual_bound`, never from `fun` |
| `linprog(method="highs-ipm")` | With the HiGHS options `run_crossover="off"` and `presolve=False`, passed verbatim (SciPy warns they are unrecognized), it returns a point inside the optimal face; with crossover on, a vertex | An interior optimal point is available from HiGHS |
| `highs-ipm` stopped early | An iteration limit or a loose `ipm_optimality_tolerance` returns status 1 or 4 with no point and no duals | Early-terminated interior duals for column generation (R2) come only from `methods/ipm.py` |
| `minimize(method="trust-constr")` | Inequality constraints select `tr_interior_point`. At default options it stops on its gradient test with the barrier parameter at 8e-4, 2e-4 from the optimum of a two-variable QP; with `initial_barrier_parameter=1e-8` it lands within 1e-9 | Fixed-integer barrier solves set the initial barrier parameter explicitly; bounds use (A5), which holds at any accuracy |

The evrp-python baseline imports loguru, matplotlib and pandas, none installed. Its runner
supplies stub modules instead of adding packages to the single environment
([Routing](ROUTING.md) §9).
