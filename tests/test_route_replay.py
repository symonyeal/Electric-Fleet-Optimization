# Independent route replay (Routing §1, §9) on the self-made fixture tiny.evrp:
# depot 1 at (0,0); customers 2 (3,4), 3 (6,8), 4 (0,5) with demands 4, 3, 5;
# stations 5 (3,0), 6 (6,4); C = Q = 10, h = 1.

import pytest

from checks.route import from_evrp_python, read_routes, replay, write_routes
from data.evrp import read

P = read("tests/fixtures/tiny.evrp")
A = [1, 2, 6, 3, 6, 1]          # 5 + 3 + 4 + 4 + sqrt(52); needs both recharges at 6
B = [1, 4, 1]                   # 5 + 5, arrives with an empty battery


def kinds(r):
    return sorted({k for k, _ in r["defects"]})


def test_valid():
    r = replay(P, [A, B])
    assert r["ok"] and r["defects"] == [] and r["routes"] == 2
    assert r["length"] == pytest.approx(26 + 52**0.5)
    assert r["load"] == [7, 5] and r["low"] == pytest.approx([2, 0])


def test_depot_visit_splits_a_route():
    r = replay(P, [A + B[1:]])
    assert r["ok"] and r["routes"] == 2 and r["length"] == pytest.approx(26 + 52**0.5)


def test_missing():
    assert kinds(replay(P, [A])) == ["missing"]


def test_repeat():
    assert kinds(replay(P, [A, B, [1, 2, 1]])) == ["repeat"]


def test_overload():
    q = dict(P, Q=100.0)
    assert kinds(replay(q, [[1, 2, 3, 4, 1]])) == ["overload"]


def test_battery_on_the_depot_leg():
    """1 -> 3 spends all 10; the return leg 3 -> 1 is where the battery runs out."""
    r = replay(P, [[1, 3, 1], [1, 2, 1], B])
    assert kinds(r) == ["battery"] and "3->1" in r["defects"][0][1]


def test_without_recharge_the_route_fails():
    assert kinds(replay(P, [[1, 2, 3, 1], B])) == ["battery"]


def test_endpoint_and_unknown_node():
    assert kinds(replay(P, [A[1:], B])) == ["endpoint"]
    assert "unknown_node" in kinds(replay(P, [A, B, [1, 9, 1]]))


def test_route_file_round_trip(tmp_path):
    f = tmp_path / "s.routes"
    write_routes(f, [A, B])
    assert read_routes(f) == [A, B]


def test_evrp_python_tours():
    """GSGA prints 0-based tours with the depot at both ends; a missing end is closed."""
    s = "Tour length: 33.2\nTour 0: 0 -> 1 -> 5 -> 2 -> 5 -> 0\nTour 1: 3\n"
    assert from_evrp_python(s, depot=0) == [A, B]
    assert replay(P, from_evrp_python(s, depot=0))["ok"]
