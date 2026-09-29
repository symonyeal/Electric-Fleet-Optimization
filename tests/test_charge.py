# Fixed-integer charging subproblems (Models §4, Algorithms §5): M1-Q by the textbook QP method
# and by trust-constr, M2 by a barrier method with analytic derivatives, and the bound (A5).

import numpy as np
import pytest

from models.charge import grad_check, m1q_fixed, m2_fixed
from models.fleet import m1


def solved(seed):
    import sys
    sys.path.insert(0, "tests")
    from test_fleet import tiny
    c, v = tiny(seed)
    r = m1(c, v, fixed={"A": dict(n=1, h=500.0)}, keep_x=True)
    return c, v, np.array(r["x"])


@pytest.mark.parametrize("seed", range(4))
def test_m1q_by_the_qp_method_and_trust_constr(seed):
    c, v, x = solved(seed)
    r = m1q_fixed(c, v, x, fixed={"A": dict(n=1, h=500.0)})
    assert r["status"] == "optimal" and r["independent"] == pytest.approx(r["f"], rel=1e-5)
    assert r["L"] <= r["f"] + 1e-6 and r["f"] - r["L"] <= 1e-5 * (1 + abs(r["f"]))


@pytest.mark.parametrize("seed", range(4))
def test_m2_barrier_with_bound(seed):
    c, v, x = solved(seed)
    r = m2_fixed(c, v, x, fixed={"A": dict(n=1, h=500.0)})
    assert r["status"] == "optimal" and r["L"] <= r["f"] + 1e-6
    assert r["f"] - r["L"] <= 1e-4 * (1 + abs(r["f"]))
    assert r["loss_slack"] >= -1e-6              # every loss row holds at the barrier point


def test_m2_costs_at_least_m1_at_the_same_integers():
    """Losses only add cost at fixed integers when the taper is not binding."""
    c, v, x = solved(1)
    a = m1q_fixed(c, dict(v, charger=dict(v["charger"], gamma=0.0)), x,
                  fixed={"A": dict(n=1, h=500.0)})
    b = m2_fixed(c, dict(v, charger=dict(v["charger"], gamma=0.0)), x,
                 fixed={"A": dict(n=1, h=500.0)})
    assert b["f"] >= a["f"] - 1e-6


def test_derivatives_agree_with_finite_differences():
    """This check found a Jacobian that wrote coefficients into CSR data in coordinate order."""
    c, v, x = solved(0)
    assert grad_check(c, v, x, fixed={"A": dict(n=1, h=500.0)}) < 1e-6


@pytest.mark.parametrize("seed", range(4))
def test_two_barrier_methods_agree(seed):
    """The textbook method (Vanderbei Ch. 25) and trust-constr, from different starts."""
    from models.charge import m2_trust
    c, v, x = solved(seed)
    a = m2_fixed(c, v, x, fixed={"A": dict(n=1, h=500.0)})
    b = m2_trust(c, v, x, fixed={"A": dict(n=1, h=500.0)})
    assert b["status"] in (1, 2) and b["violation"] < 1e-8
    assert b["f"] == pytest.approx(a["f"], rel=1e-6) and b["bound"] <= b["f"] + 1e-6
