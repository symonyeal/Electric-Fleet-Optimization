# R2 (Routing §5): exact pricing against brute force, the column-generation bound against the
# full set-partitioning LP and against R1.

import itertools
import sys

import numpy as np
import pytest
from scipy.optimize import linprog

from checks.enum import route
from checks.route import replay
from data.evrp import load, read, sub
from models.colgen import colgen, ng_sets, price
from models.paths import paths
from models.route import r1

sys.path.insert(0, "tests")
from test_route_models import rand_instance

TINY = read("tests/fixtures/tiny.evrp")


def all_routes(p):
    """Every elementary route within capacity, at its least length (checks.enum)."""
    R = []
    for k in range(1, len(p["I"]) + 1):
        for S in itertools.permutations(p["I"], k):
            if p["b"][list(S)].sum() <= p["C"]:
                L, _ = route(p, S)
                if np.isfinite(L):
                    R.append((S, L))
    return R


def sp_lp(p):
    """The set-partitioning LP over all elementary routes, solved directly."""
    R = all_routes(p)
    A = np.array([[S.count(i) for S, _ in R] for i in p["I"]], float)
    return linprog([L for _, L in R], A_eq=A, b_eq=np.ones(len(p["I"])), method="highs-ds").fun


@pytest.mark.parametrize("seed", range(4))
def test_exact_pricing_equals_brute_force(seed):
    p = rand_instance(seed, n=5)
    pi = np.zeros(len(p["X"]))
    pi[p["I"]] = np.random.default_rng(seed).uniform(0, 150, len(p["I"]))
    brute = min(L - pi[list(S)].sum() for S, L in all_routes(p))
    cb, cols, exact = price(p, paths(p), pi, ng_sets(p, len(p["I"])))
    assert exact and cb == pytest.approx(brute, abs=1e-6)
    for col in cols:
        assert col["rc"] == pytest.approx(col["cost"] - pi[col["visits"]].sum(), abs=1e-9)
        assert col["cost"] == pytest.approx(route(p, col["visits"])[0], abs=1e-6) or (
            col["cost"] >= route(p, col["visits"])[0] - 1e-9)


@pytest.mark.parametrize("duals", ["ipm", "simplex"])
@pytest.mark.parametrize("p", [TINY, rand_instance(2, n=5), rand_instance(5, n=5)],
                         ids=["tiny", "rand2", "rand5"])
def test_bound_equals_the_full_set_partitioning_lp(p, duals):
    """Valid (L <= z_LP) and, at convergence, within the stopping tolerance eps (1 + |f|)."""
    r, z = colgen(p, duals=duals, nu=len(p["I"])), sp_lp(p)
    assert r["converged"] and r["L"] <= z + 1e-9 and z - r["L"] <= 1e-6 * (1 + abs(z))


@pytest.mark.parametrize("duals", ["ipm", "simplex"])
def test_bound_below_r1_at_every_iteration(duals):
    p = rand_instance(3, n=6)
    z = r1(p)["U"]
    r = colgen(p, duals=duals)
    assert all(t["L"] <= z + 1e-6 for t in r["trajectory"] if t["L"] is not None)
    assert r["U"] is not None and r["U"] >= z - 1e-6
    assert replay(p, r["routes"])["ok"]


@pytest.mark.data
def test_e_n22_k4_sub_instance():
    p = load("evrp-2019/E-n22-k4")
    q = sub(p, p["I"][:10], p["F"])
    z = r1(q)["U"]
    for duals in ("ipm", "simplex"):
        r = colgen(q, duals=duals)
        assert r["converged"] and r["L"] <= z + 1e-6 <= r["U"] + 2e-6
