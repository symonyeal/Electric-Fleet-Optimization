# Outer approximation (Algorithms §6) on a convex MINLP with a known optimum, and M2 against its
# M2-P bracket and against M1 (Models §4-§5).

import itertools
import sys

import numpy as np
import pytest

from methods.oa import oa
from models.charge import m2, m2p
from models.fleet import m1

sys.path.insert(0, "tests")
from test_fleet import tiny

FIX = {"A": dict(n=1, h=600.0)}


def test_known_optimum():
    """min t s.t. (x - 2.4)^2 <= t, x in {0, ..., 5}: x* = 2, t* = 0.16."""
    con = dict(idx=np.array([0, 1]), f=lambda z: (z[0] - 2.4) ** 2 - z[1],
               grad=lambda z: np.array([2 * (z[0] - 2.4), -1.0]))

    def sub(v):
        x = round(v[0])
        return "optimal", np.array([x, (x - 2.4) ** 2]), (x - 2.4) ** 2

    r = oa(np.array([0.0, 1.0]), np.zeros((0, 2)), np.zeros(0), np.zeros(0),
           np.zeros(2), np.array([5.0, 100.0]), np.array([1, 0]), [con], sub)
    assert r["status"] == "optimal" and r["U"] == pytest.approx(0.16) and r["v"][0] == 2
    L = [it["L"] for it in r["iterations"]]
    assert all(b >= a - 1e-9 for a, b in itertools.pairwise(L)) and L[-1] <= 0.16 + 1e-9


@pytest.mark.parametrize("seed", range(3))
def test_m2_bracket_and_order(seed):
    c, v = tiny(seed)
    r = m2(c, v, fixed=FIX, max_iter=30)
    b = m2p(c, v, J=8, fixed=FIX)
    z1 = m1(c, dict(v, charger=dict(v["charger"], gamma=0.0)), fixed=FIX)["U"]
    assert r["status"] == "optimal", r["iterations"][-3:]
    assert b["lower"] <= r["L"] + 1e-6 and r["L"] <= r["U"] + 1e-6
    assert r["U"] <= b["upper"] + 1e-6
    assert r["U"] >= z1 - 1e-6                        # losses and taper only add cost
    L = [it["L"] for it in r["iterations"]]
    assert all(b2 >= a - 1e-6 for a, b2 in itertools.pairwise(L))
