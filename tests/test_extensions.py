# M3 (Models §6) and M4 (Models §7): local solutions under the integrated taper law, and one
# fleet for several energy scenarios.

import sys

import numpy as np
import pytest

from models.fleet import m1
from models.scenario import m4, scen
from models.taper import integrate, law, m3_fixed

sys.path.insert(0, "tests")
from test_fleet import tiny

FIX = {"A": dict(n=1, h=600.0)}


@pytest.mark.parametrize("e0,q", [(50.0, 450.0), (200.0, 100.0), (0.0, 300.0)])
def test_closed_form_matches_integration(e0, q):
    """(14) against (13) integrated numerically over one 5-minute slot."""
    assert law(e0, q, 300 / 3600, 250.0) == pytest.approx(integrate(e0, q, 300 / 3600, 250.0),
                                                          abs=1e-9)


@pytest.mark.slow
@pytest.mark.parametrize("seed", range(3))
def test_m3_local_solutions_and_optimistic_bound(seed):
    c, v = tiny(seed)
    r1_ = m1(c, v, fixed=FIX, keep_x=True)
    r = m3_fixed(c, v, np.array(r1_["x"]), fixed=FIX, starts=4, seed=seed)
    assert r["status"] == "local" and r["best"] >= r["optimistic"] - 1e-6
    assert r["integration_error"] < 1e-8
    assert len(r["solutions"]) == 4


SC = [(0.25, 1.2), (0.5, 1.3), (0.25, 1.4)]


@pytest.mark.parametrize("seed", range(3))
def test_m4_against_wait_and_see(seed):
    """Expected cost is at least the weighted scenario optima (wait-and-see); worst case at least
    the largest; every scenario's plan replays with its own consumption."""
    c, v = tiny(seed)
    ws = [m1(c, scen(v, k), fixed=FIX)["U"] for _, k in SC]
    e, w = m4(c, v, SC, fixed=FIX), m4(c, v, SC, fixed=FIX, worst=True)
    assert e["status"] == "optimal" and w["status"] == "optimal"
    assert all(s["ok"] for s in e["scenarios"] + w["scenarios"])
    assert e["U"] >= np.dot([p for p, _ in SC], ws) - 1e-6
    assert w["U"] >= max(ws) - 1e-6 and w["U"] >= e["U"] - 1e-6
    assert len({s["fleet"] for s in e["scenarios"]}) == 1
