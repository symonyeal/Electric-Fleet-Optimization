"""R2: set-partitioning bound by column generation with interior duals (Routing §5; BT §6.1).

Master over routes r with length c_r and visit counts a_ir:
    min sum c_r lam_r   s.t.   sum_r a_ir lam_r = 1  (i in I),   lam_r >= 0.        (R2.1)
lam_r <= 1 holds at every feasible point, since each route visits a customer, but is not
imposed: at the initial columns it binds, and it then makes the dual set unbounded, which pulls
interior duals, and the bound below, far from the optimum (measured on tiny.evrp). For any duals pi
and the exact least reduced cost cbar* over the ng-route set,
    z_LP >= sum_i pi_i + n min(0, cbar*)                                          (R2.2)
(Lagrangean duality, BT §11.4, with the redundant row sum lam <= n). The bound needs exact
pricing, not an exact master; duals come from methods/ipm.py stopped at gap delta, or from the
simplex method of HiGHS. A pricing call stopped by its time limit is not exact and updates
nothing.

R2-RCC (Routing §5a) adds rounded capacity inequalities (Laporte, Nobert and Desrochers 1985),
in the entry form of robust branch-cut-and-price (Fukasawa et al. 2006): for S within I,
    sum_r beta_S(r) lam_r >= kappa(S) = ceil(b(S) / C),                            (R2.3)
beta_S(r) the number of arcs (u, v) of r's customer sequence with u not in S and v in S. Every
partition into feasible elementary routes satisfies (R2.3), since each route serving S enters it,
so z_LP(R2.1, R2.3) <= z*. With multipliers sigma >= 0 the reduced cost becomes
cbar_r = c_r - sum_i a_ir pi_i - sum_S sigma_S beta_S(r): a cost w_uv = sum sigma_S on each arc
entering S, so labeling and its dominance are unchanged, and
    z_LP(R2.1, R2.3) >= sum_i pi_i + sum_S sigma_S kappa(S) + n min(0, cbar*).     (R2.4)
"""

import heapq
import itertools
import math
import time

import numpy as np
import scipy.sparse as sp
from scipy.optimize import Bounds, LinearConstraint, linprog, milp

from checks.certificate import digest, gap_state, provenance, record
from checks.route import replay
from methods.ipm import ipm, standard
from models.paths import paths

VERSION = "R2/1"
RCC = "R2-RCC/1"


def ng_sets(p, nu=8):
    """N_i: customer i and its nu - 1 nearest customers, as bitmasks over positions in I."""
    I, D = p["I"], p["D"]
    pos = {i: k for k, i in enumerate(I)}
    return {i: sum(1 << pos[j] for j in sorted(I, key=lambda j: D[i, j])[:nu]) for i in I}


def price(p, P, pi, ng, labels=None, time_limit=math.inf, tol=1e-9, W=None):
    """Least reduced-cost ng-routes by labeling on the station-path multigraph.

    A label at node i is (cbar, q, y, M): reduced cost, load, charge on leaving i, ng-memory.
    Extending along p in P_ij needs y >= a_p and, at a customer j, j not in M and q + b_j <= C;
    then y' = y - e_ij (direct) or Q - w_p, cbar' = cbar + l_p - pi_j - W_ij, M' = (M & N_j) | {j}.
    W is the arc dual of (R2.4), zero when absent.
    L1 dominates L2 at the same node if cbar1 <= cbar2, q1 <= q2, y1 >= y2 and M1 within M2.
    Labels are processed in order of load, which grows along every extension.

    INPUT   labels ..... None for exact pricing; k keeps the k best labels per node (heuristic)
    OUTPUT  (cbar*, columns, exact): cbar* the least reduced cost over completed routes (exact
            only if exact is True), columns with cbar < 0 sorted by cbar
    """
    o, I, b, C, Q = p["depot"], p["I"], p["b"], p["C"], p["Q"]
    pos = {i: k for k, i in enumerate(I)}
    out = {}
    for (i, _), v in P.items():
        out.setdefault(i, []).extend(v)
    lab = [(0.0, 0.0, Q, 0, -1, None, o)]            # cbar, q, y, M, parent, path, node
    alive, at = [True], {i: [] for i in I}
    heap, best, done, t0 = [(0.0, 0)], math.inf, [], time.perf_counter()
    exact = labels is None
    while heap:
        if time.perf_counter() - t0 > time_limit:
            exact = False
            break
        _, k = heapq.heappop(heap)
        if not alive[k]:
            continue
        cb, q, y, M, _, _, i = lab[k]
        for path in out.get(i, ()):
            _, j, l, a, w, nodes = path
            if y < a - tol:
                continue
            if j == o:
                if i != o:
                    best = min(best, cb + l)
                    if cb + l < -tol:
                        done.append((cb + l, k, path))
                continue
            if M >> pos[j] & 1 or q + b[j] > C + tol:
                continue
            new = (cb + l - pi[j] - (0.0 if W is None else W[i, j]), q + b[j],
                   y - a if len(nodes) == 2 else Q - w,
                   (M & ng[j]) | (1 << pos[j]), k, path, j)
            if any(lab[m][0] <= new[0] + tol and lab[m][1] <= new[1] + tol and
                   lab[m][2] >= new[2] - tol and not lab[m][3] & ~new[3] for m in at[j]):
                continue
            for m in at[j]:
                if new[0] <= lab[m][0] + tol and new[1] <= lab[m][1] + tol and \
                        new[2] >= lab[m][2] - tol and not new[3] & ~lab[m][3]:
                    alive[m] = False
            at[j] = [m for m in at[j] if alive[m]]
            if labels is not None and len(at[j]) >= labels:
                worst = max(at[j], key=lambda m: lab[m][0])
                if lab[worst][0] <= new[0]:
                    continue
                alive[worst] = False
                at[j].remove(worst)
            lab.append(new)
            alive.append(True)
            at[j].append(len(lab) - 1)
            heapq.heappush(heap, (new[1], len(lab) - 1))
    cols, seen = [], set()
    for rc, k, last in sorted(done, key=lambda t: t[0]):
        arcs = [last]
        while lab[k][4] >= 0:
            arcs.append(lab[k][5])
            k = lab[k][4]
        arcs.reverse()
        nodes = [o] + [v for a in arcs for v in a[5][1:]]
        if tuple(nodes) in seen:
            continue
        seen.add(tuple(nodes))
        visits = [a[1] for a in arcs[:-1]]
        cols.append(dict(rc=rc, cost=sum(a[2] for a in arcs), visits=visits, nodes=nodes))
    return best, cols, exact


def initial(p, P):
    """One out-and-back route per customer: the least l1 + l2 over P_0i x P_i0 with charge on
    arrival at i covering the first leg home."""
    o, Q, cols = p["depot"], p["Q"], []
    for i in p["I"]:
        cand = [(p1[2] + p2[2], p1, p2) for p1 in P.get((o, i), []) for p2 in P.get((i, o), [])
                if (Q - p1[4]) >= p2[3] - 1e-9]
        if cand:
            L, p1, p2 = min(cand, key=lambda t: t[0])
            cols.append(dict(cost=L, visits=[i], nodes=[*p1[5], *p2[5][1:]]))
    return cols


def from_routes(p, routes):
    """Columns from exchange-format routes (1-based), at their replayed lengths."""
    cols = []
    for r in routes:
        v = [k - 1 for k in r]
        cols.append(dict(cost=sum(p["D"][a, c] for a, c in itertools.pairwise(v)),
                         visits=[k for k in v if k in set(p["I"])], nodes=v))
    return cols


def seq(p, col):
    """A column's customer sequence 0, visits, 0: the arcs (R2.3) counts."""
    return [p["depot"], *col["visits"], p["depot"]]


def beta(p, S, col):
    """beta_S(r): arcs of r entering S."""
    return sum(u not in S and v in S for u, v in itertools.pairwise(seq(p, col)))


def arc_duals(p, cuts, sigma):
    """W_uv = sum of sigma_S over the cuts S that (u, v) enters."""
    W = np.zeros((len(p["X"]),) * 2)
    for (S, _), s in zip(cuts, sigma):
        e = np.zeros(len(p["X"]))
        e[list(S)] = 1
        W += s * np.outer(1 - e, e)
    return W


def master(p, cols, duals, delta, time_limit=math.inf, cuts=()):
    """Solve (R2.1), with the rows (R2.3) of cuts = [(S, kappa)], over the columns within
    time_limit seconds. OUTPUT f (master objective), pi (duals over nodes), lam, status, sigma
    (cut duals, >= 0). Any pi and sigma >= 0 give a valid bound (R2.4) after exact pricing, so a
    master stopped at its limit still supplies duals."""
    I, m = p["I"], len(cols)
    pos = {i: k for k, i in enumerate(I)}
    r, c = zip(*[(pos[i], k) for k, col in enumerate(cols) for i in col["visits"]])
    A = sp.csr_array((np.ones(len(r)), (r, c)), shape=(len(I), m))
    A.sum_duplicates()
    cost = np.array([col["cost"] for col in cols])
    pi, sigma = np.zeros(len(p["X"])), np.zeros(len(cuts))
    B = sp.csr_array(np.array([[beta(p, S, col) for col in cols] for S, _ in cuts], float)
                     .reshape(len(cuts), m))
    kappa = np.array([k for _, k in cuts], float)
    ub = dict(A_ub=-B, b_ub=-kappa) if cuts else {}
    if duals == "simplex":
        h = linprog(cost, A_eq=A, b_eq=np.ones(len(I)), bounds=(0, None), method="highs-ds",
                    options=dict(time_limit=max(time_limit, 1e-3)), **ub)
        if h.status != 0 or h.eqlin is None:
            return math.inf, pi, None, "limit" if h.status == 1 else "numerical", sigma
        pi[I] = h.eqlin.marginals
        if cuts:
            sigma = np.maximum(0.0, -h.ineqlin.marginals)
        return h.fun, pi, h.x, "optimal", sigma
    s = ipm(*standard(cost, A_eq=A, b_eq=np.ones(len(I)), **ub), delta=delta,
            time_limit=time_limit)
    if s["x"] is None:
        return math.inf, pi, None, s["status"], sigma
    pi[I] = s["y"][:len(I)]
    sigma = np.maximum(0.0, -s["y"][len(I):len(I) + len(cuts)])      # slack row: y <= 0
    return s["f"], pi, s["x"][:m], s["status"], sigma


def separate(p, cols, lam, cuts, add=10, tol=1e-6):
    """Violated (R2.3) by greedy growth (Lysgaard, Letchford and Eglese 2004, §4: the simplest of
    their heuristics). x_uv = sum_r lam_r [(u, v) in r]; from each seed, S grows by the customer
    with the largest flow to and from S, and each S met is tested: the flow entering S,
    y(S) = sum_{u not in S, v in S} x_uv, against kappa(S). OUTPUT up to add new cuts, most
    violated first. O(n^3) per call."""
    I, b, C, X = p["I"], p["b"], p["C"], len(p["X"])
    x = np.zeros((X, X))
    for col, l in zip(cols, lam):
        if l > tol:
            for u, v in itertools.pairwise(seq(p, col)):
                x[u, v] += l
    w = x + x.T
    old, found = {S for S, _ in cuts}, {}
    for i in I:
        S = [i]
        while len(S) < len(I):
            rest = [j for j in I if j not in S]
            S.append(max(rest, key=lambda j: w[S, j].sum()))
            F = frozenset(S)
            k = math.ceil(b[S].sum() / C - tol)
            e = np.ones(X, bool)
            e[S] = False
            v = k - x[np.ix_(e, S)].sum()
            if v > tol and F not in old:
                found[F] = (v, k)
    return [(S, k) for S, (v, k) in sorted(found.items(), key=lambda t: -t[1][0])[:add]]


def colgen(p, duals="ipm", nu=8, eps=1e-6, delta_max=0.1, delta_min=1e-9, D=10.0, add=20,
           labels=10, init_routes=(), max_iter=1000, time_limit=3600.0, price_limit=600.0,
           milp_limit=None, rcc=False):
    """Column generation for (R2.1) with bound (R2.2), and the restricted master as a MILP.
    rcc=True is R2-RCC: at each convergence the master's point is separated for (R2.3), and
    generation resumes with the cuts found, under bound (R2.4); it converges when none is.

    Heuristic pricing (labels per node capped) runs first; exact pricing runs when it finds
    nothing, and only exact pricing updates the bound L. With interior duals the master is
    stopped at relative gap delta_k, delta_{k+1} = max(delta_min, min(delta_max, gap_k / D)),
    gap_k = (f_k - L) / (1 + |f_k|) (the form of Gondzio, Gonzalez-Brevis and Munari's rule;
    the parameters here are this project's). Stops when gap_k <= eps after exact pricing
    found no negative column.

    One deadline, time_limit seconds from the call, covers the run. The restricted MILP is given
    milp_limit seconds (default the lesser of 300 s and a tenth of time_limit), reserved from
    the start; every master and pricing call before it gets at most the time left to the
    deadline less that reserve, and exact pricing at most price_limit of it. The record keeps
    the requested budget and the time actually spent.
    """
    t0 = time.perf_counter()
    milp_limit = min(300.0, 0.1 * time_limit) if milp_limit is None else milp_limit
    left = lambda: max(0.0, time_limit - milp_limit - (time.perf_counter() - t0))
    P, ng, n = paths(p), ng_sets(p, nu), len(p["I"])
    cols = initial(p, P) + from_routes(p, init_routes)
    keys = {tuple(c["nodes"]) for c in cols}
    L, delta, traj, calls, exact_calls = -math.inf, delta_max, [], 0, 0
    converged, f, cuts = False, math.inf, []
    for k in range(1, max_iter + 1):
        if left() <= 0:
            break
        f, pi, lam, st, sigma = master(p, cols, duals, delta if duals == "ipm" else None,
                                       time_limit=left(), cuts=cuts)
        W = arc_duals(p, cuts, sigma) if cuts else None
        _, new, _ = price(p, P, pi, ng, labels=labels, time_limit=left(), W=W)
        calls += 1
        fresh = [c for c in new if tuple(c["nodes"]) not in keys]
        exact = False
        if not fresh and left() > 0:
            cb, new, exact = price(p, P, pi, ng, time_limit=min(price_limit, left()), W=W)
            calls += 1
            exact_calls += 1
            if exact:                                                  # (R2.2), (R2.4)
                L = max(L, pi[p["I"]].sum() + sigma @ np.array([k for _, k in cuts], float)
                        + n * min(0.0, cb))
            fresh = [c for c in new if tuple(c["nodes"]) not in keys]
        for c in fresh[:add]:
            keys.add(tuple(c["nodes"]))
            cols.append(c)
        gap = (f - L) / (1 + abs(f)) if math.isfinite(L) else math.inf
        cut = separate(p, cols[:len(lam)], lam, cuts) if (
            rcc and exact and not fresh and gap <= eps and lam is not None) else []
        traj.append(dict(k=k, f=f, L=L if math.isfinite(L) else None, gap=gap, delta=delta,
                         cols=len(cols), exact=exact, master=st, t=time.perf_counter() - t0,
                         **({"cuts": len(cuts) + len(cut)} if rcc else {})))
        cuts += cut
        if exact and not fresh and gap <= eps and not cut:
            converged = True
            break
        if duals == "ipm":                         # no new column: the master was too loose
            d = delta / 10 if exact and not fresh else delta_max
            delta = max(delta_min, min(d, gap / D) if math.isfinite(gap) else d)
    rest = time_limit - (time.perf_counter() - t0)
    U, routes, rp = (restricted_milp(p, cols, time_limit=rest) if rest > 0
                     else (None, None, None))
    Lf = L if math.isfinite(L) else None
    g = gap_state(U, Lf)
    st = ("optimal" if g == "closed" else "numerical" if g == "crossed"
          else "feasible_limit" if U is not None else "no_incumbent")
    elapsed = time.perf_counter() - t0
    return record("R2", p["name"], st, U=U, L=Lf,
                  validation="replayed" if U is not None else
                  "validation_failed" if rp else "not_available",
                  bound_source="r24_exact_pricing" if rcc else "r22_exact_pricing",
                  solver=dict(code=None, message="converged" if converged else "limit"),
                  elapsed=elapsed,
                  provenance=provenance(p, duals=duals, nu=nu, eps=eps, delta_max=delta_max,
                                        delta_min=delta_min, D=D, labels=labels, add=add,
                                        max_iter=max_iter, time_limit=time_limit,
                                        price_limit=price_limit, milp_limit=milp_limit,
                                        init_routes=len(init_routes),
                                        init_digest=digest(list(init_routes)),
                                        formulation=RCC if rcc else VERSION,
                                        **({"rcc": True} if rcc else {})),
                  **({"cuts": [dict(S=sorted(int(i) for i in S), kappa=k) for S, k in cuts]}
                     if rcc else {}),
                  time_budget=dict(requested=time_limit, loop=time_limit - milp_limit,
                                   milp=milp_limit, spent=elapsed),
                  converged=converged, lp=f, iterations=len(traj), pricing=calls,
                  exact_pricing=exact_calls, columns=len(cols), trajectory=traj,
                  routes=routes, replay=rp)


def restricted_milp(p, cols, time_limit=300.0):
    """Set partitioning over the generated elementary columns: a heuristic upper bound."""
    E = [c for c in cols if len(set(c["visits"])) == len(c["visits"])]
    pos = {i: k for k, i in enumerate(p["I"])}
    r, c = zip(*[(pos[i], k) for k, col in enumerate(E) for i in col["visits"]])
    A = sp.csr_array((np.ones(len(r)), (r, c)), shape=(len(p["I"]), len(E)))
    res = milp([col["cost"] for col in E], constraints=LinearConstraint(A, 1, 1),
               integrality=np.ones(len(E)), bounds=Bounds(0, 1),
               options=dict(time_limit=time_limit))
    if res.x is None:
        return None, None, None
    routes = [[k + 1 for k in E[k]["nodes"]] for k in np.flatnonzero(res.x > 0.5)]
    rp = replay(p, routes)
    return (rp["length"] if rp["ok"] else None), routes, dict(ok=rp["ok"], defects=rp["defects"])
