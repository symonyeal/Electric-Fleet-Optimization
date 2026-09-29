"""Outer approximation for convex MINLPs (Algorithms §6; Duran and Grossmann 1986).

    min c'v   s.t.   lo <= Av <= hi,   l <= v <= u,   v_j integer (integ_j = 1),
                     c_k(v) <= 0   (convex, each on a few variables).

The master is the MILP with every c_k replaced by the tangent cuts collected so far,
    c_k(v^) + grad c_k(v^)'(v - v^) <= 0,
which are valid everywhere because c_k is convex; HiGHS's dual bound of the master is therefore a
lower bound L on the MINLP. Each master solution's integers are fixed and the convex subproblem
solved; a solution that passes the independent validation gives an upper bound U. Cuts are added
at the master point and at the subproblem point. The loop stops when U - L is within tolerance,
at a limit, or with status `stall` when the master repeats an assignment and no cut is violated.
A subproblem failure never excludes an assignment: it only adds cuts at the master point.
"""

import time

import numpy as np
import scipy.sparse as sp
from scipy.optimize import Bounds, LinearConstraint, milp


def cut(con, v):
    """Tangent row of con at v: (indices, coefficients, upper bound)."""
    z = v[con["idx"]]
    g = con["grad"](z)
    return con["idx"], g, g @ z - con["f"](z)


def oa(c, A, lo, hi, l, u, integ, cons, subproblem, validate=None, points=(), eps_abs=1e-6,
       eps_rel=1e-6, tol=1e-7, max_iter=100, time_limit=3600.0, master_limit=600.0):
    """Outer approximation.

    INPUT   cons ....... [dict(idx, f, grad)]: c_k(v[idx]) = f(z) <= 0, convex, gradient grad(z)
            subproblem . v_master -> (status, v, value): the convex problem at v_master's integers
            validate ... v -> (ok, U): independent check of a subproblem solution (default
                         accepts it at its value)
            points ..... initial vectors at which to add cuts
    OUTPUT  status (optimal, feasible_limit, no_incumbent, infeasible, stall), U, L, v,
            iterations [(k, L, U, cuts, violation)], cuts, elapsed
    """
    A = sp.csr_array(A)
    rows = []
    for v0 in points:
        for con in cons:
            rows.append(cut(con, np.asarray(v0, float)))
    U, best, L, hist, seen, t0 = np.inf, None, -np.inf, [], set(), time.perf_counter()
    J = np.flatnonzero(integ)
    status = "feasible_limit"
    for k in range(1, max_iter + 1):
        if time.perf_counter() - t0 > time_limit:
            break
        C = [LinearConstraint(A, lo, hi)]
        if rows:
            r_, c_, d_ = [], [], []
            for q, (idx, g, _) in enumerate(rows):
                r_ += [q] * len(idx)
                c_ += list(idx)
                d_ += list(g)
            T = sp.csr_array((d_, (r_, c_)), shape=(len(rows), len(c)))
            C.append(LinearConstraint(T, -np.inf, np.array([b for _, _, b in rows])))
        res = milp(c, constraints=C, integrality=integ, bounds=Bounds(l, u),
                   options=dict(time_limit=master_limit, mip_rel_gap=eps_rel / 10))
        if res.status == 2:
            status = "infeasible" if not np.isfinite(U) else status
            break
        if res.x is None:
            status = "no_incumbent" if not np.isfinite(U) else "feasible_limit"
            break
        L = max(L, getattr(res, "mip_dual_bound", res.fun))
        v = res.x
        viol = max((con["f"](v[con["idx"]]) for con in cons), default=0.0)
        new = [cut(con, v) for con in cons if con["f"](v[con["idx"]]) > tol]
        key = tuple(np.round(v[J]).astype(int))
        st, w, val = subproblem(v)
        if w is not None:
            ok, Uv = validate(w) if validate else (True, val)
            if ok and Uv < U:
                U, best = Uv, w
            new += [cut(con, w) for con in cons]
        hist.append(dict(k=k, L=L, U=U if np.isfinite(U) else None, cuts=len(rows),
                         violation=viol, sub=st))
        if np.isfinite(U) and U - L <= eps_abs + eps_rel * max(1.0, abs(U)):
            status = "optimal"
            break
        if key in seen and viol <= tol:
            status = "stall"
            break
        seen.add(key)
        rows += new
    if not np.isfinite(U) and status == "feasible_limit":
        status = "no_incumbent"
    return dict(status=status, U=U if np.isfinite(U) else None,
                L=L if np.isfinite(L) else None, v=best, iterations=hist, cuts=len(rows),
                elapsed=time.perf_counter() - t0)
