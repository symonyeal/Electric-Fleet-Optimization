"""Primal-dual path-following method (Vanderbei Ch. 17-19; QP Ch. 24; Algorithms §2-§3).

    min c'x + x'Qx/2   s.t.   Ax = b,   l <= x <= u,        l finite, u_j = inf allowed.

Fixed variables (l_j = u_j) are eliminated first. The rest are shifted to 0 <= x <= U = u - l,
with w = U - x on finite U. With multipliers y, z >= 0 (x >= 0), v >= 0 (w >= 0) the central
path is
    Ax = b,   x + w = U,   A'y + z - v - Qx = c,   XZe = mu e,   WVe = mu e.
Eliminating dz, dw, dv leaves the quasi-definite system (Vanderbei Ch. 19)
    [ -(Q + D + dp I)   A'   ] [dx]   [rho]      D = X^-1 Z + W^-1 V,
    [  A                dd I ] [dy] = [ rp].     rho = rd - X^-1 rxz + W^-1 (rwv - V ru).
For an LP, H = D + dp I is diagonal and the normal equations
    (A H^-1 A' + dd I) dy = rp + A H^-1 rho,    dx = H^-1 (A'dy - rho)
are m x m: a dense Cholesky costs O(m^3 + m^2 n) against a sparse LU of order m + n.
"""

import time

import numpy as np
import scipy.sparse as sp
from scipy.linalg import LinAlgError, cho_factor, cho_solve
from scipy.sparse.linalg import splu


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


def _step(v, dv, eta):
    """Fraction-to-boundary: largest t <= 1 with v + t dv >= (1 - eta) v."""
    neg = dv < 0
    return min(1.0, eta * np.min(-v[neg] / dv[neg])) if neg.any() else 1.0


def ipm(c, A, b, l, u, Q=None, eps=1e-8, delta=None, sigma=0.1, eta=0.9995, kmax=200,
        dp=1e-10, dd=1e-10, kkt=None, trace=False, h=None, Jh=None, Hh=None,
        time_limit=float("inf")):
    """Primal-dual path following; with h, for convex programs (Vanderbei Ch. 25).

    INPUT   c, A, b, l, u, Q .. problem data (A, Q sparse or dense; Q convex)
            h, Jh, Hh ....... optional convex constraints h(x) <= 0: values, Jacobian (sparse,
                              one row per constraint), and sum_k lam_k Hessian h_k (sparse)
            eps ............. tolerance of the stopping rule (A2)
            delta ........... stop early once residuals meet eps and the relative gap delta
            sigma, eta ...... centering parameter, fraction to the boundary
            dp, dd .......... primal and dual regularization of the Newton system
            kkt ............. "normal" or "augmented"; default normal for LPs with m <= 3000
            time_limit ...... seconds; at the limit the status is `limit`, as at kmax
    OUTPUT  x, y, lam, a (= c + Qx - A'y + Jh'lam), f (objective), L (bound A3/A5), status
            (optimal, feasible_limit, limit, numerical), k, err (primal, dual, gap), stats,
            trace. Cost per iteration: one sparse LU of the (n + m) quasi-definite matrix.

    Convex constraints get slacks s = -h(x) >= 0 and multipliers lam >= 0 with s lam = mu.
    Eliminating ds and dlam adds Hh + Jh' (lam/s) Jh to the (1,1) block and
    Jh' ((mu - s lam - lam rh) / s) to the right-hand side, where rh = -h(x) - s; steps are
    common to primal and dual and backtrack on the residual merit.
    """
    t_start = time.perf_counter()
    A = sp.csr_array(A, dtype=float)
    m, N = A.shape
    c, b, l, u = (np.asarray(v, float) for v in (c, b, l, u))
    if not np.all(np.isfinite(l)):
        raise ValueError("ipm needs finite lower bounds")
    if (cut := np.flatnonzero(l > u)).size:            # empty box: a proof of infeasibility
        return dict(x=None, y=None, a=None, f=None, L=None, status="infeasible", k=0, err=None,
                    stats=dict(m=m, n=N), trace=[], reason=f"l > u in columns {cut.tolist()}")
    Q = sp.csr_array((N, N)) if Q is None else sp.csr_array(Q, dtype=float)
    nl = h is not None
    qp = Q.nnz > 0 or nl
    J = np.flatnonzero(u - l > 0)                       # free after eliminating fixed x_j
    A1, Q1 = A[:, J], Q[J][:, J]
    b1, c1, U = b - A @ l, (c + Q @ l)[J], (u - l)[J]
    f0 = c @ l + l @ (Q @ l) / 2
    n, B = len(J), np.isfinite(U)
    x = np.where(B, U / 2, 1.0)                        # centered start: every x_j z_j = w_j v_j = 1
    w = np.where(B, U - x, 1.0)
    z, v, y = 1 / x, np.where(B, 1 / w, 0.0), np.zeros(m)
    kkt = kkt or ("normal" if not qp and m <= 3000 else "augmented")
    st = dict(m=m, n=N, n_free=n, reg=(dp, dd), kkt=kkt, t_factor=0.0, t_solve=0.0,
              fallback=0, backtracks=0)
    tr, status = [], "limit"

    def xs(x):                                          # restore fixed and shifted x
        X = l.copy()
        X[J] += x
        return X

    if nl:
        sl = np.maximum(-h(xs(x)), 1.0)                 # slack of h, and its multiplier
        lam = 1 / sl
    else:
        sl = lam = np.zeros(0)
    nb = max(n + B.sum() + len(sl), 1)

    def resid(x, w, y, z, v, sl, lam):
        rp, ru = b1 - A1 @ x, np.where(B, U - x - w, 0.0)
        rd = c1 - A1.T @ y - z + v + Q1 @ x
        rh = np.zeros(0)
        if nl:
            X = xs(x)
            rd = rd + sp.csr_array(Jh(X))[:, J].T @ lam
            rh = -h(X) - sl
        return rp, ru, rd, rh, x @ z + w[B] @ v[B] + sl @ lam

    def merit(r):
        return sum(np.abs(q).max(initial=0) for q in r[:4]) + r[4]

    for k in range(kmax + 1):
        rp, ru, rd, rh, g = R = resid(x, w, y, z, v, sl, lam)
        pobj = f0 + c1 @ x + x @ (Q1 @ x) / 2
        err = (max(np.abs(rp).max(initial=0) / (1 + np.abs(b1).max(initial=0)),    # (A2), with
                   (np.abs(ru[B]) / (1 + U[B])).max(initial=0),                 # each bound row
                   np.abs(rh).max(initial=0) / (1 + np.abs(sl).max(initial=0))),
               np.abs(rd).max(initial=0) * max(1 / (1 + np.abs(c1).max(initial=0)),  # own bound;
                                               np.abs(x).sum() / (1 + abs(pobj))),    # |x'rd| too
               g / (1 + abs(pobj)))
        if trace:
            tr.append(dict(k=k, f=pobj, L=bound(c, Q, A, b, l, u, xs(x), y, h, Jh, lam),
                           err=err))
        if err[0] <= eps and err[1] <= eps and err[2] <= eps:
            status = "optimal"
            break
        if delta and err[0] <= eps and err[1] <= eps and err[2] <= delta:
            status = "feasible_limit"
            break
        if not np.isfinite(g) or max(np.abs(x).max(initial=0), np.abs(y).max(initial=0)) > 1e14:
            status = "numerical"
            break
        if k == kmax or time.perf_counter() - t_start > time_limit:
            break
        mu = sigma * g / nb
        rxz, rwv = mu - x * z, np.where(B, mu - w * v, 0.0)
        Wi = np.where(B, 1 / np.where(B, w, 1.0), 0.0)
        D = z / x + Wi * v
        rho = rd - rxz / x + Wi * (rwv - v * ru)
        H1 = Q1
        if nl:
            X = xs(x)
            Jf = sp.csr_array(Jh(X))[:, J]
            rsl = mu - sl * lam
            H1 = Q1 + sp.csr_array(Hh(X, lam))[J][:, J] + Jf.T @ sp.diags_array(lam / sl) @ Jf
            rho = rho + Jf.T @ ((rsl - lam * rh) / sl)
        t, d = time.perf_counter(), None
        if kkt == "normal":
            Hi = 1 / (D + dp)
            M = (A1 @ sp.diags_array(Hi) @ A1.T).toarray() + dd * np.eye(m)
            try:                                        # a numerical failure falls back
                F = cho_factor(M)
                st["t_factor"] += time.perf_counter() - t
                t = time.perf_counter()
                dy = cho_solve(F, rp + A1 @ (Hi * rho))
                d = np.r_[Hi * (A1.T @ dy - rho), dy]
            except LinAlgError:
                st["fallback"] += 1
        if d is None:
            K = sp.block_array([[-(sp.csr_array(H1) + sp.diags_array(D + dp)), A1.T],
                                [A1, sp.diags_array(np.full(m, dd))]], format="csc")
            F = splu(K)
            st["t_factor"] += time.perf_counter() - t
            t = time.perf_counter()
            d = F.solve(np.r_[rho, rp])
            st.update(nnz_K=K.nnz, nnz_LU=F.L.nnz + F.U.nnz)
        st["t_solve"] += time.perf_counter() - t
        dx, dy = d[:n], d[n:]
        dz = (rxz - z * dx) / x
        dw = np.where(B, ru - dx, 0.0)
        dv = Wi * (rwv - v * dw)
        tp = min(_step(x, dx, eta), _step(w[B], dw[B], eta))
        td = min(_step(z, dz, eta), _step(v[B], dv[B], eta))
        if nl:
            ds = rh - Jf @ dx
            dl = (rsl - lam * ds) / sl
            tp, td = min(tp, _step(sl, ds, eta)), min(td, _step(lam, dl, eta))
        if qp:
            tp = td = min(tp, td)
        if nl:                                          # backtrack on the residual merit
            m0 = merit(R)
            while tp > 1e-12:
                Rn = resid(x + tp * dx, np.where(B, w + tp * dw, 1.0), y + tp * dy,
                           z + tp * dz, np.where(B, v + tp * dv, 0.0), sl + tp * ds,
                           lam + tp * dl)
                if merit(Rn) <= (1 - 1e-4 * tp) * m0:
                    break
                tp /= 2
                st["backtracks"] += 1
            td = tp
            sl, lam = sl + tp * ds, lam + td * dl
        x, w = x + tp * dx, np.where(B, w + tp * dw, 1.0)
        y, z, v = y + td * dy, z + td * dz, np.where(B, v + td * dv, 0.0)
    if kkt == "normal":
        st.update(nnz_factor=m * (m + 1) // 2)
    X = xs(x)
    a = c + Q @ X - A.T @ y + (Jh(X).T @ lam if nl else 0.0)
    return dict(x=X, y=y, lam=lam, a=a, f=c @ X + X @ (Q @ X) / 2,
                L=bound(c, Q, A, b, l, u, X, y, h, Jh, lam), status=status, k=k, err=err,
                stats=st, trace=tr)
