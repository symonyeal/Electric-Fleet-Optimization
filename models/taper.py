"""M3: charging under an integrated taper law, at a fixed schedule (Models §6).

Within a connected slot the stipulated law de/dt = q (1 - e/B), with constant command q, gives
    e+ = B - (B - e) exp(-Delta q / B)                                             (14)
and grid power largest at the slot's start, g^ = q (1 - e/B) / eta                 (16).
With the schedule, the plugs and the infrastructure of an M1 solution fixed, the commands q_jt
of the charging slots are the variables; energies follow by (14) bus by bus. The problem is
nonconvex (a difference of convex functions, Models (15)), so trust-constr returns local
solutions: several starts are run and none is labeled global. The fixed-integer M1 LP is a
valid optimistic bound: an M3 slot adds at most Delta P of energy, and its average grid power is
below the peak (16) that M3's rows use.
"""

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import Bounds, NonlinearConstraint, linprog, minimize

from methods.branch import split
from models.charge import fixed_box
from models.fleet import rows, solution, tariff
import itertools


def law(e, q, dt, B):
    """(14): energy after dt hours at command q from e."""
    return B - (B - e) * np.exp(-dt * q / B)


def integrate(e, q, dt, B):
    """(13) integrated numerically, for checking (14)."""
    return solve_ivp(lambda _, z: q * (1 - z / B), (0.0, dt), [e], rtol=1e-12,
                     atol=1e-12).y[0, -1]


def setup(c, v, x, fixed=None):
    """The schedule of an M1 solution x, and its charging slots as M3's variables."""
    M = rows(c, v, fixed)
    duties, _, infra = solution(M, v, x)
    _, ub = fixed_box(M, x)
    i, K, T = M["idx"], M["K"], M["inst"]["T"]
    on = [(j, t) for k, (j, t) in enumerate(K) if ub[i["p"] + k] > 0]  # plug held in M1
    return dict(M=M, duties=duties, infra=infra, on=on, x=x, trips={tr["id"]: j for j, tr in
                                                                  enumerate(T)})


def simulate(S, v, qv):
    """Energies, grid peaks per site and slot, and the cost of commands qv (in S["on"] order)."""
    M, b, ch, co = S["M"], v["battery"], v["charger"], v["cost"]
    m, h, eta = M["inst"], M["h"], ch["eta"]
    B, rB, top, s0B = b["B"], m["rB"], m["top"], m["s0B"]
    q = dict(zip(S["on"], qv, strict=True))
    T, kap = m["T"], m["kappa"]
    E = m["E"]
    cons, energy, restore, peak = [], 0.0, 0.0, {}
    km_ij = {(a, z): k for k, (a, z, _) in enumerate(m["P"])}
    for d in S["duties"]:
        idx = [S["trips"][k] for k in d]
        e = s0B - kap * m["km0"][idx[0]]
        cons.append(e - rB)                                        # arrival above reserve
        for n_, j in enumerate(idx):
            for t in m["win"].get(j, []):
                if (j, t) in q:
                    g = q[j, t] * (1 - e / B) / eta                # (16)
                    s = m["site"][T[j]["first"]]
                    peak[s, t] = peak.get((s, t), 0.0) + g
                    e2 = law(e, q[j, t], h, B)
                    energy += (e2 - e) / eta
                    e = e2
            cons += [top - e, e - E[j] - rB]                        # departure within bounds
            e -= E[j]
            if n_ + 1 < len(idx):
                e -= kap * m["km_ij"][km_ij[j, idx[n_ + 1]]]
                cons.append(e - rB)
            else:
                e -= kap * m["km1"][j]
                cons.append(e - rB)
                restore += (s0B - e) / eta
    for (s, _), g in peak.items():                                  # grid (6) at the peak
        cons.append(v["sites"][s]["G0"] + S["infra"][s]["h"] - v["sites"][s]["L"] - g)
    ex, w0, w1 = tariff(co)
    D = {}
    for (s, t), g in peak.items():
        if w0 <= t * m["D"] % 86400 < w1:                          # billing window (Data §3)
            D[s] = max(D.get(s, 0.0), v["sites"][s]["L"] + g)
    cost = ex * (co["energy"] * energy + co["depot_energy"] * restore
                 + co["peak"] * sum(D.values()))
    return np.array(cons), cost


def m3_fixed(c, v, x, fixed=None, starts=5, seed=0):
    """Local solutions of M3 at x's schedule from several starts, the optimistic M1 bound, and
    the largest gap between (14) and numerical integration at the best solution."""
    S = setup(c, v, x, fixed)
    P, n = v["charger"]["P"], len(S["on"])
    M, co = S["M"], v["cost"]
    m = M["inst"]
    km_ij = {(a, z): k for k, (a, z, _) in enumerate(m["P"])}
    km = 0.0
    for d in S["duties"]:                                          # buses, deadhead, sites
        idx = [S["trips"][k] for k in d]
        km += m["km0"][idx[0]] + m["km1"][idx[-1]] + sum(
            m["km_ij"][km_ij[a, z]] for a, z in itertools.pairwise(idx))
    fixed_cost = (co["F"] * len(S["duties"]) + co["deadhead"] * km
                  + sum(co["site"] + tariff(co)[0] * co.get("basic", 0.0) + co["plug"] * f["n"]
                        + co["upgrade"] * f["h"]
                        for f in S["infra"].values()))
    lb, ub = fixed_box(M, x)
    A = M["R"].constraint(len(M["c"]))
    Aub, bub, Aeq, beq = split(A.A, A.lb, A.ub)
    lp = linprog(M["c"], Aub, bub, Aeq, beq, bounds=list(zip(lb, ub)), method="highs-ds")
    g = np.random.default_rng(seed)
    sols = []
    for k in range(starts):
        q0 = np.full(n, P) if k == 0 else g.uniform(0.0, P, n)
        r = minimize(lambda z: simulate(S, v, z)[1], q0, method="trust-constr",
                     bounds=Bounds(np.zeros(n), np.full(n, P)),
                     constraints=[NonlinearConstraint(lambda z: simulate(S, v, z)[0], 0.0,
                                                      np.inf)],
                     options=dict(maxiter=2000, gtol=1e-8, xtol=1e-12))
        con, cost = simulate(S, v, r.x)
        sols.append(dict(value=cost + fixed_cost, feasible=bool(con.min() >= -1e-6),
                         status=r.status, q=r.x))
    ok = [s_ for s_ in sols if s_["feasible"]]
    best = min(ok, key=lambda s_: s_["value"]) if ok else None
    err = 0.0
    if best is not None:
        h, B = M["h"], v["battery"]["B"]
        for qq in best["q"][:10]:
            for e0 in (0.2 * B, 0.6 * B):
                err = max(err, abs(law(e0, qq, h, B) - integrate(e0, qq, h, B)))
    return dict(solutions=sols, best=None if best is None else best["value"],
                spread=None if not ok else max(s_["value"] for s_ in ok) - best["value"],
                optimistic=lp.fun if lp.status == 0 else None, integration_error=err,
                status="local" if best is not None else "numerical", slots=n)
