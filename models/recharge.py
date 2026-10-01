"""R3: partial recharging with resistive loss, a convex MINLP (Routing §6).

Arcs are direct (i, -, j) or through one station (i, f, j), sources {0} ∪ I, sinks I ∪ {0'}.
With x binary per arc, u load and y charge on arrival and t time of arrival at each customer,
and per station arc the energy charged q, dwell tau and grid energy g:
    min  c_d sum l x + c_e sum g + c_tau sum tau
    degree rows, the capacity bound and lifted MTZ rows as in R1 (R1.2)-(R1.3);
    y_i >= sum_{out of i} a x   (a = e_ij direct, e_if via a station)          (R1.4)
    y_j = y_i - e_ij  on a used direct arc                       (two big-M rows)
    y_j = y_i + q - e_if - e_fj  on a used station arc,  y_i - e_if x + q <= Q   (R3.1)
(R1 needs only the upper side, since it always charges to full; with partial charges y must be
the true charge, or the capacity row y_i - e_if + q <= Q would be under-stated.)
    0 <= q <= Q x,  q <= P tau,  tau_min x <= tau <= T x                        (R3.2)
    g >= q/eta + alpha q^2 / tau   (closed perspective; convex)                 (R3.3)
    t_j >= t_i + sigma + travel (+ tau) - M (1 - x),  every route back by T.
At most one station lies between consecutive customers: a restriction, so R3's optimum is an
upper bound on the unrestricted model. The least dwell tau_min on a used station keeps (R3.3)
smooth for the barrier method; outer approximation cuts (R3.4) hold down to tau = 0.
"""

import math

import numpy as np
import scipy.sparse as sp

from checks.certificate import provenance, record
from checks.route import replay_charge
from data.scenario import validate
from methods.branch import split
from methods.ipm import ipm, standard
from methods.oa import oa
from models.milp import Rows
import itertools

VERSION = "R3/1"


def arcs(p):
    o, I, F, D, h, Q = p["depot"], p["I"], p["F"], p["D"], p["h"], p["Q"]
    out = []
    for i in [o, *I]:
        for j in [*I, o]:
            if i == j:
                continue
            if h * D[i, j] <= Q + 1e-9:
                out.append((i, None, j))
            out += [(i, f, j) for f in F if h * D[i, f] <= Q + 1e-9 and h * D[f, j] <= Q + 1e-9]
    return out


def rows(p, sc):
    validate(sc)
    o, I, b, C, Q, h, D = p["depot"], p["I"], p["b"], p["C"], p["Q"], p["h"], p["D"]
    t, ch, co = sc["time"], sc["charger"], sc["cost"]
    v, sig, T, tmin, P = t["speed"], t["service"], t["T"], t["tau_min"], ch["P"]
    A = arcs(p)
    S = [k for k, a in enumerate(A) if a[1] is not None]
    n, N, m = len(I), len(A), len(S)
    ci = {i: k for k, i in enumerate(I)}
    x, u, y, tt = 0, N, N + n, N + 2 * n
    q, tau, g = N + 3 * n, N + 3 * n + m, N + 3 * n + 2 * m
    nv = N + 3 * n + 3 * m
    sp_ = {k: s for s, k in enumerate(S)}
    lb, ub, integ, cost = np.zeros(nv), np.full(nv, np.inf), np.zeros(nv), np.zeros(nv)
    ub[:N], integ[:N] = 1, 1
    lb[u:u + n], ub[u:u + n] = b[I], C
    ub[y:y + n], ub[tt:tt + n] = Q, T
    ub[q:q + m], ub[tau:tau + m] = Q, T
    ub[g:g + m] = Q / ch["eta"] + ch["alpha"] * Q * Q / tmin     # most a visit can draw
    length = lambda a: D[a[0], a[2]] if a[1] is None else D[a[0], a[1]] + D[a[1], a[2]]
    cost[:N] = co["distance"] * np.array([length(a) for a in A])
    cost[g:g + m], cost[tau:tau + m] = co["energy"], co["dwell"]
    R = Rows()
    out = {i: [] for i in [o, *I]}
    inn = {j: [] for j in [*I, o]}
    X = {}
    for k, (i, _, j) in enumerate(A):
        out[i].append(k)
        inn[j].append(k)
        X.setdefault((i, j), []).append(k)
    for i in I:
        R.add(out[i], [1.0] * len(out[i]), 1, 1)
        R.add(inn[i], [1.0] * len(inn[i]), 1, 1)
    R.add(out[o], [1.0] * len(out[o]), math.ceil(b[I].sum() / C - 1e-9))
    for i in I:
        for j in I:
            if i != j:
                xij, xji = X.get((i, j), []), X.get((j, i), [])
                R.add([u + ci[j], u + ci[i], *xij, *xji],
                      [1.0, -1.0, *[-C] * len(xij), *[-(C - b[i] - b[j])] * len(xji)], b[j] - C)
    first = lambda a: h * (D[a[0], a[2]] if a[1] is None else D[a[0], a[1]])
    for i in I:                                                        # (R1.4)
        R.add([y + ci[i], *out[i]], [1.0, *[-first(A[k]) for k in out[i]]], 0)
    for k, (i, f, j) in enumerate(A):
        tr = length(A[k]) / v
        if f is None:                   # y is the true charge on used arcs: rows on both sides
            e = h * D[i, j]
            if i != o and j != o:
                R.add([y + ci[j], y + ci[i], k], [1.0, -1.0, e + Q], hi=Q)
                R.add([y + ci[j], y + ci[i], k], [1.0, -1.0, e - Q], lo=-Q)
            elif i == o:
                R.add([y + ci[j], k], [1.0, e], hi=Q)
                R.add([y + ci[j], k], [1.0, -(Q - e)], lo=0)
        else:
            s, e1, e2 = sp_[k], h * D[i, f], h * D[f, j]
            yi = [y + ci[i]] if i != o else []
            Qi = 0.0 if i != o else Q                                   # the depot sends Q
            if j != o:                                                  # (R3.1)
                R.add([y + ci[j], *yi, q + s, k], [1.0, *[-1.0] * len(yi), -1.0, e1 + e2 + Q],
                      hi=Q + Qi)
                R.add([y + ci[j], *yi, q + s, k],                       # and its lower side
                      [1.0, *[-1.0] * len(yi), -1.0, e1 + e2 - Q - Qi], lo=-Q)
            else:
                R.add([*yi, q + s, k], [*[1.0] * len(yi), 1.0, -(e1 + e2 + Q)], lo=-Q - Qi)
            R.add([*yi, q + s, k], [*[1.0] * len(yi), 1.0, -e1], hi=Q - Qi)
            R.add([q + s, k], [1.0, -Q], hi=0)                           # (R3.2)
            R.add([q + s, tau + s], [1.0, -P], hi=0)
            R.add([tau + s, k], [1.0, -T], hi=0)
            R.add([tau + s, k], [1.0, -tmin], lo=0)
        dw = [tau + sp_[k]] if f is not None else []
        M = 2 * T + sig + tr
        if j != o and i != o:                                           # time
            R.add([tt + ci[j], tt + ci[i], *dw, k], [1.0, -1.0, *[-1.0] * len(dw), -M],
                  lo=sig + tr - M)
        elif j != o:
            R.add([tt + ci[j], *dw, k], [1.0, *[-1.0] * len(dw), -M], lo=tr - M)
        elif i != o:
            R.add([tt + ci[i], *dw, k], [1.0, *[1.0] * len(dw), M], hi=T + M - sig - tr)
    return dict(c=cost, R=R, lb=lb, ub=ub, integ=integ, A=A, S=S, idx=dict(x=x, u=u, y=y, t=tt,
                q=q, tau=tau, g=g), n=n, m=m, sc=sc)


def loss(M):
    """(R3.3) per station arc on (q, tau, g), with the closure at tau = 0 (then q = 0)."""
    eta, alpha = M["sc"]["charger"]["eta"], M["sc"]["charger"]["alpha"]
    i = M["idx"]

    def f(z):
        qv, tv, gv = z
        return qv / eta + (alpha * qv * qv / tv if tv > 1e-12 else 0.0) - gv

    def grad(z):
        r = z[0] / z[1] if z[1] > 1e-12 else 0.0                       # power q/tau
        return np.array([1 / eta + 2 * alpha * r, -alpha * r * r, -1.0])   # (R3.4) at r

    return [dict(idx=np.array([i["q"] + s, i["tau"] + s, i["g"] + s]), f=f, grad=grad)
            for s in range(M["m"])]


def routes_of(p, M, v):
    """Routes (1-based, stations included) and charges {(route, position): (q, tau)}."""
    o, A, S = p["depot"], M["A"], {k: s for s, k in enumerate(M["S"])}
    i = M["idx"]
    succ = {A[k][0]: k for k in range(len(A)) if v[k] > 0.5 and A[k][0] != o}
    R, Qc = [], {}
    for k0 in (k for k in range(len(A)) if v[k] > 0.5 and A[k][0] == o):
        r, k = [o], k0
        while True:
            a = A[k]
            if a[1] is not None:
                Qc[len(R), len(r)] = (float(v[i["q"] + S[k]]), float(v[i["tau"] + S[k]]))
                r.append(a[1])
            r.append(a[2])
            if a[2] == o:
                break
            k = succ[a[2]]
        R.append([z + 1 for z in r])
        del r
    return R, Qc


def fixed(p, M, x, tol=1e-9):
    """R3 at x's routes by the textbook barrier method (Vanderbei Ch. 25), with (A5)."""
    lb, ub = M["lb"].copy(), M["ub"].copy()
    N, i, S = len(M["A"]), M["idx"], M["S"]
    lb[:N] = ub[:N] = np.round(x[:N])
    off = [s for s, k in enumerate(S) if lb[k] == 0]
    for key in ("q", "tau", "g"):
        ub[i[key] + np.array(off, int)] = 0.0
    on = [s for s, k in enumerate(S) if lb[k] == 1]
    A = M["R"].constraint(len(M["c"]))
    St = standard(M["c"], *split(A.A, A.lb, A.ub), lb, ub)
    Ns = len(St[0])
    eta, alpha = M["sc"]["charger"]["eta"], M["sc"]["charger"]["alpha"]
    Qi, Ti, Gi = (i[k] + np.array(on, int) for k in ("q", "tau", "g"))
    k = len(on)
    rr = np.r_[np.arange(k), np.arange(k), np.arange(k)]
    cc = np.r_[Qi, Ti, Gi]

    def h(w):
        return w[Qi] / eta + alpha * w[Qi] ** 2 / w[Ti] - w[Gi]

    def Jh(w):
        r = w[Qi] / w[Ti]
        return sp.csr_array((np.r_[1 / eta + 2 * alpha * r, -alpha * r * r, -np.ones(k)],
                             (rr, cc)), shape=(k, Ns))

    def Hh(w, lam):                       # alpha q^2/tau: [[2/tau, -2q/tau^2], [., 2q^2/tau^3]]
        qv, tv = w[Qi], w[Ti]
        a = 2 * alpha * lam
        return sp.csr_array((np.r_[a / tv, -a * qv / tv ** 2, -a * qv / tv ** 2,
                                   a * qv ** 2 / tv ** 3],
                             (np.r_[Qi, Qi, Ti, Ti], np.r_[Qi, Ti, Qi, Ti])), shape=(Ns, Ns))

    r = ipm(*St, **(dict(h=h, Jh=Jh, Hh=Hh) if k else {}))
    if r["x"] is None or r["status"] != "optimal":
        return r["status"], None, None, None
    return r["status"], r["x"][:len(M["c"])], r["f"], r["L"]


def r3p(p, sc, J=8, time_limit=600.0):
    """R3-P (Routing §6): tangents (R3.4) at powers r_0..r_J give a lower MILP; the maximum of
    the secants (R3.5), valid since q <= P tau keeps q/tau in [0, P], an upper MILP whose
    routes are replayed. OUTPUT lower (valid lower bound on R3), upper (replayed cost)."""
    from scipy.optimize import Bounds, LinearConstraint, milp
    M = rows(p, sc)
    N, i, m = len(M["c"]), M["idx"], M["m"]
    eta, alpha, P = sc["charger"]["eta"], sc["charger"]["alpha"], sc["charger"]["P"]
    A = M["R"].constraint(N)
    r = np.linspace(0.0, P, J + 1)
    out = {}
    for side, pieces in (("lower", [(1 / eta + 2 * alpha * s, alpha * s * s) for s in r]),
                         ("upper", [(1 / eta + alpha * (s0 + s1), alpha * s0 * s1)
                                    for s0, s1 in itertools.pairwise(r)])):
        rr, cc, dd = [], [], []
        for s in range(m):
            for k, (slope, tq) in enumerate(pieces):
                row = s * len(pieces) + k
                rr += [row] * 3
                cc += [i["q"] + s, i["tau"] + s, i["g"] + s]
                dd += [slope, -tq, -1.0]
        T = sp.csr_array((dd, (rr, cc)), shape=(m * len(pieces), N))
        res = milp(M["c"], constraints=[A, LinearConstraint(T, -np.inf, 0.0)],
                   integrality=M["integ"], bounds=Bounds(M["lb"], M["ub"]),
                   options=dict(time_limit=time_limit, mip_rel_gap=1e-7))
        if side == "lower":
            out["lower"] = getattr(res, "mip_dual_bound", None) if res.x is not None else None
        else:
            out["upper"] = None
            if res.x is not None:
                routes, charges = routes_of(p, M, res.x)
                rp = replay_charge(p, sc, routes, charges)
                out["upper"] = rp["cost"] if rp["ok"] else None
                out["upper_defects"] = rp["defects"]
    return out


def r3(p, sc, name=None, max_iter=50, time_limit=3600.0, master_limit=600.0, keep_x=False):
    """R3 by outer approximation; U is the cost of routes replayed with partial charges.
    keep_x adds the solution vector, for the fixed-route subproblem."""
    M = rows(p, sc)
    A = M["R"].constraint(len(M["c"]))
    P, i, m = sc["charger"]["P"], M["idx"], M["m"]
    pts = []
    for rate in (0.0, P / 2, P):                          # cuts at powers 0, P/2, P per arc
        z = np.zeros(len(M["c"]))
        z[i["tau"]:i["tau"] + m] = 1.0
        z[i["q"]:i["q"] + m] = rate
        pts.append(z)

    def sub(x):
        st, w, f, _ = fixed(p, M, x)
        return st, w, f

    def validate(w):
        routes, charges = routes_of(p, M, w)
        rp = replay_charge(p, sc, routes, charges)
        return rp["ok"], rp["cost"]

    r = oa(M["c"], A.A, A.lb, A.ub, M["lb"], M["ub"], M["integ"], loss(M), sub, validate, pts,
           max_iter=max_iter, time_limit=time_limit, master_limit=master_limit)
    routes = charges = None
    if r["v"] is not None:
        routes, charges = routes_of(p, M, r["v"])
    return record("R3", name or p["name"], r["status"], U=r["U"], L=r["L"],
                  bound_source="oa_master_dual",
                  solver=dict(code=None, message=f"outer approximation, "
                              f"{len(r['iterations'])} iterations"), elapsed=r["elapsed"],
                  provenance=provenance(p, max_iter=max_iter, time_limit=time_limit,
                                        master_limit=master_limit, formulation=VERSION),
                  iterations=r["iterations"],
                  routes=routes, charges=None if charges is None else
                  {f"{a}:{b}": qt for (a, b), qt in charges.items()}, arcs=len(M["A"]),
                  **({"x": None if r["v"] is None else r["v"].tolist()} if keep_x else {}))
