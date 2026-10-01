"""R0 and R1 (Routing §3-§4) and the report's formulation R1-TR (§2), solved by HiGHS.

R1 on the station-path multigraph P = paths(p): x_p binary, u_i in [b_i, C] the load delivered up
to and including i, y_i in [alpha_i, Q] the charge on arrival at customer i.
    min  sum l_p x_p                                                             (R1.1)
    sum_{delta+(i)} x = sum_{delta-(i)} x = 1                                    (R1.2)
    u_j - u_i >= b_j - C (1 - X_ij) + (C - b_i - b_j) X_ji,  X_ij = sum_{P_ij} x (R1.3)
    y_i >= sum_{delta+(i)} a_p x_p                                               (R1.4)
    y_j <= Q - sum_{delta-(j) \\ D} w_p x_p                                       (R1.5)
    y_j <= y_i - e_ij x_ij + (Q - alpha_i)(1 - x_ij),  (i, j) direct             (R1.6)
    sum_{delta+(0)} x >= ceil(sum b / C).
(R1.3) is the MTZ row lifted by Desrochers and Laporte (1991); alpha_i = min_{delta+(i)} a_p is a
valid lower bound on y_i, which tightens (R1.6). R0 keeps only direct arcs and drops (R1.4)-(R1.6).
"""

import math

import numpy as np

from checks.certificate import provenance, record
from checks.route import replay
from models.milp import Rows, solve, status
from models.paths import paths

VERSION = {"R0": "R0/1", "R1": "R1/1", "R1-TR": "R1-TR/1"}


def chain(o, arcs, x):
    """Depot-to-depot node sequences of the chosen arcs (each arc carries its node tuple)."""
    succ = {a[0]: a for a, v in zip(arcs, x) if v > 0.5 and a[0] != o}
    R = []
    for a, v in zip(arcs, x):
        if v > 0.5 and a[0] == o:
            r = list(a[-1])
            while r[-1] != o:
                r += list(succ[r[-1]][-1][1:])
            R.append([k + 1 for k in r])
    return R


def rows(p, battery=True):
    """R1 (battery=True) or R0 as data: min c'v, rows lo <= Av <= hi, lb <= v <= ub, v_k integer
    where integ_k = 1. v = (x over arcs, u over customers[, y over customers]).

    OUTPUT  dict(c, R, lb, ub, integ, arcs, cut): cut lists customers with no admissible path in
            or out, which proves infeasibility; the rows are then not built.
    """
    o, I, b, C, Q, D = p["depot"], p["I"], p["b"], p["C"], p["Q"], p["D"]
    if battery:
        arcs = [a for v in paths(p).values() for a in v]
    else:
        arcs = [(i, j, D[i, j], 0.0, 0.0, (i, j)) for i in [o] + I for j in I + [o] if i != j]
    n, N = len(I), len(arcs)
    ci = {i: k for k, i in enumerate(I)}
    u = lambda i: N + ci[i]
    y = lambda i: N + n + ci[i]
    nv = N + (2 * n if battery else n)
    R, X = Rows(), {}
    out = {i: [] for i in [o] + I}
    inn = {j: [] for j in I + [o]}
    for k, (i, j, *_) in enumerate(arcs):
        out[i].append(k)
        inn[j].append(k)
        X.setdefault((i, j), []).append(k)
    M = dict(arcs=arcs, cut=[i + 1 for i in I if not out[i] or not inn[i]])
    if M["cut"]:
        return M
    for i in I:                                                     # (R1.2)
        R.add(out[i], [1.0] * len(out[i]), 1, 1)
        R.add(inn[i], [1.0] * len(inn[i]), 1, 1)
    R.add(out[o], [1.0] * len(out[o]), math.ceil(b[I].sum() / C - 1e-9))
    for i in I:                                                     # (R1.3), lifted
        for j in I:
            if i != j:
                xij, xji = X.get((i, j), []), X.get((j, i), [])
                R.add([u(j), u(i), *xij, *xji],
                      [1.0, -1.0, *[-C] * len(xij), *[-(C - b[i] - b[j])] * len(xji)], b[j] - C)
    alpha = {i: min(arcs[k][3] for k in out[i]) for i in I} if battery else {}
    if battery:
        for i in I:                                                 # (R1.4)
            R.add([y(i), *out[i]], [1.0, *[-arcs[k][3] for k in out[i]]], 0)
        for j in I:                                                 # (R1.5)
            K = [k for k in inn[j] if len(arcs[k][5]) > 2 or arcs[k][0] == o]
            R.add([y(j), *K], [1.0, *[arcs[k][4] for k in K]], hi=Q)
        for k, (i, j, _, a, _, v) in enumerate(arcs):                # (R1.6)
            if len(v) == 2 and i != o and j != o:
                Mi = Q - alpha[i]
                R.add([y(j), y(i), k], [1.0, -1.0, a + Mi], hi=Mi)
    return dict(M, R=R, c=np.r_[[a[2] for a in arcs], np.zeros(nv - N)],
                lb=np.r_[np.zeros(N), b[I], [alpha[i] for i in I] if battery else []],
                ub=np.r_[np.ones(N), np.full(n, C), np.full(n, Q) if battery else []],
                integ=np.r_[np.ones(N), np.zeros(nv - N)])


def routes_of(p, M, v):
    """Routes (exchange format) of a solution vector v of rows(p)."""
    return chain(p["depot"], M["arcs"], v)


def r1(p, battery=True, time_limit=600.0, gap=1e-7):
    """R1 (battery=True) or R0 (battery=False) by HiGHS. Returns a result record.

    U is the length of the returned routes as replayed by checks.route; L is HiGHS's dual bound.
    """
    name = "R1" if battery else "R0"
    M = rows(p, battery)
    if M["cut"]:
        return record(name, p["name"], "infeasible", solver=dict(
            code=None, message=f"customers {M['cut']} have no admissible path in or out"),
            elapsed=0.0, provenance=provenance(p, formulation=VERSION[name]), routes=None,
            paths=len(M["arcs"]))
    res, dt = solve(M["c"], M["R"], M["lb"], M["ub"], M["integ"], time_limit, gap)
    s = status(res)
    routes = routes_of(p, M, res.x) if res.x is not None else None
    rp = replay(p if battery else dict(p, Q=np.inf), routes) if routes else None
    U = rp["length"] if rp and rp["ok"] else None
    L = getattr(res, "mip_dual_bound", None) if s in ("optimal", "feasible_limit") else None
    return record(name, p["name"], s, U=U, L=L,
                  validation="replayed" if U is not None else
                  "validation_failed" if rp else "not_available",
                  objective=None if res.x is None else float(res.fun), bound_source="highs_dual",
                  solver=dict(code=int(res.status), message=res.message), elapsed=dt,
                  provenance=provenance(p, time_limit=time_limit, mip_rel_gap=gap,
                                        formulation=VERSION[name]),
                  routes=routes,
                  replay=None if rp is None else dict(ok=rp["ok"], defects=rp["defects"]),
                  paths=len(M["arcs"]), rows=len(M["R"].lo),
                  nodes=getattr(res, "mip_node_count", None))


def r0(p, **kw):
    return r1(p, battery=False, **kw)


def r1tr(p, beta=None, time_limit=600.0, gap=1e-7):
    """The report's MILP (its (1)-(10)) with the depot split into source 0 and sink 0'.

    Station f has beta copies (default 2n, the report's footnote 1), used in order (copy k+1 only
    if copy k is), and arcs between copies of one station are omitted: neither changes the
    optimum. u is the remaining load capacity and y the charge on arrival, as in the report.
    """
    o, I, F, b, C, Q, h, D = p["depot"], p["I"], p["F"], p["b"], p["C"], p["Q"], p["h"], p["D"]
    beta = beta or 2 * len(I)
    V = [("s", o), *[("c", i) for i in I], *[("f", f, k) for f in F for k in range(beta)],
         ("t", o)]
    loc = [v[1] for v in V]
    src, snk = 0, len(V) - 1
    arcs = [(a, z) for a in range(len(V) - 1) for z in range(1, len(V))
            if a != z and (a, z) != (src, snk)
            and not (V[a][0] == V[z][0] == "f" and V[a][1] == V[z][1])]
    N, m = len(arcs), len(V)
    u = lambda v: N + v
    y = lambda v: N + m + v
    R = Rows()
    out = [[] for _ in V]
    inn = [[] for _ in V]
    for k, (a, z) in enumerate(arcs):
        out[a].append(k)
        inn[z].append(k)
    for v, kind in enumerate(V):
        if kind[0] == "c":                                          # (2), (4)
            R.add(out[v], [1.0] * len(out[v]), 1, 1)
        if kind[0] in "cf":
            R.add(out[v] + inn[v], [1.0] * len(out[v]) + [-1.0] * len(inn[v]), 0, 0)
        if kind[0] == "f":                                          # (3), copies in order
            R.add(out[v], [1.0] * len(out[v]), hi=1)
            if kind[2] > 0:
                R.add(out[v] + out[v - 1], [1.0] * len(out[v]) + [-1.0] * len(out[v - 1]), hi=0)
    for k, (a, z) in enumerate(arcs):
        e = h * D[loc[a], loc[z]]
        if a != src:                                                # (5)
            R.add([u(z), u(a), k], [1.0, -1.0, (b[loc[a]] if V[a][0] == "c" else 0.0) + C], hi=C)
        else:
            R.add([u(z)], [1.0], hi=C)
        if V[a][0] == "c":                                          # (7)
            R.add([y(z), y(a), k], [1.0, -1.0, e + Q], hi=Q)
        else:                                                       # (8)
            R.add([y(z), k], [1.0, e], hi=Q)
    lb = np.zeros(N + 2 * m)
    ub = np.r_[np.ones(N), np.full(m, C), np.full(m, Q)]
    lb[u(src)], lb[y(src)] = C, Q
    c = np.r_[[D[loc[a], loc[z]] for a, z in arcs], np.zeros(2 * m)]
    res, dt = solve(c, R, lb, ub, np.r_[np.ones(N), np.zeros(2 * m)], time_limit, gap)
    s = status(res)
    routes = None
    if res.x is not None:
        succ = {a: z for (a, z), v in zip(arcs, res.x) if v > 0.5}
        routes = []
        for (a, z), v in zip(arcs, res.x):
            if v > 0.5 and a == src:
                r = [src, z]
                while r[-1] != snk:
                    r.append(succ[r[-1]])
                routes.append([loc[k] + 1 for k in r])
    rp = replay(p, routes) if routes else None
    U = rp["length"] if rp and rp["ok"] else None
    L = getattr(res, "mip_dual_bound", None) if s in ("optimal", "feasible_limit") else None
    return record("R1-TR", p["name"], s, U=U, L=L,
                  validation="replayed" if U is not None else
                  "validation_failed" if rp else "not_available",
                  objective=None if res.x is None else float(res.fun), bound_source="highs_dual",
                  solver=dict(code=int(res.status), message=res.message), elapsed=dt,
                  provenance=provenance(p, beta=beta, time_limit=time_limit, mip_rel_gap=gap,
                                        formulation=VERSION["R1-TR"]),
                  routes=routes,
                  replay=None if rp is None else dict(ok=rp["ok"], defects=rp["defects"]),
                  arcs=N)
