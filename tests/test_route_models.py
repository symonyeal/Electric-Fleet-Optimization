# R0, R1 and R1-TR (Routing §2-§4) against exhaustive enumeration and the independent replay.

import numpy as np
import pytest

from checks.enum import enum
from checks.route import replay
from data.evrp import dist, load, read, sub
from models.route import r0, r1, r1tr

TINY = read("tests/fixtures/tiny.evrp")


def rand_instance(seed, n=5, m=3):
    """Self-made: depot at the center of [0,100]^2, n customers, m stations. The battery lets
    every customer be served by 0 -> i -> (nearest station or depot) -> 0, so the instance is
    feasible, but is short of most out-and-back trips, so stations get used."""
    g = np.random.default_rng(seed)
    X = np.vstack([[50, 50], g.uniform(0, 100, (n + m, 2))])
    D = dist(X)
    I, F = list(range(1, n + 1)), list(range(n + 1, n + m + 1))
    Q = 1.01 * max(max(D[0, i] + min(D[i, [0, *F]]) for i in I), D[0, F].max())
    return dict(name=f"rand{seed}", NAME="", X=X, D=D, depot=0, I=I, F=F,
                b=np.r_[0, g.integers(1, 5, n), np.zeros(m)], C=8.0, Q=Q, h=1.0, K=1, opt=None)


def check(p, r):
    """U is the replayed length; the bound is below it."""
    rp = replay(p, r["routes"])
    assert rp["ok"], rp["defects"]
    assert r["U"] == pytest.approx(rp["length"], abs=1e-6) and r["L"] <= r["U"] + 1e-6


def test_tiny():
    z, routes = enum(TINY)
    a, b, c = r1(TINY), r1tr(TINY), r0(TINY)
    assert a["status"] == b["status"] == "optimal"
    assert a["U"] == pytest.approx(z, abs=1e-6) and b["U"] == pytest.approx(z, abs=1e-6)
    assert c["U"] <= a["U"] + 1e-9
    check(TINY, a)
    assert replay(TINY, routes)["length"] == pytest.approx(z, abs=1e-9)


@pytest.mark.parametrize("seed", range(8))
def test_random_instances(seed):
    p = rand_instance(seed)
    z, _ = enum(p)
    a = r1(p)
    assert a["status"] == "optimal" and a["U"] == pytest.approx(z, abs=1e-6)
    check(p, a)
    assert r0(p)["U"] <= a["U"] + 1e-9
    if seed < 4:
        q = sub(p, p["I"][:4], p["F"])
        assert r1tr(q)["U"] == pytest.approx(r1(q)["U"], abs=1e-6)


def test_stations_are_used():
    """The generator is only a test of charging if optimal routes visit stations."""
    used = [any(k - 1 in p["F"] for r in enum(p)[1] for k in r)
            for p in map(rand_instance, range(8))]
    assert sum(used) >= 5


def test_infeasible():
    p = rand_instance(0)
    p = dict(p, Q=0.9 * p["D"][0, p["I"]].max())
    assert enum(p)[0] == np.inf and r1(p)["status"] == "infeasible"


@pytest.mark.data
@pytest.mark.parametrize("k", range(3))
def test_e_n22_k4_sub_instances(k):
    """Five customers farthest from the depot, in three rotations, with all eight stations."""
    p = load("evrp-2019/E-n22-k4")
    far = sorted(p["I"], key=lambda i: -p["D"][p["depot"], i])
    q = sub(p, far[k:k + 5], p["F"])
    z, _ = enum(q)
    a = r1(q)
    assert a["U"] == pytest.approx(z, abs=1e-6)
    check(q, a)
    t = sub(p, far[k:k + 3], p["F"][:4])
    assert r1tr(t)["U"] == pytest.approx(r1(t)["U"], abs=1e-6)
    assert r1(t)["U"] == pytest.approx(enum(t)[0], abs=1e-6)
