# Toolchain

Measured 28 September 2026 on the system Python 3.14.7 (Windows 10, AMD64): numpy 2.5.3,
SciPy 1.18.1 with its bundled HiGHS 1.12.0, pytest 9.1.1, ruff 0.16.7. Each statement below is
pinned by a test in `tests/test_toolchain.py`; a SciPy upgrade that changes one fails there.

On 29 September 2026 the same tests passed on a second machine, a 13th Gen Intel Core i5-1335U
(Windows 11) with Python 3.14.3, numpy 2.4.4 and SciPy 1.17.1, which bundles the same HiGHS
1.12.0. The benchmark runs of that date executed there. Since revision 9c00dc3 every result
bundle names its processor and versions under `provenance.host`; elapsed times and
time-limited bounds are comparable only between bundles that share them.

| Capability | Finding | Consequence |
| --- | --- | --- |
| `milp` | Returns `mip_dual_bound`, `mip_gap`, `mip_node_count` with the incumbent | Lower bounds come from `mip_dual_bound`, never from `fun` |
| `linprog(method="highs-ipm")` | With the HiGHS options `run_crossover="off"` and `presolve=False`, passed verbatim (SciPy warns they are unrecognized), it returns a point inside the optimal face, with its duals; with crossover on, a vertex | An interior optimal point, and its duals, are available from HiGHS when solved to optimality |
| `highs-ipm` stopped early | An iteration limit or a loose `ipm_optimality_tolerance` returns status 1 or 4 with no point and no duals | Early-terminated interior duals for column generation (R2) come only from `methods/ipm.py` |
| `minimize(method="trust-constr")` | Inequality constraints select `tr_interior_point`. At default options it stops on its gradient test with the barrier parameter at 8e-4, 2e-4 from the optimum of a two-variable QP; with `initial_barrier_parameter=1e-8` it lands within 1e-9 | Fixed-integer barrier solves set the initial barrier parameter explicitly; bounds use (A5), which holds at any accuracy |

The evrp-python baseline imports loguru, matplotlib and pandas, none installed. Its runner, added in
Phase 3, supplies stub modules instead of adding packages to the single environment
([Routing](ROUTING.md) §9).
