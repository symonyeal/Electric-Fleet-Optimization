"""M1: joint scheduling and charging in connection form (Models §3).

Trips j = 1..n with published times; x_ij = 1 when trip j is the next trip after i on a bus,
x_0j a pull-out from the depot, x_i0 a pull-in. Energy (kWh): a_j on arrival at j's first stop,
y_j on departing it, E_j = kappa km_j the trip, e_ij the deadhead. A bus may charge at j's first
stop, when it is a charging site s(j), in the window of slots t before dep_j, with power p_jt
(battery side, kW) on a plug u_jt; the slot must lie wholly after the predecessor's arrival.
    min  F sum x_0j + c_dh (deadhead km) + sum_s ((f + rho c_b) o_s + a n_s + b h_s + rho pi D_s)
         + rho c_e (Delta/eta) sum p_jt + rho (c_dep/eta) sum_i r_i
with rho = 1 + rider and c_b the utility's basic charge per metered site (tariff(); 1 and 0
when the scenario declares no tariff).
    sum_i x_ij + x_0j = 1,  sum_j x_ij + x_i0 = 1                            (2), (3)
    a_j = y_i - E_i - e_ij  if x_ij = 1;   a_j = s0 B - e_0j  if x_0j = 1     (7), two-sided big-M
    y_j = a_j + Delta sum_t p_jt,   rB <= a_j,   rB + E_j <= y_j <= smax B    (7), (8)
    p_jt <= P u_jt,   u_jt <= x_0j + sum_{i present at t} x_ij                (4)
    sum_j u_jt <= n_s <= nbar o_s,   h_s <= hbar o_s                          (5)
    L_s o_s + sum_j p_jt / eta <= G0_s + h_s,   D_s >= L_s o_s + sum_j p_jt / eta    (6)
      (D_s over the slots of the billing-demand window only, Data §3)
    L_s o_s <= G0_s + h_s,   D_s >= L_s o_s                                    (6), per site
    y_i - E_i - e_i0 >= rB  if x_i0 = 1;   r_i >= s0 B - (y_i - E_i - e_i0)  if x_i0 = 1,  r_i >= 0.

L_s is load on the site's own meter, which exists only when the site opens (its basic charge is
paid per open site): its demand and capacity terms carry o_s and are written once per site, not
only in the slots where some charging column happens to exist. r_i is the energy the depot
restores overnight to bring bus i back to s0 B, an external recovery priced at the depot rate:
a bus returning above s0 B is credited nothing, since the model has no export decision. The
recovery itself (plugs, power, the 22:00-06:00 window, the next day's circulation) is not
modeled, so no schedule is claimed to repeat day after day (Models §3a).

The whole trip's energy is taken at its start, which enforces the reserve conservatively
(Models §1). The per-bus time-space form of the design has the same schedules but a symmetric
bus index; the connection form has none (Models §3 records the change).
"""

import time

import numpy as np

from checks.certificate import provenance, record
from checks.schedule import replay_energy
from data.scenario import billed
from models.milp import Rows, solve, status
from models.transit import compile

VERSION = "M1/2"      # 2: base load on the open site's meter; nonnegative depot restoration


def tariff(co):
    """Electricity tariff terms of a scenario's cost table (Data §3): the multiplier 1 + rider on
    every electricity charge (energy, demand, basic), and the billing-demand window in seconds of
    the day (w0 > w1 wraps across midnight). Absent keys give 1 and the whole day."""
    return (1 + co.get("rider", 0.0), 3600 * co.get("peak_from", 0.0),
            3600 * co.get("peak_to", 24.0))


def instance(c, v):
    """Everything M1 needs from a corridor c and a scenario v: the compiled instance."""
    return compile(c, v)


def rows(c, v, fixed=None, loss=False, inst=None):
    """M1 as data (c, R, lb, ub, integ) with the index maps; fixed = {site: dict(n, h)} fixes the
    infrastructure (sites open). inst is the compiled instance of (c, v), built here if absent.

    loss=True gives the linear rows of M2 (Models §4): grid power g_jt in [0, gbar u_jt] replaces
    p_jt/eta in the grid, peak and energy terms, and the taper (11), p_jt <= P (1 - e_j,t+1 / B),
    is added with e_j,t+1 = a_j + Delta sum_{t' <= t} p_jt'. The convex loss rows (10),
    g_jt >= p_jt/eta + alpha p_jt^2, are returned as index pairs M["loss"] = [(p, g)]: they are
    not linear, and the barrier solver and outer approximation treat them.
    """
    m = inst if inst is not None else compile(c, v)
    v = m["v"]
    n, P, sites, win = m["n"], m["P"], m["sites"], m["win"]
    E, kappa, top, rB, s0B, Pm, eta, dt = (m[k] for k in ("E", "kappa", "top", "rB", "s0B",
                                                         "P_max", "eta", "D"))
    h = dt / 3600
    idx, size, nv = {}, {}, 0

    def var(key, k=1):
        nonlocal nv
        idx[key], size[key] = nv, k
        nv += k
        return idx[key]

    x0, x1, xc = var("x0", n), var("x1", n), var("xc", len(P))
    a, y, r = var("a", n), var("y", n), var("r", n)
    K = [(j, t) for j in sorted(win) for t in win[j]]
    p, u = var("p", len(K)), var("u", len(K))
    g = var("g", len(K)) if loss else None
    so, sn, sh, sd = (var(k, len(sites)) for k in ("o", "n", "h", "D"))
    lb, ub, integ, cost = np.zeros(nv), np.full(nv, np.inf), np.zeros(nv), np.zeros(nv)
    ub[x0:xc + len(P)] = 1
    integ[x0:xc + len(P)] = 1
    lb[a:a + n], ub[a:a + n] = rB, top
    lb[y:y + n], ub[y:y + n] = rB + E, top
    ub[r:r + n] = s0B - rB
    ub[p:p + len(K)], ub[u:u + len(K)], integ[u:u + len(K)] = Pm, 1, 1
    for k, s in enumerate(sites):
        d = v["sites"][s]
        ub[so + k], integ[so + k], ub[sn + k], integ[sn + k] = 1, 1, d["nbar"], 1
        ub[sh + k] = d["hbar"]
        if fixed and s in fixed:
            lb[so + k] = 1
            lb[sn + k] = ub[sn + k] = fixed[s]["n"]
            lb[sh + k] = ub[sh + k] = fixed[s]["h"]
    co = v["cost"]
    ex, w0, w1 = tariff(co)
    cost[x0:x0 + n] = co["F"] + co["deadhead"] * m["km0"]
    cost[x1:x1 + n] = co["deadhead"] * m["km1"]
    cost[xc:xc + len(P)] = co["deadhead"] * m["km_ij"]
    cost[r:r + n] = ex * co["depot_energy"] / eta
    cost[p:p + len(K)] = ex * co["energy"] * h / eta
    alpha = v["charger"].get("alpha", 0.0)
    gbar = Pm / eta + alpha * Pm ** 2
    if loss:
        cost[p:p + len(K)] = 0.0
        cost[g:g + len(K)] = ex * co["energy"] * h
        ub[g:g + len(K)] = gbar
    cost[so:so + len(sites)] = co["site"] + ex * co.get("basic", 0.0)
    cost[sn:sn + len(sites)] = co["plug"]
    cost[sh:sh + len(sites)] = co["upgrade"]
    cost[sd:sd + len(sites)] = ex * co["peak"]
    R = Rows()
    into = [[] for _ in range(n)]
    outof = [[] for _ in range(n)]
    for k, (i, j, _) in enumerate(P):
        into[j].append(xc + k)
        outof[i].append(xc + k)
    for j in range(n):                                                  # (2), (3)
        R.add([x0 + j, *into[j]], [1.0] * (1 + len(into[j])), 1, 1)
        R.add([x1 + j, *outof[j]], [1.0] * (1 + len(outof[j])), 1, 1)
    for k, (i, j, _) in enumerate(P):                                    # (7), connections
        e = kappa * m["km_ij"][k]
        M = top + e
        R.add([a + j, y + i, xc + k], [1.0, -1.0, M], hi=M - E[i] - e)
        R.add([a + j, y + i, xc + k], [1.0, -1.0, -M], lo=-M - E[i] - e)
    for j in range(n):                                                  # (7), pull-outs
        e = kappa * m["km0"][j]
        M = top + e
        R.add([a + j, x0 + j], [1.0, M], hi=M + s0B - e)
        R.add([a + j, x0 + j], [1.0, -M], lo=-M + s0B - e)
    for i in range(n):                                                  # pull-ins
        e = kappa * m["km1"][i]
        M = top + e
        R.add([y + i, x1 + i], [1.0, -M], lo=E[i] + e + rB - M)
        Mr = s0B + e                                    # r_i + y_i >= s0B + E_i + e_i0
        R.add([r + i, y + i, x1 + i], [1.0, 1.0, -Mr], lo=s0B + E[i] + e - Mr)
        R.add([r + i, x1 + i], [1.0, -(s0B - rB)], hi=0)
    pk = {jt: k for k, jt in enumerate(K)}
    for j in range(n):                                                  # y_j = a_j + h sum p
        ks = [p + pk[j, t] for t in win.get(j, [])]
        R.add([y + j, a + j, *ks], [1.0, -1.0, *[-h] * len(ks)], 0, 0)
    pres = {}
    for k, (i, j, _) in enumerate(P):
        pres.setdefault(j, []).append((m["arrive"][i, j], xc + k))
    for (j, t), k in pk.items():                                        # (4)
        R.add([p + k, u + k], [1.0, -Pm], hi=0)
        here = [col for tt, col in pres.get(j, []) if tt <= t * m["D"] + 1e-9]
        R.add([u + k, x0 + j, *here], [1.0, -1.0, *[-1.0] * len(here)], hi=0)
    by = {}
    for (j, t), k in pk.items():
        by.setdefault((m["site"][m["T"][j]["first"]], t), []).append(k)
    for (s, t), ks in sorted(by.items()):                               # (5), (6) per slot
        q = sites.index(s)
        Ls = v["sites"][s]["L"]
        base = ([so + q], [Ls]) if Ls else ([], [])
        R.add([*[u + k for k in ks], sn + q], [1.0] * len(ks) + [-1.0], hi=0)
        gk, w = ([g + k for k in ks], 1.0) if loss else ([p + k for k in ks], 1 / eta)
        R.add([*gk, *base[0], sh + q], [w] * len(ks) + base[1] + [-1.0],
              hi=v["sites"][s]["G0"])
        if billed(t * dt, w0, w1):                                      # billing window
            R.add([*gk, *base[0], sd + q], [w] * len(ks) + base[1] + [-1.0], hi=0)
    for q, s in enumerate(sites):
        d = v["sites"][s]
        R.add([sn + q, so + q], [1.0, -d["nbar"]], hi=0)
        R.add([sh + q, so + q], [1.0, -d["hbar"]], hi=0)
        if d["L"]:                                                      # (6) per site
            R.add([so + q, sh + q], [d["L"], -1.0], hi=d["G0"])
            R.add([so + q, sd + q], [d["L"], -1.0], hi=0)
    pairs = []
    if loss:
        B = m["B"]
        for (j, t), k in pk.items():                                    # (10) bound, (11)
            R.add([g + k, u + k], [1.0, -gbar], hi=0)
            before = [p + pk[j, s_] for s_ in win[j] if s_ <= t]
            R.add([p + k, a + j, *before], [1.0, Pm / B, *[Pm * h / B] * len(before)],
                  hi=Pm)
            pairs.append((p + k, g + k))
    return dict(c=cost, R=R, lb=lb, ub=ub, integ=integ, idx=idx, size=size, K=K, inst=m,
                loss=pairs, alpha=alpha, eta=eta, h=h)


def linear(M):
    """M's linear rows as a LinearConstraint, built once and kept in M."""
    if "A" not in M:
        M["A"] = M["R"].constraint(len(M["c"]))
    return M["A"]


def priority(M):
    """Branching priority for methods/branch.py: scheduling arcs first, then sites and plugs,
    then plug slots. Measured on tiny M1: most-fractional branching alone reached its node limit
    of 10,000 on 4 and 5 trips; with this order the tree certified both, in 105 and 193 nodes."""
    pr, i, s = np.zeros(len(M["c"])), M["idx"], M["size"]
    pr[i["x0"]:i["x0"] + s["x0"] + s["x1"] + s["xc"]] = 2
    pr[i["o"]:i["o"] + s["o"]] = pr[i["n"]:i["n"] + s["n"]] = 1
    return pr


def solution(M, v, x):
    """Duties (trip ids), charging plan {trip id: {slot: kW}} and infrastructure from x."""
    m, idx = M["inst"], M["idx"]
    T, n, P = m["T"], m["n"], m["P"]
    succ = {P[k][0]: P[k][1] for k in range(len(P)) if x[idx["xc"] + k] > 0.5}
    duties = []
    for j in range(n):
        if x[idx["x0"] + j] > 0.5:
            d = [j]
            while d[-1] in succ:
                d.append(succ[d[-1]])
            duties.append([T[k]["id"] for k in d])
    plan = {}
    for k, (j, t) in enumerate(M["K"]):
        if x[idx["p"] + k] > 1e-9:
            plan.setdefault(T[j]["id"], {})[t] = float(x[idx["p"] + k])
    infra = {s: dict(n=round(x[idx["n"] + q]), h=float(x[idx["h"] + q]))
             for q, s in enumerate(m["sites"]) if x[idx["o"] + q] > 0.5}
    return duties, plan, infra


def m1(c, v, name="corridor", fixed=None, time_limit=600.0, gap=1e-6, keep_x=False, inst=None):
    """M1 by HiGHS; U is the cost of the returned schedule as recomputed by the replay, which
    must agree with the model's objective. keep_x adds the solution vector, for the
    fixed-integer subproblems of Phase 8."""
    m = inst if inst is not None else compile(c, v)
    M = rows(c, v, fixed, inst=m)
    t0 = time.perf_counter()
    res, dt = solve(M["c"], M["R"], M["lb"], M["ub"], M["integ"], time_limit, gap)
    s = status(res)
    duties = plan = infra = rp = None
    if res.x is not None:
        duties, plan, infra = solution(M, v, res.x)
        rp = replay_energy(c, v, duties, plan, infra)
    U = rp["cost"] if rp and rp["ok"] else None
    L = getattr(res, "mip_dual_bound", None) if s in ("optimal", "feasible_limit") else None
    return record("M1", name, s, U=U, L=L,
                  validation="replayed" if U is not None else
                  "validation_failed" if rp else "not_available",
                  objective=None if res.x is None else float(res.fun), bound_source="highs_dual",
                  solver=dict(code=int(res.status), message=res.message), elapsed=dt,
                  provenance=provenance(dict(name=name, sha256=c.get("source", {}).get("sha256")),
                                        fixed=fixed, time_limit=time_limit, mip_rel_gap=gap,
                                        formulation=VERSION, corridor=m["corridor"],
                                        scenario=m["scenario"]),
                  fleet=None if duties is None else len(duties), duties=duties, plan=plan,
                  infra=infra, replay=None if rp is None else {k: rp[k] for k in (
                      "ok", "defects", "cost", "parts", "recovery")},
                  variables=len(M["c"]), rows=len(M["R"].lo), wall=time.perf_counter() - t0,
                  nodes=getattr(res, "mip_node_count", None),
                  **({"x": None if res.x is None else res.x.tolist()} if keep_x else {}))
