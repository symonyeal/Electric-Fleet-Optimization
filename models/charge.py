"""Fixed-integer charging subproblems of M1-Q and M2 (Models §4), solved by interior-point and
barrier methods and bounded by (A5) (Algorithms §5).

With every integer of M1 fixed, what remains is convex:
    M1-Q   min c'v + Delta sum gamma p^2       over M1's rows          (a QP)
    M2     min c'v + Delta sum gamma p^2       over M2's linear rows and
           c_k(v) = p_k/eta + alpha p_k^2 - g_k <= 0                   (a convex QCQP)
Fixing u_jt = 0 fixes p_jt = g_jt = 0: those faces are removed before any barrier acts. The
rows are built once per run (models/transit.py compiles the instance); a fixed-integer
subproblem changes only bounds and the nonlinear terms.
M1-Q is solved by methods/ipm.py and, independently, by trust-constr. M2 is solved by the
textbook barrier method for convex programs (methods/ipm.py with h; Vanderbei Ch. 25) and,
independently, by trust-constr; the two agree to 1e-6 on the tests. Bounds are (A5): any
multipliers mu, lam >= 0 and nu give one, because the Lagrangian is convex and its tangent at
v^ is a global minorant (Beck Ch. 7, 12).

The MINLP M2 is solved by outer approximation (methods/oa.py) with these subproblems, and
bracketed by M2-P (Models §5): tangents at fixed breakpoints give a lower MILP, the maximum of
secants an upper MILP whose schedules are feasible for M2. Both run with gamma = 0, the loss
alone (Models §4); the stress term is studied at fixed integers, by M1-Q.
"""

import numpy as np
import scipy.sparse as sp
from scipy.optimize import Bounds, LinearConstraint, NonlinearConstraint, linprog, milp, minimize

from checks.certificate import provenance, record
from checks.schedule import replay_energy
from methods.branch import split
from methods.ipm import ipm, standard
from methods.oa import oa
from models.fleet import linear, rows, solution
from models.transit import compile
import itertools

VERSION = "M2/2"      # follows M1/2

TC = dict(initial_barrier_parameter=1e-8, initial_barrier_tolerance=1e-8, barrier_tol=1e-10,
          gtol=1e-10, xtol=1e-14, maxiter=5000)          # docs/TOOLCHAIN.md


def lift(Ma, Mb, x):
    """Carry a solution of rows Ma to rows Mb by block name; blocks absent from Ma are 0."""
    y = np.zeros(len(Mb["c"]))
    for k, i in Ma["idx"].items():
        if k in Mb["idx"]:
            y[Mb["idx"][k]:Mb["idx"][k] + Ma["size"][k]] = x[i:i + Ma["size"][k]]
    return y


def fixed_box(M, x):
    """Bounds with every integer fixed at round(x), p = g = 0 where u = 0, and the restoration
    r_i = 0 where trip i is not a pull-in: zero directions leave the box, so no barrier acts on
    a face without interior (Models §6)."""
    lb, ub = M["lb"].copy(), M["ub"].copy()
    J = np.flatnonzero(M["integ"])
    lb[J] = ub[J] = np.round(x[J])
    i, K, n = M["idx"], len(M["K"]), M["size"]["r"]
    off = np.flatnonzero(lb[i["u"]:i["u"] + K] == 0)
    ub[i["p"] + off] = 0.0
    if "g" in i:
        ub[i["g"] + off] = 0.0
    ub[i["r"] + np.flatnonzero(lb[i["x1"]:i["x1"] + n] == 0)] = 0.0
    return lb, ub


def stress(M, v):
    """Diagonal of the M1-Q Hessian: 2 Delta gamma on p (Models (9))."""
    q = np.zeros(len(M["c"]))
    q[M["idx"]["p"]:M["idx"]["p"] + len(M["K"])] = 2 * M["h"] * v["charger"].get("gamma", 0.0)
    return q


def reduce(M, lb, ub):
    """Rows restricted to the free variables, with the fixed ones moved to the bounds."""
    A = linear(M)
    F = np.flatnonzero(lb < ub)
    Z = np.flatnonzero(lb == ub)
    s = A.A[:, Z] @ lb[Z]
    Af = A.A[:, F]
    keep = np.flatnonzero(np.diff(Af.tocsr().indptr) > 0)
    return F, Z, Af[keep], A.lb[keep] - s[keep], A.ub[keep] - s[keep]


def m1q_fixed(c, v, x, fixed=None, M=None):
    """M1-Q at fixed integers: methods/ipm.py (QP), trust-constr independently, bound (A5).
    M is M1's rows of (c, v, fixed), built here if absent."""
    M = M or rows(c, v, fixed)
    lb, ub = fixed_box(M, x)
    N, q = len(M["c"]), stress(M, v)
    A = linear(M)
    S = standard(M["c"], *split(A.A, A.lb, A.ub), lb, ub)
    Q = sp.diags_array(np.r_[q, np.zeros(len(S[0]) - N)])
    r = ipm(*S, Q=Q)
    F, Z, Af, lo, hi = reduce(M, lb, ub)
    cf, qf, v0 = M["c"][F], q[F], (lb[F] + np.minimum(ub[F], lb[F] + 1.0)) / 2
    fz = M["c"][Z] @ lb[Z] + 0.5 * q[Z] @ lb[Z] ** 2
    t = minimize(lambda w: cf @ w + 0.5 * qf @ w ** 2, v0, jac=lambda w: cf + qf * w,
                 hess=lambda w: sp.diags_array(qf), method="trust-constr",
                 constraints=[LinearConstraint(Af, lo, hi)], bounds=Bounds(lb[F], ub[F]),
                 options=TC)
    return dict(status=r["status"], f=r["f"], L=r["L"], independent=float(t.fun + fz),
                independent_status=t.status, x=r["x"][:N], kkt=r["err"])


def problem(c, v, x, fixed=None, M=None, M1=None):
    """M2 at fixed integers as functions of the free variables (for trust-constr and checks);
    M and M1 are M2's and M1's rows, built here if absent."""
    M = M or rows(c, v, fixed, loss=True)
    M1 = M1 or rows(c, v, fixed, inst=M["inst"])
    x2 = lift(M1, M, x)
    lb, ub = fixed_box(M, x2)
    F, Z, Af, lo, hi = reduce(M, lb, ub)
    pos = {k: n for n, k in enumerate(F)}
    pairs = [(pos[a], pos[b]) for a, b in M["loss"] if a in pos and b in pos]
    P, G = np.array([a for a, _ in pairs], int), np.array([b for _, b in pairs], int)
    eta, alpha = M["eta"], M["alpha"]
    q = stress(M, v)
    cf, qf = M["c"][F], q[F]
    const = M["c"][Z] @ lb[Z] + 0.5 * q[Z] @ lb[Z] ** 2
    m = len(pairs)

    def fun(w):
        return cf @ w + 0.5 * qf @ w ** 2

    def con(w):                                     # c_k(w) = p/eta + alpha p^2 - g <= 0
        return w[P] / eta + alpha * w[P] ** 2 - w[G]

    def jac(w):                                     # by coordinates: CSR orders data by column
        return sp.csr_array((np.r_[1 / eta + 2 * alpha * w[P], -np.ones(m)],
                             (np.r_[np.arange(m), np.arange(m)], np.r_[P, G])),
                            shape=(m, len(F)))

    def hess(w, lam):
        d = np.zeros(len(F))
        d[P] = 2 * alpha * lam
        return sp.diags_array(d)

    start = x2[F].copy()                            # M1's point, with g on the loss curve
    start[G] = start[P] / eta + alpha * start[P] ** 2
    return dict(M=M, lb=lb, ub=ub, F=F, Z=Z, Af=Af, lo=lo, hi=hi, P=P, G=G, fun=fun, start=start,
                grad=lambda w: cf + qf * w, con=con, jac=jac, hess=hess, const=const,
                cf=cf, qf=qf)


def m2_fixed(c, v, x, fixed=None, form="m1", M=None):
    """M2 at fixed integers by the textbook barrier method for convex programs (methods/ipm.py,
    Vanderbei Ch. 25), with its bound (A5). Loss rows whose p is fixed at 0 are dropped: their
    slack would be forced to 0, where no interior exists. x is an M1 solution (form="m1") or a
    vector of M2's rows (form="m2", as outer approximation passes); M is M2's rows, built here
    if absent, and only its bounds change."""
    M = M or rows(c, v, fixed, loss=True)
    lb, ub = fixed_box(M, lift(rows(c, v, fixed, inst=M["inst"]), M, x) if form == "m1" else x)
    N, q = len(M['c']), stress(M, v)
    A = linear(M)
    S = standard(M['c'], *split(A.A, A.lb, A.ub), lb, ub)
    Ns = len(S[0])
    pairs = [(a, b) for a, b in M['loss'] if ub[a] > 0]
    P, G = np.array([a for a, _ in pairs], int), np.array([b for _, b in pairs], int)
    eta, alpha, k = M['eta'], M['alpha'], len(pairs)
    rr = np.r_[np.arange(k), np.arange(k)]

    def h(w):                                           # p/eta + alpha p^2 - g <= 0   (10)
        return w[P] / eta + alpha * w[P] ** 2 - w[G]

    def Jh(w):
        return sp.csr_array((np.r_[1 / eta + 2 * alpha * w[P], -np.ones(k)],
                             (rr, np.r_[P, G])), shape=(k, Ns))

    def Hh(w, lam):
        d = np.zeros(Ns)
        d[P] = 2 * alpha * lam
        return sp.diags_array(d)

    r = ipm(*S, Q=sp.diags_array(np.r_[q, np.zeros(Ns - N)]),
            **(dict(h=h, Jh=Jh, Hh=Hh) if k else {}))
    if r['x'] is None:
        return dict(status=r['status'], f=None, L=None, loss_slack=None, w=None, loss_rows=k)
    w = r['x'][:N]
    return dict(status=r['status'], f=r['f'], L=r['L'],
                loss_slack=float(-h(r['x']).max(initial=0.0)) if k else 0.0,
                iterations=r['k'], kkt=r['err'], backtracks=r['stats']['backtracks'], w=w,
                loss_rows=k)


def m2_trust(c, v, x, fixed=None, M=None):
    """The same subproblem by trust-constr, kept as a cross-check (docs/TOOLCHAIN.md)."""
    d = problem(c, v, x, fixed, M=M)
    lb, ub = d['lb'][d['F']], d['ub'][d['F']]
    cons = [LinearConstraint(d['Af'], d['lo'], d['hi'])]
    if len(d['P']):
        cons.append(NonlinearConstraint(d['con'], -np.inf, 0.0, jac=d['jac'], hess=d['hess']))
    t = minimize(d['fun'], np.clip(d['start'], lb, ub), jac=d['grad'],
                 hess=lambda w: sp.diags_array(d['qf']), method='trust-constr',
                 constraints=cons, bounds=Bounds(lb, ub), options=TC)
    return dict(status=t.status, f=float(t.fun + d['const']), violation=t.constr_violation,
                bound=bound_a5(d, np.clip(t.x, lb, ub)))


def bound_a5(d, w):
    """(A5) at w: multipliers from the LP with each loss row replaced by its tangent at w and
    the objective by its tangent; any such multipliers give a valid bound."""
    Aub, bub, Aeq, beq = split(d["Af"], d["lo"], d["hi"])
    P, n = d["P"], len(w)
    eta = 1 / d["jac"](np.zeros(n)).data[0] if len(P) else 1.0
    Jw = d["jac"](w)
    Tt = Jw                                           # rows: jac_k (v - w) + c_k(w) <= 0
    bt = Jw @ w - d["con"](w)
    A_ub = sp.vstack([Aub, Tt], format="csr") if len(P) else Aub
    b_ub = np.r_[bub, bt] if len(P) else bub
    g = d["grad"](w)
    h = linprog(g, A_ub=A_ub if A_ub.shape[0] else None, b_ub=b_ub if A_ub.shape[0] else None,
                A_eq=Aeq if Aeq.shape[0] else None, b_eq=beq if Aeq.shape[0] else None,
                bounds=list(zip(d["lb"][d["F"]], d["ub"][d["F"]])), method="highs-ds")
    if h.status != 0:
        return None
    mu = -h.ineqlin.marginals if A_ub.shape[0] else np.zeros(0)
    nu = -h.eqlin.marginals if Aeq.shape[0] else np.zeros(0)
    mul, lam = mu[:Aub.shape[0]], mu[Aub.shape[0]:]
    Lw = d["fun"](w) + mul @ (Aub @ w - bub) + nu @ (Aeq @ w - beq) + (
        lam @ d["con"](w) if len(P) else 0.0)
    a = g + Aub.T @ mul + Aeq.T @ nu + (Jw.T @ lam if len(P) else 0.0)
    l, u = d["lb"][d["F"]], d["ub"][d["F"]]
    del eta
    return float(Lw + np.minimum(a * (l - w), a * (u - w)).sum() + d["const"])


def grad_check(c, v, x, fixed=None, h=1e-6):
    """Largest relative error of the analytic objective gradient and constraint Jacobian against
    central finite differences, at a random point of the box."""
    d = problem(c, v, x, fixed)
    lb, ub = d["lb"][d["F"]], d["ub"][d["F"]]
    g = np.random.default_rng(0)
    w = lb + g.uniform(0.2, 0.8, len(lb)) * (np.minimum(ub, lb + 100.0) - lb)
    E = np.eye(len(w))
    fd = np.array([(d["fun"](w + h * e) - d["fun"](w - h * e)) / (2 * h) for e in E])
    Jd = np.array([(d["con"](w + h * e) - d["con"](w - h * e)) / (2 * h) for e in E]).T
    err = [np.abs(fd - d["grad"](w)).max() / (1 + np.abs(fd).max())]
    if len(d["P"]):
        err.append(np.abs(Jd - d["jac"](w).toarray()).max() / (1 + np.abs(Jd).max()))
    return max(err)


def loss_only(v):
    return dict(v, charger=dict(v["charger"], gamma=0.0))


def loss_cons(M):
    """(10) as convex constraints for outer approximation: c(p, g) = p/eta + alpha p^2 - g."""
    eta, alpha = M["eta"], M["alpha"]
    return [dict(idx=np.array([p, g]), f=lambda z: z[0] / eta + alpha * z[0] ** 2 - z[1],
                 grad=lambda z: np.array([1 / eta + 2 * alpha * z[0], -1.0]))
            for p, g in M["loss"]]


def m2(c, v, name="corridor", fixed=None, max_iter=50, time_limit=3600.0, master_limit=600.0):
    """M2 by outer approximation; U is the cost of a schedule replayed with losses and taper."""
    v0 = loss_only(v)
    M = rows(c, v0, fixed, loss=True, inst=compile(c, v0))
    A = linear(M)
    i, K = M["idx"], len(M["K"])
    pts = []
    for r in (0.0, v["charger"]["P"] / 2, v["charger"]["P"]):
        z = np.zeros(len(M["c"]))
        z[i["p"]:i["p"] + K] = r
        pts.append(z)

    def sub(x):
        s = m2_fixed(c, v0, x, fixed, form="m2", M=M)
        return (s["status"], s["w"], s["f"]) if s["status"] == "optimal" else (s["status"], None,
                                                                              None)

    def validate(w):
        duties, plan, infra = solution(M, v0, w)
        rp = replay_energy(c, v0, duties, plan, infra, loss=True)
        return rp["ok"], rp["cost"]

    r = oa(M["c"], A.A, A.lb, A.ub, M["lb"], M["ub"], M["integ"], loss_cons(M), sub, validate,
           pts, max_iter=max_iter, time_limit=time_limit, master_limit=master_limit)
    duties = plan = infra = None
    if r["v"] is not None:
        duties, plan, infra = solution(M, v0, r["v"])
    return record("M2", name, r["status"], U=r["U"], L=r["L"],
                  bound_source="oa_master_dual",
                  solver=dict(code=None, message=f"outer approximation, "
                              f"{len(r['iterations'])} iterations"),
                  elapsed=r["elapsed"], provenance=provenance(
                      dict(name=name, sha256=c.get("source", {}).get("sha256")), fixed=fixed,
                      gamma=0.0, max_iter=max_iter, time_limit=time_limit,
                      master_limit=master_limit, formulation=VERSION,
                      corridor=M["inst"]["corridor"], scenario=M["inst"]["scenario"]),
                  iterations=r["iterations"],
                  cuts=r["cuts"], fleet=None if duties is None else len(duties), duties=duties,
                  plan=plan, infra=infra)


def m2p(c, v, J=8, fixed=None, time_limit=600.0):
    """M2-P (Models §5): lower MILP with tangents at J+1 breakpoints on [0, P], upper MILP with the
    maximum of the J secants. OUTPUT lower (a valid lower bound on M2), upper (the replayed M2
    cost of the upper MILP's schedule), and the losses' interpolation error alpha (P/J)^2 / 4."""
    v0 = loss_only(v)
    M = rows(c, v0, fixed, loss=True)
    N, eta, alpha, P = len(M["c"]), M["eta"], M["alpha"], v["charger"]["P"]
    A = linear(M)
    r = np.linspace(0.0, P, J + 1)
    out = {}
    for side, pieces in (("lower", [(1 / eta + 2 * alpha * s, alpha * s * s) for s in r]),
                         ("upper", [(1 / eta + alpha * (s0 + s1), alpha * s0 * s1)
                                    for s0, s1 in itertools.pairwise(r)])):
        rr, cc, dd, bb = [], [], [], []
        for q, (p, g) in enumerate(M["loss"]):
            for k, (slope, rhs) in enumerate(pieces):
                row = q * len(pieces) + k
                rr += [row, row]
                cc += [p, g]
                dd += [slope, -1.0]
                bb.append(rhs)
        T = sp.csr_array((dd, (rr, cc)), shape=(len(bb), N))
        res = milp(M["c"], constraints=[A, LinearConstraint(T, -np.inf, np.array(bb))],
                   integrality=M["integ"], bounds=Bounds(M["lb"], M["ub"]),
                   options=dict(time_limit=time_limit, mip_rel_gap=1e-7))
        if side == "lower":
            out["lower"] = getattr(res, "mip_dual_bound", None) if res.x is not None else None
        else:
            out["upper"] = None
            if res.x is not None:
                duties, plan, infra = solution(M, v0, res.x)
                rp = replay_energy(c, v0, duties, plan, infra, loss=True)
                out["upper"] = rp["cost"] if rp["ok"] else None
                out["upper_replay"] = rp["defects"]
    out["interpolation_error"] = alpha * (P / J) ** 2 / 4
    return out
