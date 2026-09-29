"""Educational branch-and-bound with interior-point node LPs (Algorithms §4; Vanderbei Ch. 23;
BT §11.2).

    min c'v   s.t.   lo <= Av <= hi,   l <= v <= u,   v_j integer where integ_j = 1.

Each node solves its LP relaxation by methods/ipm.py (possibly stopped early at gap delta) or by
HiGHS's interior-point method, and takes as its bound the maximum of its parent's bound and
(A3), which is valid however accurately the node was solved. A node is pruned only for a
certified infeasibility, a bound within tolerance of the incumbent, or integrality. A node the
textbook method cannot resolve is classified by highs-ds; if that fails too it stays open with
its inherited bound, so the reported gap stays open.
"""

import heapq
import math
import time
from collections import Counter

import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog

from methods.ipm import bound, ipm, standard


def split(A, lo, hi):
    """lo <= Av <= hi  ->  A_ub v <= b_ub, A_eq v = b_eq."""
    A, lo, hi = sp.csr_array(A, dtype=float), np.asarray(lo, float), np.asarray(hi, float)
    eq = np.isfinite(lo) & np.isfinite(hi) & (lo == hi)
    up, dn = np.isfinite(hi) & ~eq, np.isfinite(lo) & ~eq
    return sp.vstack([A[up], -A[dn]], format="csr"), np.r_[hi[up], -lo[dn]], A[eq], lo[eq]


def node(c, Aub, bub, Aeq, beq, l, u, lp, delta=None):
    """(status, v, L) of the node LP; L is a valid lower bound on it (A3)."""
    n = len(c)
    S = standard(c, Aub, bub, Aeq, beq, l, u)
    if lp == "ipm":
        r = ipm(*S, delta=delta)
        if r["status"] in ("optimal", "feasible_limit", "infeasible"):
            return r["status"], None if r["x"] is None else r["x"][:n], (
                math.inf if r["status"] == "infeasible" else r["L"])
    h = linprog(c, A_ub=Aub if Aub.shape[0] else None, b_ub=bub if Aub.shape[0] else None,
                A_eq=Aeq if Aeq.shape[0] else None, b_eq=beq if Aeq.shape[0] else None,
                bounds=list(zip(l, u)), method="highs-ipm" if lp == "highs-ipm" else "highs-ds")
    if h.status == 2:
        return "infeasible", None, math.inf
    if h.status != 0:
        return "numerical", None, -math.inf
    cs, As, bs, ls, us = S
    y = np.r_[h.eqlin.marginals if Aeq.shape[0] else [],
              h.ineqlin.marginals if Aub.shape[0] else []]
    xs = np.clip(np.r_[h.x, bub - Aub @ h.x], ls, us)
    return "optimal", h.x, bound(cs, sp.csr_array((len(cs), len(cs))), As, bs, ls, us, xs, y)


def bnb(c, A, lo, hi, l, u, integ, lp="ipm", validate=None, delta=None, eps_abs=1e-6,
        eps_rel=1e-6, tol_int=1e-6, node_limit=10000):
    """Best-first branch-and-bound, most-fractional branching, lexicographic ties.

    INPUT   lp ........ "ipm" (methods/ipm.py) or "highs-ipm" for node LPs
            validate .. v -> (ok, U): an independent check of an integral candidate; the default
                        accepts it at c'v
            delta ..... stop node IPMs early at relative gap delta (their bounds stay valid)
    OUTPUT  status, U, L (global lower bound), v, nodes, pruned (by reason), trajectory
            [(nodes, L, U)], inexact (bound and box of each early-stopped node), unresolved,
            rejected
    """
    c, l, u = (np.asarray(x, float) for x in (c, l, u))
    J = np.flatnonzero(integ)
    Aub, bub, Aeq, beq = split(A, lo, hi)
    tol = lambda U: eps_abs + eps_rel * max(1.0, abs(U)) if math.isfinite(U) else 0.0
    U, best, heap, seq = math.inf, None, [(-math.inf, 0, l, u)], 1
    nodes, pruned, traj, inexact, unresolved, rejected = 0, Counter(), [], [], [], 0
    t0 = time.perf_counter()
    while heap and nodes < node_limit:
        Lp, _, ln, un = heapq.heappop(heap)
        if Lp >= U - tol(U):
            pruned["bound"] += 1
            continue
        nodes += 1
        st, v, L = node(c, Aub, bub, Aeq, beq, ln, un, lp, delta)
        if st == "numerical":
            st, v, L = node(c, Aub, bub, Aeq, beq, ln, un, "highs-ds")
        if st == "infeasible":
            pruned["infeasible"] += 1
        elif st not in ("optimal", "feasible_limit"):
            unresolved.append(Lp)
        else:
            if st == "feasible_limit":
                inexact.append(dict(L=L, l=ln, u=un))
            L = max(L, Lp)
            f = v[J] - np.floor(v[J])
            frac = np.minimum(f, 1 - f)
            if L >= U - tol(U):
                pruned["bound"] += 1
            elif frac.size == 0 or frac.max() <= tol_int:
                l2, u2 = ln.copy(), un.copy()
                l2[J] = u2[J] = np.round(v[J])
                _, v2, _ = node(c, Aub, bub, Aeq, beq, l2, u2, lp)
                ok, Uv = (validate(v2) if validate else (True, c @ v2)) if v2 is not None else (
                    False, None)
                rejected += not ok
                if ok and Uv < U:
                    U, best = Uv, v2
                pruned["integral"] += 1
            else:
                k = J[np.argmax(frac)]                          # most fractional, first on ties
                ua, lb_ = un.copy(), ln.copy()
                ua[k], lb_[k] = math.floor(v[k]), math.ceil(v[k])
                for lc, uc in ((ln, ua), (lb_, un)):
                    heapq.heappush(heap, (L, seq, lc, uc))
                    seq += 1
        open_ = [h[0] for h in heap] + unresolved
        traj.append((nodes, min(open_ + [U]) if open_ else U, U))
    open_ = [h[0] for h in heap if h[0] < U - tol(U)] + unresolved
    Lg = min(open_ + [U]) if open_ else U
    if math.isfinite(U):
        status = "optimal" if U - Lg <= tol(U) else "feasible_limit"
    else:
        status = "no_incumbent" if open_ or rejected else "infeasible"
    return dict(status=status, U=U if math.isfinite(U) else None,
                L=Lg if math.isfinite(Lg) else None, v=best, nodes=nodes, pruned=dict(pruned),
                trajectory=traj, inexact=inexact, unresolved=len(unresolved), rejected=rejected,
                elapsed=time.perf_counter() - t0)
