# The textbook primal-dual method (Algorithms §2-§3; Vanderbei Ch. 17-19, 24) against HiGHS,
# Vanderbei's examples, and exact enumeration.

import itertools

import numpy as np
import pytest
from scipy.optimize import linprog

from methods.ipm import ipm, standard


def rand_lp(seed, me=3, mi=4, n=10):
    """A feasible LP with finite box: equalities through a random interior point x0."""
    g = np.random.default_rng(seed)
    x0, u = g.uniform(0.2, 0.8, n), g.uniform(1, 3, n)
    Ae, Ai = g.normal(size=(me, n)), g.normal(size=(mi, n))
    return g.normal(size=n), Ai, Ai @ x0 + g.uniform(0, 1, mi), Ae, Ae @ x0, np.zeros(n), u


def ds(c, Ai, bi, Ae, be, l, u):
    return linprog(c, A_ub=Ai, b_ub=bi, A_eq=Ae, b_eq=be, bounds=list(zip(l, u)),
                   method="highs-ds")


def test_vanderbei_2_1():
    """max 5x1 + 4x2 + 3x3 s.t. (2.1): the optimum 13 at x = (2, 0, 1)."""
    r = ipm(*standard(-np.array([5.0, 4, 3]), [[2, 3, 1], [4, 1, 2], [3, 4, 2]], [5, 11, 8]))
    assert r["status"] == "optimal"
    assert r["f"] == pytest.approx(-13, abs=1e-6)
    assert r["x"][:3] == pytest.approx([2, 0, 1], abs=1e-6)


@pytest.mark.parametrize("seed", range(20))
def test_random_lps_agree_with_highs_ds(seed):
    p = rand_lp(seed)
    z = ds(*p).fun
    r = ipm(*standard(*p))
    assert r["status"] == "optimal" and r["f"] == pytest.approx(z, rel=1e-6, abs=1e-6)


def test_fixed_variables_are_removed():
    c, Ai, bi, Ae, be, l, u = rand_lp(3)
    l[[1, 4]] = u[[1, 4]] = [0.5, 0.0]
    r = ipm(*standard(c, Ai, bi, Ae, be, l, u))
    assert r["x"][[1, 4]].tolist() == [0.5, 0.0]
    assert r["f"] == pytest.approx(ds(c, Ai, bi, Ae, be, l, u).fun, rel=1e-6, abs=1e-6)


@pytest.mark.parametrize("seed", range(10))
def test_bound_at_every_iterate(seed):
    """(A3) holds for any y, so it holds at every iterate, converged or not."""
    p = rand_lp(seed)
    z = ds(*p).fun
    r = ipm(*standard(*p), trace=True)
    L = [t["L"] for t in r["trace"]]
    assert max(L) <= z + 1e-7 * (1 + abs(z)) and L[-1] == pytest.approx(z, rel=1e-6, abs=1e-6)


def test_vanderbei_infeasible_and_unbounded():
    """Vanderbei §1.1 (p. 7): neither ends optimal (Algorithms §3)."""
    r = ipm(*standard([-5.0, -4], [[1, 1], [-2, -2]], [2, -9]))
    assert r["status"] in {"numerical", "limit"}
    r = ipm(*standard([-1.0, 4], [[-2, 1], [-1, -2]], [-1, -2]))
    assert r["status"] in {"numerical", "limit"}


def test_early_termination_returns_interior_duals():
    p = rand_lp(7)
    z = ds(*p).fun
    full, r = ipm(*standard(*p)), ipm(*standard(*p), delta=1e-2)
    assert r["status"] == "feasible_limit" and 1e-8 < r["err"][2] <= 1e-2
    assert r["k"] < full["k"] and r["L"] <= z + 1e-9
    assert np.abs(r["y"] - full["y"]).max() > 1e-6          # not yet the optimal duals


def test_interior_of_the_optimal_face():
    """min x1 + x2, x1 + x2 >= 1 on [0,2]^2: the method ends inside the face, not at a vertex."""
    r = ipm(*standard([1.0, 1.0], [[-1, -1]], [-1], l=[0, 0], u=[2, 2]))
    assert r["status"] == "optimal" and min(r["x"][:2]) > 0.1


def test_statistics():
    s = ipm(*standard(*rand_lp(0)), kkt="augmented")["stats"]
    assert (s["m"], s["n"], s["n_free"]) == (7, 14, 14) and s["nnz_LU"] >= s["nnz_K"] > 0
    assert s["t_factor"] > 0 and s["reg"] == (1e-10, 1e-10)
    s = ipm(*standard(*rand_lp(0)))["stats"]
    assert s["kkt"] == "normal" and s["nnz_factor"] == 28 and s["fallback"] == 0


@pytest.mark.parametrize("seed", range(5))
def test_nonzero_lower_bounds(seed):
    """Shifted variables are restored as l + x (a regression the l = 0 tests could not see)."""
    c, Ai, bi, Ae, be, l, u = rand_lp(seed)
    l = np.random.default_rng(seed).uniform(-1, 0.1, len(l))
    r = ipm(*standard(c, Ai, bi, Ae, be, l, u))
    assert r["f"] == pytest.approx(ds(c, Ai, bi, Ae, be, l, u).fun, rel=1e-6, abs=1e-6)
    assert np.all(r["x"][:len(l)] >= l - 1e-9)


def enum_qp(Q, c, A, b, l, u):
    """Exact min c'x + x'Qx/2, Ax = b, l <= x <= u, Q positive definite, by active sets.

    Each variable sits at l, at u, or is free; the free block solves its KKT system. The optimum
    is a primal-feasible candidate, so the least feasible candidate objective is optimal.
    """
    n, best = len(c), np.inf
    for s in itertools.product((0, 1, 2), repeat=n):
        s = np.array(s)
        x = np.where(s == 0, l, u).astype(float)
        F = np.flatnonzero(s == 2)
        K = np.block([[Q[np.ix_(F, F)], A[:, F].T], [A[:, F], np.zeros((len(b), len(b)))]])
        rhs = np.r_[-c[F] - Q[np.ix_(F, s != 2)] @ x[s != 2], b - A[:, s != 2] @ x[s != 2]]
        sol = np.linalg.lstsq(K, rhs, rcond=None)[0]
        x[F] = sol[:len(F)]
        if np.allclose(A @ x, b, atol=1e-9) and np.all(x >= l - 1e-9) and np.all(x <= u + 1e-9):
            best = min(best, c @ x + x @ Q @ x / 2)
    return best


@pytest.mark.parametrize("seed", range(10))
def test_convex_qp_agrees_with_enumeration(seed):
    g = np.random.default_rng(seed)
    n = 5
    M = g.normal(size=(n, n))
    Q, c, A = M @ M.T + 0.1 * np.eye(n), g.normal(size=n) * 3, g.normal(size=(1, n))
    l, u = np.zeros(n), np.ones(n)
    b = A @ g.uniform(0.2, 0.8, n)
    r = ipm(c, A, b, l, u, Q=Q)
    assert r["status"] == "optimal" and max(r["err"]) <= 1e-8
    assert r["f"] == pytest.approx(enum_qp(Q, c, A, b, l, u), abs=1e-7)
    assert r["L"] <= r["f"] + 1e-9 and r["L"] == pytest.approx(r["f"], abs=1e-6)


# Counterexamples found by the Phase 2 verifier: one large finite bound made the stopping rule
# vacuous, and standard() turned u = inf into a finite slack bound.

def not_optimal(*a, **k):
    return ipm(*standard(*a, **k))["status"] != "optimal"


@pytest.mark.parametrize("big", [1e4, 1e6, 1e8, 1e12])
def test_large_bound_does_not_hide_infeasibility(big):
    assert not_optimal([1.0, 1, 0], [[-1, -1, 0], [0, 0, 1]], [-3, big],
                       l=np.zeros(3), u=np.array([1, 1, big]))
    assert not_optimal([1.0, 1, 0], A_eq=[[1, 1, 0]], b_eq=[-1e-2], l=np.zeros(3),
                       u=np.array([big, big, big]))


@pytest.mark.parametrize("big", [1e4, 1e6, 1e8])
@pytest.mark.parametrize("t", [1e-2, 1e-4, 1e-6])
@pytest.mark.parametrize("c", [[1.0, 1, 0], [-1.0, 2, 0]])
def test_near_infeasible_with_a_large_bound(big, t, c):
    """x1 + x2 >= 2 - t on [0,1]^2 beside x3 <= big: feasible, and its optimum must be exact."""
    a = ([[-1, -1, 0], [0, 0, 1]], [-(2 - t), big])
    l, u = np.zeros(3), np.array([1, 1, big])
    z = linprog(c, A_ub=a[0], b_ub=a[1], bounds=list(zip(l, u)), method="highs-ds").fun
    r = ipm(*standard(c, *a, l=l, u=u))
    assert r["status"] == "optimal" and r["f"] == pytest.approx(z, abs=1e-6)


def test_unbounded_column_keeps_its_slack_unbounded():
    """x1 - 0.05 x2 <= 5 with x2 unbounded above: the slack has no finite upper bound."""
    c, A, b, l, u = standard([-1.0, 0], [[1, -0.05]], [5], [[1, 1]], [1])
    assert np.isinf(u[2])
    r = ipm(c, A, b, l, u)
    assert r["status"] == "optimal" and r["f"] == pytest.approx(-1, abs=1e-7)


def test_empty_box_is_infeasible_and_infinite_lower_bound_is_an_error():
    assert ipm([1.0], np.zeros((0, 1)), [], [2.0], [1.0])["status"] == "infeasible"
    r = ipm(*standard([1.0, 1], [[-1, -1]], [-3], l=[0, 0], u=[1, 1]))     # x1 + x2 >= 3 on [0,1]^2
    assert r["status"] == "infeasible" and "2" in r["reason"]
    with pytest.raises(ValueError):
        ipm([1.0], np.zeros((0, 1)), [], [-np.inf], [1.0])


INF = np.inf
CASES = {   # name: (c, A_ub, b_ub, A_eq, b_eq, l, u); cases from the Phase 2 verification
    "Vanderbei ex. 3.1 (degenerate, p. 35)": ([-10.0, 57, 9, 24], [[0.5, -5.5, -2.5, 9],
                                             [0.5, -1.5, -0.5, 1], [1, 0, 0, 0]], [0, 0, 1],
                                             None, None, None, None),
    "two-variable, optimum 31": ([-4.0, -3], [[1, -1], [2, -1], [0, 1]], [1, 3, 5],
                                 None, None, None, None),
    "degenerate vertex": ([0.0, -2], [[0, 1], [1, 1]], [0, 1], None, None, None, None),
    "duplicate equality rows": ([1.0, 2, 3], None, None, [[1, 1, 1], [1, 1, 1]], [1, 1],
                                np.zeros(3), np.full(3, 5.0)),
    "box of width 1e-9": ([1.0, -1, 2], [[1, 1, 1]], [1], None, None, np.zeros(3),
                          np.full(3, 1e-9)),
    "box of width 1e-7, l != 0": ([1.0, -1, 2], [[1, 1, 1]], [10], None, None,
                                  np.array([3, -2, 1.0]), np.array([3, -2, 1.0]) + 1e-7),
    "all fixed, feasible": ([1.0, -1, 2], [[1, 1, 1]], [5], None, None, np.array([1, 0, 1.0]),
                            np.array([1, 0, 1.0])),
    "all fixed, infeasible equality": ([1.0, -1, 2], None, None, [[1, 1, 1]], [1],
                                       np.array([1, 0, 1.0]), np.array([1, 0, 1.0])),
    "u = inf, l < 0": ([1.0, 1], [[-1, -1]], [-1], None, None, np.array([-5, -3.0]), None),
    "u = inf mixed": ([1.0, -1, 0.5], [[1, 1, 0], [0, 1, -1]], [4, 1], None, None,
                      np.array([-2, -1, 0.0]), np.array([INF, INF, 3])),
    "u = 1e10": ([1.0, -1, 0.5], [[1, 1, 0], [0, 1, -1]], [4, 1], None, None,
                 np.array([-2, -1, 0.0]), np.full(3, 1e10)),
}


@pytest.mark.parametrize("name", CASES)
def test_cases_agree_with_highs_ds(name):
    c, Ai, bi, Ae, be, l, u = CASES[name]
    n = len(c)
    bounds = list(zip(np.zeros(n) if l is None else l, [INF] * n if u is None else u))
    h = linprog(c, A_ub=Ai, b_ub=bi, A_eq=Ae, b_eq=be, bounds=bounds, method="highs-ds")
    r = ipm(*standard(c, Ai, bi, Ae, be, l, u))
    if h.status == 0:
        assert r["status"] == "optimal" and r["f"] == pytest.approx(h.fun, abs=1e-6)
    else:
        assert r["status"] != "optimal"


def test_standard_does_not_mutate_its_input():
    """standard() once compacted the caller's sparse A_ub in place (eliminate_zeros on shared
    arrays), which corrupted it for the next branch-and-bound node."""
    import scipy.sparse as sp
    A = sp.csr_array((np.array([1.0, 0.0, 2.0]), np.array([0, 1, 2]), np.array([0, 2, 3])),
                     shape=(2, 3))
    data, ind, ptr = A.data.copy(), A.indices.copy(), A.indptr.copy()
    standard([1.0, 1, 1], A, [1, 1])
    assert (A.data == data).all() and (A.indices == ind).all() and (A.indptr == ptr).all()


@pytest.mark.parametrize("seed", range(5))
def test_normal_equations_agree_with_the_augmented_system(seed):
    """Vanderbei Ch. 19: for an LP, (A H^-1 A' + dd I) dy = rp + A H^-1 rho gives the same
    step as the quasi-definite system."""
    S = standard(*rand_lp(seed))
    a, b = ipm(*S, kkt="augmented"), ipm(*S, kkt="normal")
    assert a["stats"]["kkt"] == "augmented" and b["stats"]["kkt"] == "normal"
    assert b["status"] == "optimal" and b["f"] == pytest.approx(a["f"], abs=1e-7)


def test_normal_equations_with_dependent_rows():
    c, Ai, bi, Ae, be, l, u = CASES["duplicate equality rows"]
    r = ipm(*standard(c, Ai, bi, Ae, be, l, u), kkt="normal")
    assert r["status"] == "optimal" and r["f"] == pytest.approx(1.0, abs=1e-7)


# Convex constraints h(x) <= 0 (Vanderbei Ch. 25): the barrier step of the fixed-integer M2.

def disc(r=1.0):
    """min -x1 - x2 s.t. x1^2 + x2^2 <= r^2, 0 <= x <= 2: x* = (r, r)/sqrt(2), f* = -r sqrt(2)."""
    import scipy.sparse as sp

    def h(x):
        return np.array([x[0] ** 2 + x[1] ** 2 - r * r])

    def J(x):
        return sp.csr_array(np.array([[2 * x[0], 2 * x[1]]]))

    def H(x, lam):
        return sp.diags_array(np.array([2 * lam[0], 2 * lam[0]]))

    return h, J, H


def test_convex_constraint_disc():
    h, J, H = disc()
    r = ipm(np.array([-1.0, -1]), np.zeros((0, 2)), np.zeros(0), np.zeros(2), np.full(2, 2.0),
            h=h, Jh=J, Hh=H)
    assert r["status"] == "optimal"
    assert r["x"] == pytest.approx(np.full(2, 2 ** -0.5), abs=1e-7)
    assert r["f"] == pytest.approx(-(2 ** 0.5), abs=1e-7)
    assert r["L"] <= r["f"] + 1e-9 and r["L"] == pytest.approx(r["f"], abs=1e-6)
    assert r["lam"][0] == pytest.approx(2 ** -0.5, abs=1e-6)       # KKT: 1 = 2 lam x_i


@pytest.mark.parametrize("seed", range(5))
def test_separable_loss_rows_against_tangent_lp(seed):
    """min c'x over a random LP plus rows g_k >= p_k/eta + alpha p_k^2: the value lies between
    the LP with many tangent cuts (a relaxation) and with many secants (a restriction)."""
    import scipy.sparse as sp
    g = np.random.default_rng(seed)
    k, eta, alpha = 4, 0.9, 0.05
    n = 2 * k                                            # x = (p_1..p_k, g_1..g_k)
    c = np.r_[-g.uniform(1, 3, k), np.full(k, 1.0)]      # reward p, pay for g
    A = np.r_[np.ones(k), np.zeros(k)][None, :]          # sum p = S
    b = np.array([g.uniform(1, 3 * k)])
    P, G = np.arange(k), np.arange(k, n)

    def h(x):
        return x[P] / eta + alpha * x[P] ** 2 - x[G]

    def J(x):
        return sp.csr_array((np.r_[1 / eta + 2 * alpha * x[P], -np.ones(k)],
                             (np.r_[np.arange(k), np.arange(k)], np.r_[P, G])), shape=(k, n))

    def H(x, lam):
        d = np.zeros(n)
        d[P] = 2 * alpha * lam
        return sp.diags_array(d)

    r = ipm(c, A, b, np.zeros(n), np.full(n, 10.0), h=h, Jh=J, Hh=H)
    lo = hi = None
    grid = np.linspace(0, 10, 201)
    T = [np.r_[np.eye(k)[i] * (1 / eta + 2 * alpha * s), -np.eye(k)[i]] for s in grid for i in P]
    tb = [alpha * s * s for s in grid for _ in P]
    lo = linprog(c, A_ub=np.array(T), b_ub=tb, A_eq=A, b_eq=b, bounds=(0, 10), method="highs-ds")
    S = [np.r_[np.eye(k)[i] * (1 / eta + alpha * (s0 + s1)), -np.eye(k)[i]]
         for s0, s1 in itertools.pairwise(grid) for i in P]
    sb = [alpha * s0 * s1 for s0, s1 in itertools.pairwise(grid) for _ in P]
    hi = linprog(c, A_ub=np.array(S), b_ub=sb, A_eq=A, b_eq=b, bounds=(0, 10), method="highs-ds")
    assert r["status"] == "optimal" and lo.fun - 1e-7 <= r["f"] <= hi.fun + 1e-7
    assert r["L"] <= r["f"] + 1e-9 and hi.fun - lo.fun < 1e-3
