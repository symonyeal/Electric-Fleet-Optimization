"""M0: the battery-free fleet on the trip compatibility DAG (Models §2; Vanderbei Ch. 14-15;
BT Ch. 7; PS).

Trip j may follow trip i when arr_i + tau_ij + layover <= dep_j, tau_ij the deadhead time from
i's last stop to j's first. With x_ij = 1 when j immediately follows i,
    max sum x_ij   s.t.   sum_j x_ij <= 1,   sum_i x_ij <= 1,   x >= 0,
is a bipartite matching LP whose vertices are integral; time forbids cycles, so a matching is a
path cover and the least fleet is n minus the largest matching. The same number comes from the
min-cost flow with a unit cost on each pull-out, and from Hopcroft-Karp. An interior-point method
can stop inside a face of optimal solutions; its point is used for the value only, never rounded.
"""

import itertools

import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog
from scipy.sparse.csgraph import maximum_bipartite_matching

from methods.ipm import ipm, standard


def great_circle_km(a, b):
    p1, p2 = np.radians(a["lat"]), np.radians(b["lat"])
    h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(
        np.radians(b["lon"] - a["lon"]) / 2) ** 2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(h))


def compat(c, sc):
    """[(i, j, tau_ij)] over trip indices with arr_i + tau_ij + layover <= dep_j (seconds);
    tau = great-circle km x detour / speed. O(n^2)."""
    T, S = c["trips"], c["stops"]
    ends = {(t["last"], u["first"]) for t in T for u in T}
    tau = {(a, b): 3600 * great_circle_km(S[a], S[b]) * sc["detour"] / sc["speed"] for a, b in ends}
    return [(i, j, tau[t["last"], u["first"]]) for i, t in enumerate(T) for j, u in enumerate(T)
            if t["arr"] + tau[t["last"], u["first"]] + sc["layover"] <= u["dep"] + 1e-9]


def m0(c, sc):
    """Least battery-free fleet, three ways, with duties from a vertex and the agency's blocks.

    OUTPUT  fleet (matching LP by highs-ds), flow (min-cost flow), hopcroft_karp, ipm (largest
            matching by methods/ipm.py), ipm_fractional (entries of its point strictly inside
            (0, 1)), duties (trip ids), blocks, block_violations (agency connections our
            deadhead model does not allow), pairs.
    """
    T = c["trips"]
    n, P = len(T), compat(c, sc)
    m = len(P)
    I, J = np.array([p[0] for p in P], int), np.array([p[1] for p in P], int)
    A = sp.vstack([sp.csr_array((np.ones(m), (I, np.arange(m))), shape=(n, m)),
                   sp.csr_array((np.ones(m), (J, np.arange(m))), shape=(n, m))], format="csr")
    h = linprog(-np.ones(m), A_ub=A, b_ub=np.ones(2 * n), bounds=(0, 1), method="highs-ds")
    r = ipm(*standard(-np.ones(m), A, np.ones(2 * n), l=np.zeros(m), u=np.ones(m)))
    x = r["x"][:m]
    G = sp.csr_array((np.ones(m), (I, J)), shape=(n, n))
    hk = int((maximum_bipartite_matching(G, perm_type="column") >= 0).sum())
    F = sp.hstack([sp.eye_array(n), sp.csr_array((n, n)),                  # into i: s_i + x_hi
                   sp.csr_array((np.ones(m), (J, np.arange(m))), shape=(n, m))])
    G2 = sp.hstack([sp.csr_array((n, n)), sp.eye_array(n),                 # out of i: t_i + x_ij
                    sp.csr_array((np.ones(m), (I, np.arange(m))), shape=(n, m))])
    fl = linprog(np.r_[np.ones(n), np.zeros(n + m)], A_eq=sp.vstack([F, G2]),
                 b_eq=np.ones(2 * n), bounds=(0, 1), method="highs-ds")
    succ = {I[k]: J[k] for k in np.flatnonzero(h.x > 0.5)}
    heads = set(range(n)) - set(succ.values())
    duties = []
    for s in sorted(heads, key=lambda i: T[i]["dep"]):
        d = [s]
        while d[-1] in succ:
            d.append(succ[d[-1]])
        duties.append([T[i]["id"] for i in d])
    blocks = {}
    for i in sorted(range(n), key=lambda i: T[i]["dep"]):
        blocks.setdefault(T[i]["block"], []).append(i)
    ok = {(i, j) for i, j, _ in P}
    viol = sum((a, b) not in ok for B in blocks.values() for a, b in itertools.pairwise(B))
    return dict(fleet=n - round(-h.fun), flow=round(fl.fun), hopcroft_karp=n - hk,
                ipm=-r["f"], ipm_status=r["status"],
                ipm_fractional=int(((x > 1e-6) & (x < 1 - 1e-6)).sum()),
                duties=duties, blocks=len(blocks), block_violations=viol, pairs=m)
