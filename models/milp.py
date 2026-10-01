"""MILP plumbing shared by every formulation: sparse rows built one at a time, the HiGHS call,
and the names of its terminations. It holds no model; route, transit and recharging formulations
depend on it and not on each other.
"""

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
