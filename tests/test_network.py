# M0 (Models §2): matching LP, min-cost flow and a combinatorial matching, against Dilworth's
# theorem on single-terminal timetables and against the agency's blocks.

import json

import numpy as np
import pytest

from checks.schedule import replay
from models.network import compat, m0

with open("tests/fixtures/route100.json", encoding="utf-8") as f:
    R100 = json.load(f)


def synthetic(seed, n=30):
    """n trips from and to one stop: with zero deadhead and layover the least fleet is the
    greatest number of trips in service at once (Dilworth's theorem on interval orders)."""
    g = np.random.default_rng(seed)
    dep = np.sort(g.integers(0, 20000, n))
    arr = dep + g.integers(600, 5000, n)
    T = [dict(id=str(k), first="s", last="s", dep=int(d), arr=int(a), km=10.0, block=str(k))
         for k, (d, a) in enumerate(zip(dep, arr))]
    overlap = max(sum(t["dep"] <= s < t["arr"] for t in T) for s in dep)
    return dict(trips=T, stops={"s": dict(name="s", lat=49.2, lon=-123.1)}), overlap


SC0 = dict(speed=25.0, detour=1.3, layover=0.0)


@pytest.mark.parametrize("seed", range(10))
def test_dilworth(seed):
    c, w = synthetic(seed)
    r = m0(c, SC0)
    assert r["fleet"] == r["flow"] == r["hopcroft_karp"] == w
    assert r["ipm"] == pytest.approx(len(c["trips"]) - w, abs=1e-6)
    assert replay(c, r["duties"], SC0)["ok"]


def test_ipm_stays_inside_a_face_and_is_not_rounded():
    """Two trips ending before two others start: two optimal matchings; the interior-point
    solution is their midpoint, and duties come from the vertex, not from it."""
    T = [dict(id=k, first="s", last="s", dep=d, arr=a, km=1.0, block=k)
         for k, d, a in (("a", 0, 10), ("b", 0, 10), ("c", 20, 30), ("d", 20, 30))]
    c = dict(trips=T, stops={"s": dict(name="s", lat=0.0, lon=0.0)})
    r = m0(c, SC0)
    assert r["fleet"] == 2 and r["ipm_fractional"] == 4
    assert sorted(len(d) for d in r["duties"]) == [2, 2] and replay(c, r["duties"], SC0)["ok"]


def test_route_100():
    sc = dict(speed=25.0, detour=1.3, layover=300.0)
    r = m0(R100, sc)
    assert r["fleet"] == r["flow"] == r["hopcroft_karp"]
    assert replay(R100, r["duties"], sc)["ok"]
    assert r["blocks"] == 23
    if r["block_violations"] == 0:
        assert r["fleet"] <= r["blocks"]
    print("route 100 fleet", r["fleet"], "blocks", r["blocks"], "violations", r["block_violations"])


def test_compatibility_uses_deadhead_and_layover():
    c = R100
    P = compat(c, dict(speed=25.0, detour=1.3, layover=300.0))
    T = c["trips"]
    for i, j, tau in P[:200]:
        assert T[i]["arr"] + tau + 300.0 <= T[j]["dep"]
