"""MILP plumbing shared by every formulation: sparse rows built one at a time, the HiGHS call,
and the names of its terminations. It holds no model; route, transit and recharging formulations
depend on it and not on each other.
"""

import itertools
import time

import numpy as np
import scipy.sparse as sp
from scipy.optimize import Bounds, LinearConstraint, milp

HIGHS = {0: "optimal", 1: "feasible_limit", 2: "infeasible", 3: "unbounded", 4: "numerical"}


class Rows:
    """Sparse rows lo <= A v <= hi, accumulated one at a time."""

    def __init__(self):
        self.r, self.c, self.v, self.lo, self.hi = [], [], [], [], []

    def add(self, cols, vals, lo=-np.inf, hi=np.inf):
        k = len(self.lo)
        self.r += [k] * len(cols)
        self.c += list(cols)
        self.v += list(vals)
        self.lo.append(lo)
        self.hi.append(hi)

    def constraint(self, n):
        A = sp.csr_array((self.v, (self.r, self.c)), shape=(len(self.lo), n))
        return LinearConstraint(A, self.lo, self.hi)


def solve(c, rows, lb, ub, integ, time_limit, gap):
    """HiGHS on min c'v, rows, lb <= v <= ub, integrality integ. OUTPUT (result, seconds)."""
    t = time.perf_counter()
    res = milp(c, constraints=rows.constraint(len(c)), integrality=integ, bounds=Bounds(lb, ub),
               options=dict(time_limit=time_limit, mip_rel_gap=gap, disp=False))
    return res, time.perf_counter() - t


def status(res):
    """The solver's own termination: a time or node limit without an incumbent is no_incumbent."""
    s = HIGHS.get(res.status, "numerical")
    return "no_incumbent" if s == "feasible_limit" and res.x is None else s


def dual_bound(res, s):
    """HiGHS's MIP dual bound when status s has one, never the incumbent's value."""
    return getattr(res, "mip_dual_bound", None) if s in ("optimal", "feasible_limit") else None


def bracket(c, A, lb, ub, integ, eta, alpha, P, J, loss_rows, replay, time_limit):
    """The MILP bracket of a model whose loss rows are g >= p/eta + alpha p^2 on [0, P]
    (Models §5, Routing §6): the tangents at the J + 1 breakpoints r_k = kP/J give a lower MILP,
    the maximum of the J secants an upper one, each piece a (slope, intercept) pair.

    INPUT   A ........... the model's LinearConstraint; c, lb, ub, integ its data
            loss_rows ... pieces -> (T, hi): the model's rows T v <= hi for these pieces
            replay ...... x -> (U, defects): the independent replay of an upper solution
    OUTPUT  lower (HiGHS's dual bound of the lower MILP), upper (replayed), upper_defects
    """
    r = np.linspace(0.0, P, J + 1)
    out = {}
    for side, pieces in (("lower", [(1 / eta + 2 * alpha * s, alpha * s * s) for s in r]),
                         ("upper", [(1 / eta + alpha * (s0 + s1), alpha * s0 * s1)
                                    for s0, s1 in itertools.pairwise(r)])):
        T, hi = loss_rows(pieces)
        res = milp(c, constraints=[A, LinearConstraint(T, -np.inf, hi)], integrality=integ,
                   bounds=Bounds(lb, ub), options=dict(time_limit=time_limit, mip_rel_gap=1e-7))
        if side == "lower":
            out["lower"] = getattr(res, "mip_dual_bound", None) if res.x is not None else None
        else:
            out["upper"], out["upper_defects"] = replay(res.x) if res.x is not None else (None,
                                                                                          None)
    return out
