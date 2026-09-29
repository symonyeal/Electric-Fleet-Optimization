"""Primal-dual path-following method (Vanderbei Ch. 17-19; QP Ch. 24; Algorithms §2-§3).

    min c'x + x'Qx/2   s.t.   Ax = b,   l <= x <= u,        l finite, u_j = inf allowed.

Fixed variables (l_j = u_j) are eliminated first. The rest are shifted to 0 <= x <= U = u - l,
with w = U - x on finite U. With multipliers y, z >= 0 (x >= 0), v >= 0 (w >= 0) the central
path is
    Ax = b,   x + w = U,   A'y + z - v - Qx = c,   XZe = mu e,   WVe = mu e.
Eliminating dz, dw, dv leaves the quasi-definite system (Vanderbei Ch. 19)
    [ -(Q + D + dp I)   A'   ] [dx]   [rho]      D = X^-1 Z + W^-1 V,
    [  A                dd I ] [dy] = [ rp].     rho = rd - X^-1 rxz + W^-1 (rwv - V ru).
"""

import time

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu


def standard(c, A_ub=None, b_ub=None, A_eq=None, b_eq=None, l=None, u=None):
    """min c'x s.t. A_ub x <= b_ub, A_eq x = b_eq, l <= x <= u  ->  (c, A, b, l, u), equality form.

    Slacks s = b_ub - A_ub x are appended with 0 <= s <= b_ub - min_{l<=x<=u} A_ub x, finite
    whenever the box makes it so; (A3) needs finite bounds to be finite.
    """
    c = np.asarray(c, float)
    n = len(c)
    l = np.zeros(n) if l is None else np.asarray(l, float)
    u = np.full(n, np.inf) if u is None else np.asarray(u, float)
    Ai = sp.csr_array(np.zeros((0, n)) if A_ub is None else A_ub, dtype=float)
    Ae = sp.csr_array(np.zeros((0, n)) if A_eq is None else A_eq, dtype=float)
    bi = np.zeros(0) if b_ub is None else np.asarray(b_ub, float)
    be = np.zeros(0) if b_eq is None else np.asarray(b_eq, float)
    Ai.eliminate_zeros()
    lo = Ai.maximum(0) @ l + Ai.minimum(0) @ np.where(np.isinf(u), 1e300, u)
    smax = np.where(lo < -1e299, np.inf, bi - lo)
    mi = len(bi)
    A = sp.block_array([[Ae, None], [Ai, sp.eye_array(mi)]], format="csr")
    if mi == 0:
        A = sp.csr_array(Ae)
    return (np.r_[c, np.zeros(mi)], A, np.r_[be, bi], np.r_[l, np.zeros(mi)], np.r_[u, smax])


def bound(c, Q, A, b, l, u, x, y):
    """Lower bound from any x in [l, u] and any y (A3; A5 for convex Q).

    The Lagrangian L(x) = c'x + x'Qx/2 - y'(Ax - b) is convex, so its tangent at x is a global
    minorant; minimize the tangent over the box. Returns -inf when an infinite bound is needed.
    """
    a = c + Q @ x - A.T @ y
    L = c @ x + x @ (Q @ x) / 2 - y @ (A @ x - b)
    inf = np.isinf(u)
    lo = a * (l - x)
    hi = np.where(a < 0, np.where(inf, -np.inf, a * np.where(inf, 0.0, u - x)), 0.0)
    return L + np.minimum(lo, hi).sum()


def _step(v, dv, eta):
    """Fraction-to-boundary: largest t <= 1 with v + t dv >= (1 - eta) v."""
    neg = dv < 0
    return min(1.0, eta * np.min(-v[neg] / dv[neg])) if neg.any() else 1.0


def ipm(c, A, b, l, u, Q=None, eps=1e-8, delta=None, sigma=0.1, eta=0.9995, kmax=200,
        dp=1e-10, dd=1e-10, trace=False):
    """Primal-dual path following.

    INPUT   c, A, b, l, u, Q .. problem data (A, Q sparse or dense; Q convex)
            eps ............. tolerance of the stopping rule (A2)
            delta ........... stop early once residuals meet eps and the relative gap delta
            sigma, eta ...... centering parameter, fraction to the boundary
            dp, dd .......... primal and dual regularization of the Newton system
    OUTPUT  x, y, a (= c + Qx - A'y), f (objective), L (bound A3/A5), status (optimal,
            feasible_limit, limit, numerical), k, err (primal, dual, gap), stats, trace.
            Cost per iteration: one sparse LU of the (n + m) quasi-definite matrix.
    """
    A = sp.csr_array(A, dtype=float)
    m, N = A.shape
    c, b, l, u = (np.asarray(v, float) for v in (c, b, l, u))
    Q = sp.csr_array((N, N)) if Q is None else sp.csr_array(Q, dtype=float)
    qp = Q.nnz > 0
    J = np.flatnonzero(u - l > 0)                       # free after eliminating fixed x_j
    A1, Q1 = A[:, J], Q[J][:, J]
    b1, c1, U = b - A @ l, (c + Q @ l)[J], (u - l)[J]
    f0 = c @ l + l @ (Q @ l) / 2
    n, B = len(J), np.isfinite(U)
    x = np.where(B, np.minimum(1.0, U / 2), 1.0)
    w = np.where(B, U - x, 1.0)
    z, v, y = np.ones(n), B.astype(float), np.zeros(m)
    nb = max(n + B.sum(), 1)
    st = dict(m=m, n=N, n_free=n, reg=(dp, dd), t_factor=0.0, t_solve=0.0)
    tr, status = [], "limit"

    def xs(x):                                          # restore fixed and shifted x
        X = l.copy()
        X[J] += x
        return X

    for k in range(kmax + 1):
        rp, ru = b1 - A1 @ x, np.where(B, U - x - w, 0.0)
        rd = c1 - A1.T @ y - z + v + Q1 @ x
        g = x @ z + w[B] @ v[B]
        pobj = f0 + c1 @ x + x @ (Q1 @ x) / 2
        dobj = f0 + b1 @ y - U[B] @ v[B] - x @ (Q1 @ x) / 2
        err = (max(np.abs(rp).max(initial=0), np.abs(ru).max(initial=0))
               / (1 + max(np.abs(b1).max(initial=0), np.abs(U[B]).max(initial=0))),
               np.abs(rd).max(initial=0) / (1 + np.abs(c1).max(initial=0)),
               g / (1 + abs(pobj) + abs(dobj)))
        if trace:
            tr.append(dict(k=k, f=pobj, L=bound(c, Q, A, b, l, u, xs(x), y), err=err))
        if err[0] <= eps and err[1] <= eps and err[2] <= eps:
            status = "optimal"
            break
        if delta and err[0] <= eps and err[1] <= eps and err[2] <= delta:
            status = "feasible_limit"
            break
        if not np.isfinite(g) or max(np.abs(x).max(initial=0), np.abs(y).max(initial=0)) > 1e14:
            status = "numerical"
            break
        if k == kmax:
            break
        mu = sigma * g / nb
        rxz, rwv = mu - x * z, np.where(B, mu - w * v, 0.0)
        Wi = np.where(B, 1 / np.where(B, w, 1.0), 0.0)
        D = z / x + Wi * v
        rho = rd - rxz / x + Wi * (rwv - v * ru)
        K = sp.block_array([[-(Q1 + sp.diags_array(D + dp)), A1.T],
                            [A1, sp.diags_array(np.full(m, dd))]], format="csc")
        t = time.perf_counter()
        F = splu(K)
        st["t_factor"] += time.perf_counter() - t
        t = time.perf_counter()
        d = F.solve(np.r_[rho, rp])
        st["t_solve"] += time.perf_counter() - t
        dx, dy = d[:n], d[n:]
        dz = (rxz - z * dx) / x
        dw = np.where(B, ru - dx, 0.0)
        dv = Wi * (rwv - v * dw)
        tp = min(_step(x, dx, eta), _step(w[B], dw[B], eta))
        td = min(_step(z, dz, eta), _step(v[B], dv[B], eta))
        if qp:
            tp = td = min(tp, td)
        x, w = x + tp * dx, np.where(B, w + tp * dw, 1.0)
        y, z, v = y + td * dy, z + td * dz, np.where(B, v + td * dv, 0.0)
    if k:
        st.update(nnz_K=K.nnz, nnz_LU=F.L.nnz + F.U.nnz)
    X = xs(x)
    return dict(x=X, y=y, a=c + Q @ X - A.T @ y, f=c @ X + X @ (Q @ X) / 2,
                L=bound(c, Q, A, b, l, u, X, y), status=status, k=k, err=err, stats=st,
                trace=tr)
