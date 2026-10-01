# Educational branch-and-bound (Algorithms §4) against HiGHS, on 0-1 programs and tiny R1.

import itertools
import sys

import numpy as np
import pytest
from scipy.optimize import Bounds, LinearConstraint, linprog, milp

from checks.route import replay
from data.evrp import read
from methods.branch import bnb
from models.route import r1, routes_of, rows

sys.path.insert(0, "tests")
from test_route_models import rand_instance

TINY = read("tests/fixtures/tiny.evrp")


def knapsack(seed, n=10):
    """max p'x, w'x <= W, one cover row, x binary, as min -p'x."""
    g = np.random.default_rng(seed)
    p, w = g.integers(5, 40, n).astype(float), g.integers(3, 30, n).astype(float)
    A = np.vstack([w, np.r_[np.ones(n // 2), np.zeros(n - n // 2)]])
    return -p, A, np.array([-np.inf, 1]), np.array([w.sum() / 2, np.inf]), np.zeros(n), np.ones(n)


def highs(c, A, lo, hi, l, u, integ):
    return milp(c, constraints=LinearConstraint(A, lo, hi), integrality=integ,
                bounds=Bounds(l, u)).fun


@pytest.mark.parametrize("lp", ["ipm", "highs-ipm"])
@pytest.mark.parametrize("seed", range(6))
def test_zero_one_programs(seed, lp):
    c, A, lo, hi, l, u = knapsack(seed)
    integ = np.ones(len(c))
    r = bnb(c, A, lo, hi, l, u, integ, lp=lp)
    z = highs(c, A, lo, hi, l, u, integ)
    assert r["status"] == "optimal" and r["U"] == pytest.approx(z, abs=1e-6)
    L = [t[1] for t in r["trajectory"]]
    assert all(b >= a - 1e-9 for a, b in itertools.pairwise(L)) and max(L) <= z + 1e-6
    assert set(r["pruned"]) <= {"bound", "infeasible", "integral"}


def tree(p, **kw):
    M = rows(p)
    A = M["R"].constraint(len(M["c"]))

    def validate(v):
        rp = replay(p, routes_of(p, M, v))
        return rp["ok"], rp["length"]

    return bnb(M["c"], A.A, A.lb, A.ub, M["lb"], M["ub"], M["integ"], validate=validate, **kw)


@pytest.mark.parametrize("p", [TINY, rand_instance(1, n=4),
                               pytest.param(rand_instance(4, n=4), marks=pytest.mark.slow)],
                         ids=["tiny", "rand1", "rand4"])
def test_r1_through_the_tree(p):
    z = r1(p)["U"]
    for kw in ({"lp": "ipm"}, {"lp": "ipm", "delta": 1e-2}, {"lp": "highs-ipm"}):
        r = tree(p, **kw)
        assert r["status"] == "optimal" and r["U"] == pytest.approx(z, abs=1e-6), kw
        assert max(t[1] for t in r["trajectory"]) <= z + 1e-6


def test_early_stopped_nodes_give_valid_bounds():
    """Node LPs stopped at gap 1e-2: each such node's bound is below that node's exact LP value
    (a node's bound need not be below the global optimum)."""
    p = rand_instance(1, n=4)
    M = rows(p)
    A = M["R"].constraint(len(M["c"]))
    r = tree(p, lp="ipm", delta=1e-2)
    assert r["inexact"]
    D, hi, lo = A.A.toarray(), A.ub, A.lb
    Aub = np.vstack([D[np.isfinite(hi)], -D[np.isfinite(lo)]])
    bub = np.r_[hi[np.isfinite(hi)], -lo[np.isfinite(lo)]]
    for nd in r["inexact"]:
        z = linprog(M["c"], A_ub=Aub, b_ub=bub, bounds=list(zip(nd["l"], nd["u"])),
                    method="highs-ds")
        assert z.status == 0 and nd["L"] <= z.fun + 1e-7


def test_incumbent_needs_validation():
    """Every candidate refused: no incumbent, and the refused nodes keep their bounds."""
    c, A, lo, hi, l, u = knapsack(0)
    r = bnb(c, A, lo, hi, l, u, np.ones(len(c)), validate=lambda v: (False, None))
    assert r["U"] is None and r["rejected"] > 0
    assert r["status"] in ("validation_failed", "no_incumbent") and r["L"] is not None
    assert r["L"] <= highs(c, A, lo, hi, l, u, np.ones(len(c))) + 1e-6


def test_default_check_reads_the_rows():
    """Without a validator, a candidate is accepted only if it satisfies the original rows."""
    from methods.branch import primal
    A = np.array([[1.0, 1.0]])
    assert primal(np.array([1.0, 0.0]), A, np.array([1.0]), np.array([1.0]), np.zeros(2),
                  np.ones(2), np.array([0, 1]))
    assert not primal(np.array([1.0, 1.0]), A, np.array([1.0]), np.array([1.0]), np.zeros(2),
                      np.ones(2), np.array([0, 1]))
    assert not primal(np.array([0.5, 0.5]), A, np.array([1.0]), np.array([1.0]), np.zeros(2),
                      np.ones(2), np.array([0, 1]))
