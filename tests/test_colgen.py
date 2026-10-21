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
from models.colgen import arc_duals, beta, colgen, ng_sets, price
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


@pytest.mark.parametrize("seed", range(4))
def test_pricing_with_cut_duals_equals_brute_force(seed):
    """(R2.4)'s reduced cost c_r - pi'a_r - sum sigma_S beta_S(r): labeling against brute force."""
    p = rand_instance(seed, n=5)
    g = np.random.default_rng(seed)
    pi = np.zeros(len(p["X"]))
    pi[p["I"]] = g.uniform(0, 150, len(p["I"]))
    cuts = [(frozenset(g.choice(p["I"], 2 + k % 3, replace=False).tolist()), 1) for k in range(4)]
    sigma = g.uniform(0, 40, len(cuts))
    W = arc_duals(p, cuts, sigma)
    rc = lambda S, L: L - pi[list(S)].sum() - sum(
        s * beta(p, C, dict(visits=list(S))) for (C, _), s in zip(cuts, sigma))
    brute = min(rc(S, L) for S, L in all_routes(p))
    cb, _, exact = price(p, paths(p), pi, ng_sets(p, len(p["I"])), W=W)
    assert exact and cb == pytest.approx(brute, abs=1e-6)


@pytest.mark.parametrize("duals", ["ipm", "simplex"])
@pytest.mark.parametrize("seed, n", [(1, 8), (4, 6), (5, 6), (5, 8)])
def test_rcc_bound_is_valid_and_no_weaker(seed, n, duals):
    """z_LP(R2.1) <= L(R2-RCC) <= z*, and every cut holds at R1's optimal routes. On these four
    instances plain R2 leaves a gap; measured 2026-10-20, the cuts close it on all but (5, 6)."""
    p = rand_instance(seed, n=n)
    z = r1(p)
    a, b = colgen(p, duals="simplex"), colgen(p, duals=duals, rcc=True)
    assert b["converged"] and b["cuts"]
    assert a["L"] - 1e-6 * (1 + abs(a["L"])) <= b["L"] <= z["U"] + 1e-6
    opt = [dict(visits=[k - 1 for k in r if k - 1 in set(p["I"])]) for r in z["routes"]]
    for c in b["cuts"]:
        assert sum(beta(p, set(c["S"]), r) for r in opt) >= c["kappa"]
    if (seed, n) != (5, 6):
        assert b["L"] == pytest.approx(z["U"], rel=1e-6)


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


def test_status_is_optimal_only_when_the_gap_is_certified():
    """R2's LP can converge while the integer gap stays open; status must say which."""
    p = rand_instance(3, n=6)
    r = colgen(p, duals="simplex")
    assert r["converged"]
    assert (r["status"] == "optimal") == (r["U"] - r["L"] <= 1e-6 * (1 + abs(r["U"])))
