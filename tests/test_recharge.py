# R3 (Routing §6): with free, instantaneous charging it is R1 restricted to one station between
# customers; under the declared scenario it is bracketed by R3-P and its routes replay.

import copy
import itertools
import sys

import numpy as np
import pytest

from checks.route import replay_charge
from data.evrp import read
from data.scenario import load
from models.recharge import fixed, r3, r3p, rows
from models.route import r1

sys.path.insert(0, "tests")
from test_route_models import rand_instance

SC, _ = load("data/scenarios/r3.toml")
TINY = read("tests/fixtures/tiny.evrp")


def free(sc):
    """Charging costs nothing and takes (almost) no time: R3 = R1 with at most one station
    between customers."""
    s = copy.deepcopy(sc)
    s["charger"].update(alpha=0.0, P=1e4)            # a full charge in under 0.01 h
    s["cost"].update(energy=0.0, dwell=0.0)
    s["time"].update(T=100.0, tau_min=1e-3, service=0.0)
    return s


def at_most_one_station(p, routes):
    F = {f + 1 for f in p["F"]}
    return all(not (a in F and b in F) for r in routes for a, b in itertools.pairwise(r))


@pytest.mark.parametrize("p", [TINY, rand_instance(1, n=4), rand_instance(4, n=4)],
                         ids=["tiny", "rand1", "rand4"])
def test_free_charging_is_r1_with_one_station(p):
    a, b = r3(p, free(SC), max_iter=40), r1(p)
    assert a["status"] == "optimal" and b["status"] == "optimal"
    assert a["U"] >= b["U"] - 1e-6
    if at_most_one_station(p, b["routes"]):
        assert a["U"] == pytest.approx(b["U"], abs=1e-5)


@pytest.mark.parametrize("p", [TINY, rand_instance(1, n=4)], ids=["tiny", "rand1"])
def test_scenario_bracket_and_replay(p):
    r = r3(p, SC, max_iter=40)
    br = r3p(p, SC, J=8)
    assert r["status"] == "optimal", r["iterations"][-3:]
    assert br["lower"] <= r["L"] + 1e-6 <= r["U"] + 2e-6 <= br["upper"] + 3e-6
    assert replay_charge(p, SC, r["routes"], {tuple(map(int, k.split(":"))): v
                                              for k, v in r["charges"].items()})["ok"]
    L = [it["L"] for it in r["iterations"]]
    assert all(y >= x - 1e-6 for x, y in itertools.pairwise(L))


def test_fixed_routes_bound():
    """At the optimal routes the barrier's bound (A5) is below its value and within tolerance."""
    M = rows(TINY, SC)
    r = r3(TINY, SC, max_iter=40, keep_x=True)
    st, _, f, L = fixed(TINY, M, np.array(r["x"]))
    assert st == "optimal" and L <= f + 1e-7 and f - L <= 1e-6 * (1 + abs(f))
    assert f == pytest.approx(r["U"], rel=1e-6)
