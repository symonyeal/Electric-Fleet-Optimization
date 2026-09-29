"""Exhaustive EVRP optimum for tiny instances (Validation §2). Imports nothing from models/.

Rules of Routing §1. For a fixed customer order, a label search carries (length, charge) through
the order; between consecutive stops it may go direct or through any walk of stations, found by
Dijkstra over legs the battery allows. The subset cost is the least over orders; the optimum is
the least partition of the customers into routes. O(n! 3^n) in the worst case: n <= 7.
"""

import itertools
import math

INF = math.inf


def enum(p, tol=1e-9):
    """OUTPUT  (z*, routes): optimal length and routes as 1-based identifiers; (inf, None) if
    no feasible solution exists."""
    X, o, I, F, Q, h, C, b = p["X"], p["depot"], p["I"], p["F"], p["Q"], p["h"], p["C"], p["b"]

    def d(i, j):
        return math.hypot(X[i][0] - X[j][0], X[i][1] - X[j][1])

    def reach(s, y, t):
        """(added length, charge on arrival at t, stations between) for each way from s to t."""
        out = [(d(s, t), y - h * d(s, t), [])] if h * d(s, t) <= y + tol else []
        dist = {f: d(s, f) for f in F if h * d(s, f) <= y + tol}
        prev, done = dict.fromkeys(dist), set()
        while len(done) < len(dist):
            f = min((g for g in dist if g not in done), key=dist.get)
            done.add(f)
            for g in F:
                dg = dist[f] + d(f, g)
                if g not in done and h * d(f, g) <= Q + tol and dg < dist.get(g, INF):
                    dist[g], prev[g] = dg, f
        for g, dg in dist.items():
            if h * d(g, t) <= Q + tol:
                walk = [g]
                while prev[walk[-1]] is not None:
                    walk.append(prev[walk[-1]])
                out.append((dg + d(g, t), Q - h * d(g, t), walk[::-1]))
        return out

    def route(seq):
        labels = [(0.0, Q, [o])]
        for t in [*seq, o]:
            new = sorted((L + dl, y2, v + mid + [t]) for L, y, v in labels
                         for dl, y2, mid in reach(v[-1], y, t))
            labels, best = [], -INF
            for lab in new:                                   # Pareto: shorter or more charge
                if lab[1] > best + tol:
                    labels.append(lab)
                    best = lab[1]
        return (labels[0][0], labels[0][2]) if labels else (INF, None)

    n = len(I)
    cost = {0: (0.0, [])}
    for mask in range(1, 1 << n):
        S = [I[k] for k in range(n) if mask >> k & 1]
        cost[mask] = (INF, None)
        if sum(b[i] for i in S) <= C + tol:
            cost[mask] = min((route(q) for q in itertools.permutations(S)), key=lambda r: r[0])
    f = {0: (0.0, [])}
    for mask in range(1, 1 << n):
        low, f[mask] = mask & -mask, (INF, None)
        s = mask
        while s:
            if s & low and cost[s][0] + f[mask ^ s][0] < f[mask][0]:
                f[mask] = (cost[s][0] + f[mask ^ s][0], [cost[s][1], *f[mask ^ s][1]])
            s = (s - 1) & mask
    z, R = f[(1 << n) - 1]
    return (z, [[k + 1 for k in r] for r in R]) if z < INF else (INF, None)
