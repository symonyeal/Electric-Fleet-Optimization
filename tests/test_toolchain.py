# Characterization of the installed SciPy/HiGHS (docs/TOOLCHAIN.md). These pin library
# behavior the design depends on; a SciPy upgrade that changes it fails here first.

import warnings

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp, minimize

# min x1 + x2 s.t. x1 + x2 >= 1, x3 <= 1, 0 <= x <= 2: the optimal face is a segment.
c = np.array([1.0, 1.0, 0.0])
A, b = np.array([[-1.0, -1.0, 0.0], [0.0, 0.0, 1.0]]), np.array([-1.0, 1.0])


def ipm(**o):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")          # HiGHS options SciPy does not list
        return linprog(c, A_ub=A, b_ub=b, bounds=[(0, 2)] * 3, method="highs-ipm", options=o)


def test_milp_reports_its_dual_bound():
    r = milp([1, 1], constraints=LinearConstraint([[1, 2]], 1.5, np.inf), integrality=[1, 1],
             bounds=Bounds(0, 5))
    assert r.status == 0 and r.fun == 1.0 and r.mip_dual_bound == 1.0
    assert {"mip_gap", "mip_node_count"} <= set(r.keys())


def test_highs_ipm_without_crossover_stops_inside_the_optimal_face():
    r = ipm(run_crossover="off", presolve=False)
    assert r.status == 0 and min(r.x[:2]) > 0.1          # not a vertex
    assert min(ipm(run_crossover="on", presolve=False).x[:2]) == 0


def test_highs_ipm_exposes_no_early_duals():
    """Stopped early, HiGHS returns no point and no duals: interior duals need methods/ipm.py."""
    r = ipm(run_crossover="off", presolve=False, ipm_iteration_limit=2)
    assert r.status == 1 and r.x is None
    r = ipm(run_crossover="off", presolve=False, ipm_optimality_tolerance=1e-2)
    assert r.status == 4 and r.x is None


def test_trust_constr_accuracy_follows_its_barrier_parameter():
    """min (x1-1)^2 + (x2-2)^2 s.t. x1 + x2 <= 1: x* = (0, 1).

    At default options trust-constr stops on its gradient test with the barrier parameter at
    8e-4, 2e-4 from x*; started at mu = 1e-8 it lands within 1e-9.
    """
    def solve(**o):
        return minimize(lambda x: (x[0] - 1) ** 2 + (x[1] - 2) ** 2, [0.0, 0.0],
                        method="trust-constr", jac=lambda x: np.array([2 * (x[0] - 1),
                                                                         2 * (x[1] - 2)]),
                        hess=lambda x: 2 * np.eye(2),
                        constraints=[LinearConstraint([[1, 1]], -np.inf, 1)], options=o)
    r = solve()
    assert r.method == "tr_interior_point" and abs(r.x - [0, 1]).max() > 1e-4
    r = solve(initial_barrier_parameter=1e-8, initial_barrier_tolerance=1e-8,
              barrier_tol=1e-12, gtol=1e-12, xtol=1e-14)
    assert abs(r.x - [0, 1]).max() < 1e-9
