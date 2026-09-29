# M1 (Models §3, connection form): exhaustive enumeration on tiny timetables, the energy replay,
# the Route 100 morning, its LP relaxation by the textbook IPM, and the educational tree.

import copy
import itertools
import json

import numpy as np
import pytest

from checks.enum_transit import enum_m1
from checks.schedule import replay_energy
from data.scenario import load
from methods.branch import bnb, split
from methods.ipm import ipm, standard
from models.fleet import m1, priority, rows
from models.network import m0

V, _ = load("data/scenarios/route100.toml")
with open("tests/fixtures/route100.json", encoding="utf-8") as f:
    R100 = json.load(f)


def tiny(seed, n=5):
    """n trips from and to one stop 'a', the only site and the depot. Each trip uses 40% of the
    battery; a bus starting at 90% with a 20% reserve needs a charge before a second trip."""
    g = np.random.default_rng(seed)
    dep = np.sort(g.integers(0, 12, n)) * 1200 + 21600
    T = [dict(id=f"t{k}", first="a", last="a", dep=int(d), arr=int(d) + 1500,
              km=0.4 * 250 / 1.3, block="b") for k, d in enumerate(dep)]
    v = copy.deepcopy(V)
    v["sites"] = {"A": dict(V["sites"]["marpole"], stops=["a"], nbar=2.0)}
    v["depot"] = dict(lat=49.2, lon=-123.1)
    return dict(trips=T, stops={"a": dict(name="a", lat=49.2, lon=-123.1)}), v


@pytest.mark.parametrize("seed", range(6))
def test_tiny_equals_enumeration(seed):
    c, v = tiny(seed)
    z, _ = enum_m1(c, v, "A", 1, 500.0)
    r = m1(c, v, fixed={"A": dict(n=1, h=500.0)})
    assert np.isfinite(z) and r["status"] == "optimal"
    assert r["U"] == pytest.approx(z, rel=1e-6, abs=1e-4)
    assert r["replay"]["ok"] and r["objective"] == pytest.approx(r["U"], rel=1e-6, abs=1e-4)


RS1640 = dict(rider=-0.015, basic=0.2999)          # BC Hydro RS 1640 riders and basic charge


def test_absent_tariff_keys_leave_m1_unchanged():
    """Data §3: a scenario without tariff keys gives the rows and costs it gave before them."""
    c, v = tiny(2)
    w = copy.deepcopy(v)
    w["cost"].update(rider=0.0, basic=0.0, peak_from=0.0, peak_to=24.0)
    M, N = rows(c, v), rows(c, w)
    assert np.array_equal(M["c"], N["c"])
    a, b = M["R"].constraint(len(M["c"])), N["R"].constraint(len(N["c"]))
    assert (a.A != b.A).nnz == 0 and np.array_equal(a.lb, b.lb) and np.array_equal(a.ub, b.ub)


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("w", [(6.0, 22.0), (7.5, 22.0)])
def test_tiny_with_tariff_equals_enumeration(seed, w):
    """Riders, a basic charge and demand billed only inside a window: M1's rows, the
    enumeration's own MILP and the replay each price them, and agree. The 07:30 window cuts
    through the tiny instances' charging slots."""
    c, v = tiny(seed)
    v["cost"].update(RS1640, peak_from=w[0], peak_to=w[1])
    z, _ = enum_m1(c, v, "A", 1, 500.0)
    r = m1(c, v, fixed={"A": dict(n=1, h=500.0)})
    assert np.isfinite(z) and r["status"] == "optimal" and r["replay"]["ok"]
    assert r["U"] == pytest.approx(z, rel=1e-6, abs=1e-4)
    assert r["objective"] == pytest.approx(r["U"], rel=1e-6, abs=1e-4)


def test_billing_window_moves_charging_out_of_it():
    """The window binds: billed from 07:30, seed 1 charges earlier and its demand charge falls
    from 60.22 to 13.38 (measured 2026-09-29), lowering the optimum."""
    c, v = tiny(1)
    v["cost"].update(RS1640)
    a = m1(c, v, fixed={"A": dict(n=1, h=500.0)})
    v["cost"].update(peak_from=7.5, peak_to=22.0)
    b = m1(c, v, fixed={"A": dict(n=1, h=500.0)})
    assert b["replay"]["parts"]["peak"] < a["replay"]["parts"]["peak"] - 40
    assert b["U"] < a["U"] - 40


def test_riders_and_basic_charge_by_hand():
    """The replay's bill with a -1.5% rider and a basic charge, from the bill without them."""
    c, v = tiny(1)
    r = m1(c, v, fixed={"A": dict(n=1, h=500.0)})
    a = replay_energy(c, v, r["duties"], r["plan"], r["infra"])
    w = copy.deepcopy(v)
    w["cost"].update(RS1640)
    b = replay_energy(c, w, r["duties"], r["plan"], r["infra"])
    for k in ("energy", "depot_energy", "peak"):
        assert b["parts"][k] == pytest.approx(0.985 * a["parts"][k])
    assert b["parts"]["basic"] == pytest.approx(0.985 * 0.2999 * len(r["infra"]))
    e = a["parts"]["energy"] + a["parts"]["depot_energy"] + a["parts"]["peak"]
    assert b["cost"] - a["cost"] == pytest.approx(-0.015 * e + b["parts"]["basic"])


def test_billing_window_without_charging_bills_no_demand():
    """Demand counts only in its window: after the last charging slot it is zero."""
    c, v = tiny(1)
    r = m1(c, v, fixed={"A": dict(n=1, h=500.0)})
    last = max(s for d in r["plan"].values() for s in d)
    w = copy.deepcopy(v)
    w["cost"].update(peak_from=(last + 1) * v["time"]["delta"] / 3600, peak_to=24.0)
    a = replay_energy(c, v, r["duties"], r["plan"], r["infra"])
    b = replay_energy(c, w, r["duties"], r["plan"], r["infra"])
    assert a["parts"]["peak"] > 0 and b["parts"]["peak"] == 0.0
    assert b["cost"] == pytest.approx(a["cost"] - a["parts"]["peak"])


def test_charging_is_needed_in_the_tiny_instances():
    used = [bool(m1(*tiny(s), fixed={"A": dict(n=1, h=500.0)})["plan"]) for s in range(6)]
    assert sum(used) >= 3


def test_replay_finds_missing_charge():
    c, v = tiny(0)
    r = m1(c, v, fixed={"A": dict(n=1, h=500.0)})
    long = [d for d in r["duties"] if len(d) > 1]
    if not long:
        pytest.skip("no bus serves two trips in this instance")
    plan = {k: s for k, s in r["plan"].items() if k not in long[0][1:]}
    rp = replay_energy(c, v, r["duties"], plan, r["infra"])
    assert not rp["ok"] and any(k == "energy" for k, _ in rp["defects"])


def test_replay_traces_energy_and_site_power():
    """The traces drawn in the results are the replay's, not the solver's."""
    c, v = tiny(1)
    r = m1(c, v, fixed={"A": dict(n=1, h=500.0)})
    rp = replay_energy(c, v, r["duties"], r["plan"], r["infra"])
    b = v["battery"]
    assert len(rp["trace"]) == r["fleet"]
    for tr in rp["trace"]:
        assert tr[0][1] == pytest.approx(b["s0"] * b["B"])
        assert min(e for _, e in tr) >= b["reserve"] * b["B"] - 1e-6
        assert all(s <= t for (s, _), (t, _) in itertools.pairwise(tr))
    kw = sum(k for d in r["plan"].values() for k in d.values())
    assert sum(g for _, g in rp["load"].values()) == pytest.approx(kw / v["charger"]["eta"])


def morning(until=8 * 3600):
    return dict(R100, trips=[t for t in R100["trips"] if t["dep"] < until])


@pytest.mark.slow
def test_route100_morning():
    c = morning()
    r = m1(c, V, name="route100-morning", time_limit=120)
    assert r["U"] is not None and r["replay"]["ok"] and r["L"] <= r["U"] + 1e-6
    sc = dict(speed=V["deadhead"]["speed"], detour=V["deadhead"]["detour"],
              layover=V["time"]["layover"])
    assert r["fleet"] >= m0(c, sc)["fleet"]


@pytest.mark.slow
def test_lp_relaxation_by_the_ipm():
    """The M1 relaxation, solved by methods/ipm.py and by highs-ds, is below the MILP."""
    from scipy.optimize import linprog
    c = morning(7 * 3600)
    M = rows(c, V)
    A = M["R"].constraint(len(M["c"]))
    Aub, bub, Aeq, beq = split(A.A, A.lb, A.ub)
    r = ipm(*standard(M["c"], Aub, bub, Aeq, beq, M["lb"], M["ub"]))
    h = linprog(M["c"], A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq,
                bounds=list(zip(M["lb"], M["ub"])), method="highs-ds")
    assert r["status"] == "optimal" and r["f"] == pytest.approx(h.fun, rel=1e-6)
    assert r["L"] <= m1(c, V, time_limit=120)["U"] + 1e-6


@pytest.mark.parametrize("n", [4, 5])
def test_tree_on_tiny_m1(n):
    """TRN-10: with scheduling-first priority the educational tree certifies HiGHS's optimum."""
    c, v = tiny(1, n=n)
    M = rows(c, v, fixed={"A": dict(n=1, h=500.0)})
    A = M["R"].constraint(len(M["c"]))
    r = bnb(M["c"], A.A, A.lb, A.ub, M["lb"], M["ub"], M["integ"], priority=priority(M))
    z = m1(c, v, fixed={"A": dict(n=1, h=500.0)})["objective"]
    assert r["status"] == "optimal" and r["U"] == pytest.approx(z, rel=1e-6, abs=1e-4)
    assert r["nodes"] < 1000
