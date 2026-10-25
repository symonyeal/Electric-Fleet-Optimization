"""Primal-dual path-following method (Vanderbei Ch. 17-19; QP Ch. 24; Algorithms §2-§3).

    min c'x + x'Qx/2   s.t.   Ax = b,   l <= x <= u,        l finite, u_j = inf allowed.

Fixed variables (l_j = u_j) are eliminated first. The rest are shifted to 0 <= x <= U = u - l,
with w = U - x on finite U. With multipliers y, z >= 0 (x >= 0), v >= 0 (w >= 0) the central
path is
    Ax = b,   x + w = U,   A'y + z - v - Qx = c,   XZe = mu e,   WVe = mu e.
Eliminating dz, dw, dv leaves the quasi-definite system (Vanderbei Ch. 19)
    [ -(Q + D + dp I)   A'   ] [dx]   [rho]      D = X^-1 Z + W^-1 V,
    [  A                dd I ] [dy] = [ rp].     rho = rd - X^-1 rxz + W^-1 (rwv - V ru).
The iteration runs in Rust (crates/efo-kernels/src/ipm.rs), which factors this system by a
sparse LDL' in a fill-reducing order chosen once; the reduction, the restoration and the bound
(A3) are here. The cost per iteration is one numerical factorization of order n + m.
"""

import numpy as np
import scipy.sparse as sp

from methods.native import ipm_core


def standard(c, A_ub=None, b_ub=None, A_eq=None, b_eq=None, l=None, u=None):
    """min c'x s.t. A_ub x <= b_ub, A_eq x = b_eq, l <= x <= u  ->  (c, A, b, l, u), equality form.

    Slacks s = b_ub - A_ub x are appended with 0 <= s <= b_ub - min_{l<=x<=u} A_ub x, finite
    whenever the box makes it so; (A3) needs finite bounds to be finite. A negative bound means
    the row cannot hold on the box, and ipm() returns `infeasible`.
    """
    c = np.asarray(c, float)
    n = len(c)
    l = np.zeros(n) if l is None else np.asarray(l, float)
    u = np.full(n, np.inf) if u is None else np.asarray(u, float)
    Ai = sp.csr_array(np.zeros((0, n)) if A_ub is None else A_ub, dtype=float, copy=True)
    Ae = sp.csr_array(np.zeros((0, n)) if A_eq is None else A_eq, dtype=float)
    bi = np.zeros(0) if b_ub is None else np.asarray(b_ub, float)
    be = np.zeros(0) if b_eq is None else np.asarray(b_eq, float)
    Ai.eliminate_zeros()
    inf = np.isinf(u)
    lo = Ai.maximum(0) @ l + Ai[:, ~inf].minimum(0) @ u[~inf]          # min of each row on the box
    unb = np.asarray((Ai[:, inf] < 0).sum(axis=1)).ravel() > 0         # ... -inf through u = inf
    smax = np.where(unb, np.inf, bi - lo)
    mi = len(bi)
    A = sp.block_array([[Ae, None], [Ai, sp.eye_array(mi)]], format="csr")
    if mi == 0:
        A = sp.csr_array(Ae)
    return (np.r_[c, np.zeros(mi)], A, np.r_[be, bi], np.r_[l, np.zeros(mi)], np.r_[u, smax])


def bound(c, Q, A, b, l, u, x, y, h=None, Jh=None, lam=None):
    """Lower bound from any x in [l, u], any y and any lam >= 0 (A3; A5 for convex Q and h).

    The Lagrangian L(x) = c'x + x'Qx/2 - y'(Ax - b) + lam'h(x) is convex, so its tangent at x is
    a global minorant; minimize the tangent over the box. Returns -inf when an infinite bound
    is needed.
    """
    a = c + Q @ x - A.T @ y
    L = c @ x + x @ (Q @ x) / 2 - y @ (A @ x - b)
    if h is not None:
        a = a + Jh(x).T @ lam
        L = L + lam @ h(x)
    inf = np.isinf(u)
    lo = a * (l - x)
    hi = np.where(a < 0, np.where(inf, -np.inf, a * np.where(inf, 0.0, u - x)), 0.0)
    return L + np.minimum(lo, hi).sum()


def ipm(c, A, b, l, u, Q=None, eps=1e-8, delta=None, sigma=0.1, eta=0.9995, kmax=200,
        dp=1e-10, dd=1e-10, trace=False, h=None, Jh=None, Hh=None, time_limit=float("inf")):
    """Primal-dual path following; with h, for convex programs (Vanderbei Ch. 25).

    INPUT   c, A, b, l, u, Q .. problem data (A, Q sparse or dense; Q convex)
            h, Jh, Hh ....... optional convex constraints h(x) <= 0: values, Jacobian (sparse,
                              one row per constraint), and sum_k lam_k Hessian h_k (sparse)
            eps ............. tolerance of the stopping rule (A2)
            delta ........... stop early once residuals meet eps and the relative gap delta
            sigma ........... centering parameter; None selects Mehrotra's predictor-corrector
                              (LP and QP; with h, sigma = 0.1), which takes a fifth of the
                              iterations but ends so close to complementarity that a reduced
                              cost on a column without upper bound can fall below zero by the
                              dual residual, and (A3) is then -inf: use it for the point only
            eta ............. fraction to the boundary
            dp, dd .......... primal and dual regularization of the Newton system
            time_limit ...... seconds; at the limit the status is `limit`, as at kmax
    OUTPUT  x, y, lam, a (= c + Qx - A'y + Jh'lam), f (objective), L (bound A3/A5), status
            (optimal, feasible_limit, limit, numerical, infeasible), k, err (primal, dual, gap),
            stats, trace [(k, f, L, err)].

    Convex constraints get slacks s = -h(x) >= 0 and multipliers lam >= 0 with s lam = mu.
    Eliminating ds and dlam adds Hh + Jh' (lam/s) Jh to the (1,1) block and
    Jh' ((mu - s lam - lam rh) / s) to the right-hand side, where rh = -h(x) - s; steps are
    common to primal and dual and backtrack on the residual merit.
    """
    A = sp.csr_array(A, dtype=float)
    m, N = A.shape
    c, b, l, u = (np.asarray(v, float) for v in (c, b, l, u))
    if not np.all(np.isfinite(l)):
        raise ValueError("ipm needs finite lower bounds")
    if (cut := np.flatnonzero(l > u)).size:            # empty box: a proof of infeasibility
        return dict(x=None, y=None, a=None, f=None, L=None, status="infeasible", k=0, err=None,
                    stats=dict(m=m, n=N), trace=[], reason=f"l > u in columns {cut.tolist()}")
    Q = sp.csr_array((N, N)) if Q is None else sp.csr_array(Q, dtype=float)
    J = np.flatnonzero(u - l > 0)                       # free after eliminating fixed x_j
    A1, Q1 = A[:, J].tocsc(), Q[J][:, J].tocsc()
    b1, c1, U = b - A @ l, (c + Q @ l)[J], (u - l)[J]

    def xs(x):                                          # restore fixed and shifted x
        X = l.copy()
        X[J] += x
        return X

    def coo(M):
        M = sp.coo_array(M)
        return M.row.astype(np.int64), M.col.astype(np.int64), M.data.astype(float)

    nl = {}
    if h is not None:
        nl = dict(h=lambda x: np.asarray(h(xs(x)), float),
                  jh=lambda x: coo(sp.csr_array(Jh(xs(x)))[:, J]),
                  hh=lambda x, lam: coo(sp.csr_array(Hh(xs(x), lam))[J][:, J]))
    ix = lambda M: (M.indptr.astype(np.int64), M.indices.astype(np.int64), M.data)
    r = ipm_core(m, len(J), *ix(A1), b1, c1, U, *ix(Q1), c @ l + l @ (Q @ l) / 2, **nl, eps=eps,
                 delta=delta, sigma=sigma, eta=eta, kmax=kmax, dp=dp, dd=dd,
                 time_limit=time_limit, trace=trace)
    X, y, lam = xs(r["x"]), r["y"], r["lam"]
    a = c + Q @ X - A.T @ y + (Jh(X).T @ lam if h is not None else 0.0)
    tr = [dict(k=t["k"], f=t["f"], L=bound(c, Q, A, b, l, u, xs(t["x"]), t["y"], h, Jh, t["lam"]),
               err=t["err"]) for t in r["trace"]]
    return dict(x=X, y=y, lam=lam, a=a, f=c @ X + X @ (Q @ X) / 2,
                L=bound(c, Q, A, b, l, u, X, y, h, Jh, lam), status=r["status"], k=r["k"],
                err=r["err"], stats=dict(r["stats"], m=m, n=N, n_free=len(J), reg=(dp, dd)),
                trace=tr)
