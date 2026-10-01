"""Educational branch-and-bound with interior-point node LPs (Algorithms §4; Vanderbei Ch. 23;
BT §11.2).

    min c'v   s.t.   lo <= Av <= hi,   l <= v <= u,   v_j integer where integ_j = 1.

Each node solves its LP relaxation by methods/ipm.py (possibly stopped early at gap delta) or by
HiGHS's interior-point method, and takes as its bound the maximum of its parent's bound and
(A3), which is valid however accurately the node was solved. A node is pruned only for a
certified infeasibility, a bound within tolerance of the incumbent, or as solved: its LP point
looks integral (every fraction within tol_int), the integers fixed at their rounded values give
a feasible point that the independent check accepts at a value agreeing with c'v, and that value
meets the node's bound. A node the textbook method cannot resolve is classified by highs-ds; if
that fails too it stays open with its inherited bound, so the reported gap stays open.

An integral-looking node that is not solved is never discarded. If some integer value is not
exactly integral, a fraction below tol_int was hiding the optimum (x = 1e-7 at cost 1e8 is worth
10): the node branches on its most fractional variable, however small the fraction. If every
value is exactly integral and the check still fails, the node's bound is kept as unresolved, so
the gap stays open and no other feasible set is searched in its place. The tree is an
educational method (Algorithms §4): its results support a published certificate only through
that contract.
"""

import heapq
import math
import time
from collections import Counter

import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog

from checks.certificate import gap_state
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


def primal(v, A, lo, hi, l, u, J, t=1e-7):
    """v satisfies lo <= Av <= hi and l <= v <= u within t (1 + |side|) and is integral on J:
    the default independent check of a candidate, written from the problem data alone."""
    Av = A @ v
    near = lambda a, b: np.all(a <= b + t * (1 + np.abs(b)))
    return bool(near(lo, Av) and near(Av, hi) and near(l, v) and near(v, u)
                and np.all(v[J] == np.round(v[J])))


def bnb(c, A, lo, hi, l, u, integ, lp="ipm", validate=None, delta=None, eps_abs=1e-6,
        eps_rel=1e-6, tol_int=1e-6, node_limit=10000, priority=None):
    """Branch-and-bound: depth-first until the first incumbent (the child nearer the LP value
    first), best-first after; branching on the fractional variable of highest priority, then
    most fractional, then lowest index.

    INPUT   lp ........ "ipm" (methods/ipm.py) or "highs-ipm" for node LPs
            validate .. v -> (ok, U): an independent check of an integral candidate; the default
                        checks rows, bounds and integrality and takes U = c'v
            delta ..... stop node IPMs early at relative gap delta (their bounds stay valid; an
                        integral-looking node is re-solved exactly before it is judged)
            priority .. per variable; higher is branched first (default: all equal)
    OUTPUT  status (optimal, feasible_limit, no_incumbent, validation_failed, infeasible), U,
            L (global lower bound), v, nodes, pruned (by reason), trajectory [(nodes, L, U)],
            inexact (bound and box of each early-stopped node), unresolved (nodes whose bound is
            kept open), rejected (candidates refused), hidden (branchings on a fraction within
            tol_int)
    """
    c, l, u = (np.asarray(x, float) for x in (c, l, u))
    J = np.flatnonzero(integ)
    Aub, bub, Aeq, beq = split(A, lo, hi)
    A0, lo0, hi0 = sp.csr_array(A, dtype=float), np.asarray(lo, float), np.asarray(hi, float)
    check = validate or (lambda w: (primal(w, A0, lo0, hi0, l, u, J), float(c @ w)))
    tol = lambda U: eps_abs + eps_rel * max(1.0, abs(U)) if math.isfinite(U) else 0.0
    pr = np.zeros(len(c)) if priority is None else np.asarray(priority, float)
    U, best, heap, dive, seq = math.inf, None, [], [(-math.inf, 0, l, u)], 1
    nodes, pruned, traj, inexact, unresolved, rejected, hidden = 0, Counter(), [], [], [], 0, 0
    t0 = time.perf_counter()

    def branch(k, v, L, ln, un):
        nonlocal seq
        ua, lb_ = un.copy(), ln.copy()
        ua[k], lb_[k] = math.floor(v[k]), math.ceil(v[k])
        kids = [(ln, ua), (lb_, un)]
        if v[k] - math.floor(v[k]) >= 0.5:              # nearer child popped first
            kids.reverse()
        for lc, uc in kids[::-1]:                     # a stack pops the nearer child
            if math.isfinite(U):
                heapq.heappush(heap, (L, seq, lc, uc))
            else:
                dive.append((L, seq, lc, uc))
            seq += 1

    def pick(F, frac):
        return J[F[np.lexsort((F, -frac[F], -pr[J[F]]))[0]]]

    def fractions(v):
        f = v[J] - np.floor(v[J])
        return np.minimum(f, 1 - f)

    while (heap or dive) and nodes < node_limit:
        if dive and math.isfinite(U):                   # first incumbent: switch to best-first
            for nd in dive:
                heapq.heappush(heap, nd)
            dive = []
        Lp, _, ln, un = dive.pop() if dive else heapq.heappop(heap)
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
            frac = fractions(v)
            if L >= U - tol(U):
                pruned["bound"] += 1
            elif frac.size == 0 or frac.max() <= tol_int:
                if st == "feasible_limit":              # judge the node on its exact LP
                    st2, w, L2 = node(c, Aub, bub, Aeq, beq, ln, un, lp)
                    if st2 == "optimal":
                        v, L = w, max(L, L2)
                        frac = fractions(v)
                l2, u2 = ln.copy(), un.copy()
                l2[J] = u2[J] = np.round(v[J])
                st2, v2, _ = node(c, Aub, bub, Aeq, beq, l2, u2, lp)
                ok, Uv = check(v2) if v2 is not None and st2 == "optimal" else (False, None)
                if ok and (Uv is None or abs(c @ v2 - Uv) > tol(Uv)):
                    ok = False                          # the check and c'v disagree
                rejected += not ok
                if ok and Uv < U:
                    U, best = Uv, v2
                if ok and Uv <= L + tol(Uv):
                    pruned["integral"] += 1             # solved: the node bound is met
                elif L >= U - tol(U):
                    pruned["bound"] += 1
                elif (F := np.flatnonzero(frac > 0)).size:
                    hidden += 1                         # a fraction within tol_int: branch on it
                    branch(pick(F, frac), v, L, ln, un)
                else:
                    unresolved.append(L)                # exactly integral, refused: keep L
            else:
                branch(pick(np.flatnonzero(frac > tol_int), frac), v, L, ln, un)
        open_ = [h[0] for h in heap] + [d[0] for d in dive] + unresolved
        traj.append((nodes, min(open_ + [U]) if open_ else U, U))
    open_ = [h[0] for h in heap + dive if h[0] < U - tol(U)] + unresolved
    Lg = min(open_ + [U]) if open_ else U
    if math.isfinite(U):
        status = "optimal" if gap_state(U, Lg, eps_abs, eps_rel) == "closed" else "feasible_limit"
    elif rejected and not (heap or dive):
        status = "validation_failed"
    else:
        status = "no_incumbent" if open_ else "infeasible"
    return dict(status=status, U=U if math.isfinite(U) else None,
                L=Lg if math.isfinite(Lg) else None, v=best, nodes=nodes, pruned=dict(pruned),
                trajectory=traj, inexact=inexact, unresolved=len(unresolved), rejected=rejected,
                hidden=hidden, elapsed=time.perf_counter() - t0)
