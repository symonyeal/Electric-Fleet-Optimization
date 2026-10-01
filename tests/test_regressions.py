# The result-integrity regressions of the 2026-10-01 audit (Validation §2, "Defects"). Each test
# is numbered as in the audit's required list and was written to fail at 098642b.

import copy
import json
import math
import sys
import time

import numpy as np
import pytest

from checks.certificate import record
from checks.enum_transit import enum_m1
from checks.schedule import replay_energy
from methods.branch import bnb
from models.fleet import m1

sys.path.insert(0, "tests")
from test_fleet import tiny

KW = dict(solver=dict(code=0, message="test"), elapsed=0.0, provenance=dict(revision="t"))
FIX = {"A": dict(n=1, h=500.0)}


# 1, 2: the certificate is two-sided -------------------------------------------------------------

def test_01_lower_bound_above_upper_bound_is_not_certified():
    r = record("R1", "x", "optimal", U=100, L=100.5, **KW)
    assert r["gap_abs"] == pytest.approx(-0.5)
    assert r["certified"] is False and r["certificate_status"] == "invalid_bound"
    assert r["status"] == "invalid_bound" and r["solver_status"] == "optimal"
    assert not (r["certified"] and r["defect"])


def test_02_small_negative_gap_within_tolerance_is_consistent():
    """tol = 1e-6 + 1e-6 * 100 = 1.01e-4: a crossing of 1e-5 is numerical noise, certified and
    reported raw, without a defect; the same rule decides every stopping test."""
    from checks.certificate import gap_state
    r = record("R1", "x", "optimal", U=100.0, L=100.0 + 1e-5, **KW)
    assert r["certified"] is True and r["defect"] is None and r["status"] == "optimal"
    assert r["gap_abs"] == pytest.approx(-1e-5)                  # never clamped
    assert gap_state(100.0, 100.0 + 1e-5) == "closed"
    assert gap_state(100.0, 100.5) == "crossed"
    assert gap_state(100.0, 99.0) == "open"
    assert gap_state(None, 99.0) == "open"


def test_02b_outer_approximation_stops_on_a_crossed_bound():
    """A validator that under-reports U makes the master bound cross it: OA must not call that
    optimal, and the record built from it is invalid_bound."""
    from methods.oa import oa
    con = dict(idx=np.array([0, 1]), f=lambda z: (z[0] - 2.4) ** 2 - z[1],
               grad=lambda z: np.array([2 * (z[0] - 2.4), -1.0]))

    def sub(v):
        x = round(v[0])
        return "optimal", np.array([x, (x - 2.4) ** 2]), (x - 2.4) ** 2

    r = oa(np.array([0.0, 1.0]), np.zeros((0, 2)), np.zeros(0), np.zeros(0), np.zeros(2),
           np.array([5.0, 100.0]), np.array([1, 0]), [con], sub,
           validate=lambda w: (True, -1.0))                       # U = -1 < z* = 0.16 <= L
    assert r["status"] != "optimal"
    rec = record("OA", "x", r["status"], U=r["U"], L=r["L"], **KW)
    assert rec["status"] == "invalid_bound" and not rec["certified"]


# 3, 4: branch-and-bound -------------------------------------------------------------------------

COUNTER = ([1e8, 1.0], [[1e7, 1.0], [1.0, -2.0]], [1.0, -1.0], [np.inf, np.inf], [0.0, 0.0],
           [1.0, 1.0], [1, 1])


def test_03_hidden_fraction_cannot_certify_a_wrong_incumbent():
    """min 1e8 x1 + x2, 1e7 x1 + x2 >= 1, x1 - 2 x2 >= -1, x binary: the optimum is 1e8 at
    (1, 0). At 098642b the x2 = 0 branch's LP point x1 = 1e-7 was rounded to an infeasible 0
    and the node pruned as integral, so 1e8 + 1 at (1, 1) was certified."""
    r = bnb(*COUNTER, lp="highs-ipm", eps_abs=1e-9, eps_rel=1e-12)
    assert not (r["status"] == "optimal" and r["U"] == pytest.approx(1e8 + 1, abs=0.5))
    assert r["status"] == "optimal" and r["U"] == pytest.approx(1e8, abs=0.5)
    assert list(np.round(r["v"])) == [1.0, 0.0] and r["hidden"] >= 1


def test_04_rejected_integral_candidate_keeps_its_bound():
    """min -x1 - x2, x1 + x2 <= 2, x binary: the root LP point (1, 1) is exactly integral. If
    the independent check rejects it, the tree may not prune it away: its bound stays, and with
    no other candidate the result is validation_failed with L = -2."""
    r = bnb([-1.0, -1.0], [[1.0, 1.0]], [-np.inf], [2.0], [0.0, 0.0], [1.0, 1.0], [1, 1],
            lp="highs-ipm", validate=lambda v: (False, None))
    assert r["rejected"] >= 1 and r["U"] is None
    assert r["status"] == "validation_failed"
    assert r["L"] == pytest.approx(-2.0)


# 5, 6: base load L on the site meter ------------------------------------------------------------

def _site(v, **kw):
    v["sites"]["A"].update(kw)
    return v


def test_05_closed_candidate_site_with_base_load():
    """A site too dear to open, base load 10 kW within its grid capacity: closed, so neither the
    model nor the replay bills its load. At 098642b the model's peak rows charged it."""
    c, v = tiny(0)
    _site(v, L=10.0, G0=50.0)
    v["cost"]["site"] = 1e6
    r = m1(c, v)
    assert r["infra"] == {} and r["replay"]["ok"]
    assert r["objective"] == pytest.approx(r["U"], rel=1e-9, abs=1e-6)
    assert r["status"] == "optimal" and r["certified"]


def test_05b_base_load_above_capacity_at_a_closed_site():
    """L > G0 at a closed candidate site obliges nothing: the site stays closed. At 098642b the
    capacity rows forced it open (h >= L - G0 needs o = 1)."""
    c, v = tiny(0)
    _site(v, L=10.0, G0=0.0)
    v["cost"]["site"] = 1e6
    r = m1(c, v)
    assert r["infra"] == {} and r["objective"] < 1e6
    assert r["objective"] == pytest.approx(r["U"], rel=1e-9, abs=1e-6)


@pytest.mark.parametrize("seed", range(3))
def test_05c_open_site_with_in_window_charging(seed):
    c, v = tiny(seed)
    _site(v, L=10.0)
    z, _ = enum_m1(c, v, "A", 1, 500.0)
    r = m1(c, v, fixed=FIX)
    assert r["status"] == "optimal" and r["replay"]["ok"]
    assert r["U"] == pytest.approx(z, rel=1e-6, abs=1e-4)
    assert r["objective"] == pytest.approx(r["U"], rel=1e-6, abs=1e-4)


@pytest.mark.parametrize("seed", range(3))
def test_06_open_site_without_in_window_charging_pays_base_demand(seed):
    """Demand billed 00:00-01:00, when no slot can charge: the open site's meter still peaks at
    L. Model, enumeration and replay all bill 0.5 x 10 = 5."""
    c, v = tiny(seed)
    _site(v, L=10.0)
    v["cost"].update(peak_from=0.0, peak_to=1.0)
    z, _ = enum_m1(c, v, "A", 1, 500.0)
    r = m1(c, v, fixed=FIX)
    assert r["replay"]["parts"]["peak"] == pytest.approx(0.5 * 10.0)
    assert r["U"] == pytest.approx(z, rel=1e-6, abs=1e-4)
    assert r["objective"] == pytest.approx(r["U"], rel=1e-6, abs=1e-4)
    assert r["status"] == "optimal" and r["certified"]


def test_06b_m4_inherits_base_demand():
    from models.scenario import m4
    c, v = tiny(1)
    _site(v, L=10.0)
    v["cost"].update(peak_from=0.0, peak_to=1.0)
    r = m4(c, v, [(0.5, 1.2), (0.5, 1.3)], fixed=FIX)
    assert all(s["ok"] for s in r["scenarios"])
    assert r["objective"] == pytest.approx(r["U"], rel=1e-6, abs=1e-4)
    assert r["status"] == "optimal"


def test_06c_m2_inherits_base_demand():
    from models.charge import m2
    c, v = tiny(1)
    _site(v, L=10.0)
    v["cost"].update(peak_from=0.0, peak_to=1.0)
    r = m2(c, v, fixed={"A": dict(n=1, h=600.0)}, max_iter=30)
    assert r["status"] == "optimal" and r["certified"]


@pytest.mark.parametrize("q", [0.0, 100.0, 450.0])
def test_06d_m3_bills_base_demand(q):
    """M3's cost reconstruction adds the meter's base load: with no in-window charging, any
    command q costs exactly (1 + rider) x peak x L = 5 more at L = 10. (The reconstruction is
    tested directly: M3's local solves are nonconvex and may stop at their iteration limit.)"""
    from models.taper import setup, simulate
    fix = {"A": dict(n=1, h=600.0)}
    c, v = tiny(1)
    v["cost"].update(peak_from=0.0, peak_to=1.0)
    x = np.array(m1(c, v, fixed=fix, keep_x=True)["x"])
    w = _site(copy.deepcopy(v), L=10.0)
    S0, S1 = setup(c, v, x, fixed=fix), setup(c, w, x, fixed=fix)
    qv = np.full(len(S0["on"]), q)
    assert simulate(S1, w, qv)[1] - simulate(S0, v, qv)[1] == pytest.approx(5.0, abs=1e-9)


# 7: no revenue from terminal energy -------------------------------------------------------------

def _cheap_on_route(seed=0):
    """Short trips (2% of the pack), cheap terminal energy, dear depot energy, no demand charge:
    the price pattern under which a signed restoration term pays a bus to return full."""
    c, v = tiny(seed, n=3)
    for t in c["trips"]:
        t["km"] = 0.02 * 250 / 1.3
    v["cost"].update(F=0.0, deadhead=0.0, site=0.0, plug=0.0, upgrade=0.0, peak=0.0,
                     energy=0.01, depot_energy=1.0)
    return c, v


def test_07_terminal_energy_above_s0B_earns_nothing():
    c, v = _cheap_on_route()
    r = m1(c, v, fixed=FIX)
    assert r["replay"]["ok"] and r["replay"]["parts"]["depot_energy"] >= 0
    assert r["U"] >= 0 and r["objective"] >= -1e-6
    assert r["objective"] == pytest.approx(r["U"], rel=1e-6, abs=1e-6)
    z, _ = enum_m1(c, v, "A", 1, 500.0)
    assert r["U"] == pytest.approx(z, rel=1e-6, abs=1e-6)


def test_07b_replay_of_a_full_return_bills_no_credit():
    """A hand-made plan charges to smax before the trip, so the bus returns above s0 B; the
    restoration it is billed for is zero, not negative."""
    c, v = _cheap_on_route()
    t = c["trips"][0]
    c = dict(c, trips=[t])
    dl = v["time"]["delta"]
    s = int(t["dep"] // dl) - 1
    kw = (v["battery"]["smax"] - v["battery"]["s0"]) * v["battery"]["B"] / (dl / 3600)
    rp = replay_energy(c, v, [[t["id"]]], {t["id"]: {s: kw}}, {"A": dict(n=1, h=500.0)})
    end = rp["trace"][0][-1][1]
    assert end > v["battery"]["s0"] * v["battery"]["B"]
    assert rp["ok"] and rp["parts"]["depot_energy"] == 0.0


# 8: M4 weights ----------------------------------------------------------------------------------

@pytest.mark.parametrize("sc", [[(0.5, 1.2), (0.6, 1.3)], [(-0.5, 1.2), (1.5, 1.3)],
                                [(math.nan, 1.2), (1.0, 1.3)], [(math.inf, 1.2)], []])
def test_08_invalid_m4_weights_are_rejected_before_solving(sc, monkeypatch):
    import models.scenario as M
    monkeypatch.setattr(M, "join", lambda *a, **k: pytest.fail("rows built"))
    c, v = tiny(0)
    with pytest.raises(ValueError):
        M.m4(c, v, sc, fixed=FIX)


# 9: solver optimal, replay failed ---------------------------------------------------------------

def test_09_solver_optimal_with_failed_replay_is_not_optimal():
    r = record("M1", "x", "optimal", U=None, L=10.0, validation="validation_failed", **KW)
    assert r["status"] == "validation_failed" and not r["certified"]
    assert r["solver_status"] == "optimal" and r["validation_status"] == "validation_failed"


def test_09b_m1_with_a_rejected_schedule(monkeypatch):
    import models.fleet as F
    real = F.replay_energy
    monkeypatch.setattr(F, "replay_energy", lambda *a, **k: dict(
        real(*a, **k), ok=False, defects=[("energy", "forced")]))
    c, v = tiny(0)
    r = F.m1(c, v, fixed=FIX)
    assert r["solver_status"] == "optimal" and r["U"] is None
    assert r["status"] == "validation_failed" and not r["certified"]


def test_09c_objective_disagreeing_with_replay_is_not_optimal():
    r = record("M1", "x", "optimal", U=100.0, L=95.0, objective=95.0, **KW)
    assert r["validation_status"] == "validation_failed" and r["status"] != "optimal"
    assert "objective" in r["defect"]


# 10-13: bundles and run_bench -------------------------------------------------------------------

def _transit_case():
    from bench.cases import Case
    return Case("transit", "route100", "M0", 60.0, until=8.0)


def _bundle(case, tmp, **over):
    """A schema-current bundle for case, as run_case.py writes it, under the directory tmp."""
    from bench import schema
    from models.network import m0_record
    c, v, _ = schema.inputs(case)
    r = m0_record(c, v, name=schema.name(case))
    b = schema.bundle(r, case, command=["test"], code=dict(commit="0" * 40, dirty=False,
                                                         source=schema.source_digest()))
    b["bundle"].update(over)
    return b


def test_10_changed_scenario_invalidates_an_old_transit_bundle(tmp_path, monkeypatch):
    from bench import schema
    case = _transit_case()
    b = _bundle(case, tmp_path)
    assert schema.check(b, case) == []
    real = schema.inputs

    def changed(k, out=None):
        c, v, files = real(k, out)
        v = copy.deepcopy(v)
        v["battery"]["B"] = 300.0
        return c, v, files

    monkeypatch.setattr(schema, "inputs", changed)
    assert "scenario" in schema.check(b, case)


def test_11_dirty_or_incompatible_bundles_never_enter_a_verdict(tmp_path):
    from bench import schema
    case = _transit_case()
    dirty = _bundle(case, tmp_path)
    dirty["bundle"]["code"]["dirty"] = True
    assert "dirty" in schema.check(dirty, case)
    old = _bundle(case, tmp_path, formulation="M0/0")
    assert "formulation" in schema.check(old, case)
    bad = _bundle(case, tmp_path)
    bad.update(status="optimal", certified=False)
    assert "contract" in schema.check(bad, case)
    from bench.verdict import evrp
    v = evrp(573.13, lower=[], upper=[571.9])
    assert v["L"] is None and "certified" not in v["verdict"]


def test_12_failed_subprocess_fails_run_bench_and_keeps_reports(tmp_path, monkeypatch):
    import run_bench
    from bench import cases
    readme = tmp_path / "README.md"
    readme.write_text("<!-- results:begin -->\nold\n<!-- results:end -->\n", encoding="utf-8")
    monkeypatch.setattr(cases, "launch", lambda cmd: 1)              # every child fails
    with pytest.raises(SystemExit) as e:
        run_bench.main(["--run", "--only", "transit/route100/M0/until8"], out=tmp_path / "res",
                       readme=readme)
    assert e.value.code != 0
    assert readme.read_text(encoding="utf-8").endswith("old\n<!-- results:end -->\n")
    assert not (tmp_path / "res" / "README.md").exists()


def test_13_missing_reruns_invalid_or_stale_bundles(tmp_path):
    from bench import cases, schema
    case = _transit_case()
    out = tmp_path / "res"
    assert cases.missing([case], out) == [case]                     # no bundle
    p = cases.path(case, out)
    schema.write(p, _bundle(case, tmp_path))
    assert cases.missing([case], out) == []                         # valid
    stale = _bundle(case, tmp_path, formulation="M0/0")
    schema.write(p, stale)
    assert cases.missing([case], out) == [case]                     # stale
    p.write_text("{not json", encoding="utf-8")
    assert cases.missing([case], out) == [case]                     # unreadable


# 14: CLI pairs ----------------------------------------------------------------------------------

@pytest.mark.parametrize("argv", [["transit", "route100", "R1"], ["evrp", "E-n22-k4", "M1"],
                                  ["transit", "route100", "R2-ipm"], ["evrp", "E-n22-k4", "M0"]])
def test_14_invalid_track_model_pairs_fail_before_loading(argv, monkeypatch):
    import run_case
    monkeypatch.setattr(run_case, "load_evrp", lambda *a: pytest.fail("data loaded"))
    monkeypatch.setattr(run_case, "load_transit", lambda *a: pytest.fail("data loaded"))
    with pytest.raises(SystemExit) as e:
        run_case.main(argv)
    assert e.value.code != 0


# 15: one deadline for R2 ------------------------------------------------------------------------

def test_15_r2_time_budget_reaches_every_nested_call(monkeypatch):
    """Every master, pricing and restricted-MILP call receives at most the time left, and the
    run ends within its budget; the record keeps the requested and the actual time."""
    import models.colgen as G
    from data.evrp import read
    p = read("tests/fixtures/tiny.evrp")
    T, calls, t0 = 0.6, [], time.perf_counter()

    def spy(name, f):
        def g(*a, time_limit, **k):
            left = T - (time.perf_counter() - t0)
            calls.append((name, time_limit, left))
            time.sleep(max(0.0, min(0.15, time_limit)))           # a slow call that honors it
            return f(*a, time_limit=time_limit, **k)
        return g

    for nm in ("master", "price", "restricted_milp"):
        monkeypatch.setattr(G, nm, spy(nm, getattr(G, nm)))
    r = G.colgen(p, duals="simplex", time_limit=T)
    assert {n for n, _, _ in calls} >= {"master", "price"}
    assert all(lim <= left + 1e-3 for _, lim, left in calls)
    assert r["elapsed"] <= T + 0.25
    assert r["time_budget"]["requested"] == T
    assert r["provenance"]["params"]["time_limit"] == T


def test_json_roundtrip_of_a_record():
    """Records stay JSON-serializable with the new status fields."""
    r = record("R1", "x", "feasible_limit", U=2.0, L=1.0, **KW)
    assert json.loads(json.dumps(r))["certificate_status"] == "open"
