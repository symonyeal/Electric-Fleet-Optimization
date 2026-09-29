# Station graph and Pareto station paths (Routing §4).

import itertools
import math

import pytest

from data.evrp import load, read
from models.paths import paths, station_sp

P = read("tests/fixtures/tiny.evrp")   # depot 0 (0,0); customers 1-3; stations 4 (3,0), 5 (6,4)


def test_station_graph():
    S, _ = station_sp(P)
    assert S.tolist() == [[0, 5], [5, 0]]


def test_depot_to_customer_2_by_hand():
    """0 -> 2 direct: 10. Via 5: sqrt(52) + 4. Via 4, 5: 3 + 5 + 4. Via 4: 3 + sqrt(73).
    None of the three station paths dominates another in (l, a, omega); 0 -> 5 -> 4 -> 2 is
    dominated by 0 -> 4 -> 2."""
    got = sorted((round(l, 6), round(a, 6), round(w, 6), nodes)
                 for i, j, l, a, w, nodes in paths(P)[(0, 2)])
    r52, r73 = math.sqrt(52), math.sqrt(73)
    want = sorted([(10.0, 10.0, 10.0, (0, 2)),
                   (round(r52 + 4, 6), round(r52, 6), 4.0, (0, 5, 2)),
                   (12.0, 3.0, 4.0, (0, 4, 5, 2)),
                   (round(3 + r73, 6), 3.0, round(r73, 6), (0, 4, 2))])
    assert got == want


def test_no_path_from_depot_to_depot():
    assert (0, 0) not in paths(P)


@pytest.mark.data
def test_every_discarded_path_is_dominated():
    """Brute force: all (f, g) with a Floyd-Warshall recomputed here; every admissible candidate
    that paths() drops is dominated by one it keeps, and every kept one is admissible."""
    p = load("evrp-2019/E-n22-k4")
    D, h, Q, F, o, I = p["D"], p["h"], p["Q"], p["F"], p["depot"], p["I"]
    S = {(f, g): (0 if f == g else D[f, g] if h * D[f, g] <= Q else math.inf) for f in F for g in F}
    for k, f, g in itertools.product(F, F, F):
        S[f, g] = min(S[f, g], S[f, k] + S[k, g])
    Pp = paths(p)
    for i, j in itertools.product([o] + I, I + [o]):
        if i == j:
            continue
        kept = [(l, a, w) for _, _, l, a, w, nodes in Pp.get((i, j), []) if len(nodes) > 2]
        assert all(a <= Q + 1e-9 and w <= Q + 1e-9 for _, a, w in kept)
        for f, g in itertools.product(F, F):
            c = (D[i, f] + S[f, g] + D[g, j], h * D[i, f], h * D[g, j])
            if math.isfinite(c[0]) and c[1] <= Q and c[2] <= Q:
                assert any(all(k <= v + 1e-9 for k, v in zip(q, c)) for q in kept), (i, j, f, g)


@pytest.mark.data
def test_counts_e_n22_k4():
    n = {k: len(v) for k, v in paths(load("evrp-2019/E-n22-k4")).items()}
    assert len(n) <= 22 * 22 - 22 and min(n.values()) >= 1
    print("paths", sum(n.values()), "pairs", len(n))
