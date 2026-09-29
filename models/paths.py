"""Station graph and Pareto station paths (Routing §4).

A segment from i to j is p = (i, f_1, ..., f_k, j), k >= 0, f_t stations. It has length l_p,
first-leg energy a_p = e_{i f_1} and last-leg energy w_p = e_{f_k j} (both e_ij when k = 0).
For k >= 1 the vehicle reaches j with Q - w_p whatever its charge at i, provided that charge is
at least a_p; hence among k >= 1 only the Pareto-minimal (l, a, w) matter, and for fixed first
and last stations f, g the interior is a shortest path SP(f, g) of the station graph.
"""

import numpy as np


def station_sp(p, tol=1e-9):
    """Floyd-Warshall on stations over legs consuming at most Q. O(|F|^3).

    OUTPUT  S ..... |F| x |F| shortest lengths (inf when unreachable)
            nxt ... successor on a shortest path, for recovery
    """
    F, Q = p["F"], p["Q"]
    Dff = p["D"][np.ix_(F, F)]
    S = np.where(p["h"] * Dff <= Q + tol, Dff, np.inf)
    np.fill_diagonal(S, 0.0)
    m = len(F)
    nxt = np.tile(np.arange(m), (m, 1))
    for k in range(m):
        T = S[:, [k]] + S[[k], :]
        better = T < S
        S = np.where(better, T, S)
        nxt = np.where(better, nxt[:, [k]], nxt)
    return S, nxt


def _walk(nxt, f, g):
    v = [f]
    while v[-1] != g:
        v.append(nxt[v[-1], g])
    return v


def paths(p, tol=1e-9):
    """P[(i, j)] = [(i, j, l, a, w, nodes)], sources {0} ∪ I, sinks I ∪ {0'}, no (0, 0').

    The direct arc is kept when e_ij <= Q; station paths when a, w <= Q, then Pareto-filtered.
    Candidates per pair: |F|^2, so O(n^2 |F|^2) in all.
    """
    D, h, Q, F, o, I = p["D"], p["h"], p["Q"], p["F"], p["depot"], p["I"]
    S, nxt = station_sp(p, tol)
    F = np.asarray(F)
    P = {}
    for i in [o] + I:
        for j in I + [o]:
            if i == j:
                continue
            e = h * D[i, j]
            out = [(i, j, D[i, j], e, e, (i, j))] if e <= Q + tol else []
            l = D[i, F][:, None] + S + D[F, j][None, :]
            a = np.broadcast_to(h * D[i, F][:, None], l.shape)
            w = np.broadcast_to(h * D[F, j][None, :], l.shape)
            ok = np.isfinite(l) & (a <= Q + tol) & (w <= Q + tol)
            kept = []
            for f, g in sorted(zip(*np.nonzero(ok)), key=lambda fg: (l[fg], a[fg], w[fg])):
                c = (l[f, g], a[f, g], w[f, g])
                if not any(q[0] <= c[0] + tol and q[1] <= c[1] + tol and q[2] <= c[2] + tol
                           for q in kept):
                    kept.append(c + (f, g))
            out += [(i, j, l_, a_, w_, (i, *F[_walk(nxt, f, g)].tolist(), j))
                    for l_, a_, w_, f, g in kept]
            if out:
                P[i, j] = out
    return P
