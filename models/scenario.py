"""M4: one fleet and infrastructure for an enumerated set of energy scenarios (Models §7).

Scenario w has probability weight pi_w and consumption kappa_w per km. The schedule (x), the
sites, plugs and grid upgrade are common; charging, plugs in use and energies are recourse,
chosen after the scenario is revealed, which is an information assumption and not a policy
(Models §7). M1's rows are written once per scenario by models/fleet.rows and joined on the
common columns. Expected cost: common cost + sum_w pi_w C_w; worst case: common cost + theta
with theta >= C_w. The guarantee covers the enumerated scenarios only.
"""

import copy
import time

import numpy as np
import scipy.sparse as sp
from scipy.optimize import Bounds, LinearConstraint, milp

from checks.certificate import provenance, record
from checks.schedule import replay_energy
from models.fleet import rows, solution
from models.route import status

COMMON = ("x0", "x1", "xc", "o", "n", "h")


def scen(v, kappa):
    w = copy.deepcopy(v)
    w["battery"]["kappa"] = kappa
    return w


def join(c, v, scenarios, fixed=None, worst=False):
    """The joint MILP: columns [common | scenario 1 | ... | theta], and each scenario's map."""
    Ms = [rows(c, scen(v, k), fixed) for _, k in scenarios]
    M0 = Ms[0]
    common = np.zeros(len(M0["c"]), bool)
    for key in COMMON:
        common[M0["idx"][key]:M0["idx"][key] + M0["size"][key]] = True
    C, R = np.flatnonzero(common), np.flatnonzero(~common)
    nc, nr = len(C), len(R)
    maps, blocks, lo, hi, cost = [], [], [], [], []
    N = nc + nr * len(Ms) + (1 if worst else 0)
    lb, ub, integ, obj = np.zeros(N), np.zeros(N), np.zeros(N), np.zeros(N)
    lb[:nc], ub[:nc], integ[:nc], obj[:nc] = M0["lb"][C], M0["ub"][C], M0["integ"][C], M0["c"][C]
    for w, ((pw, _), M) in enumerate(zip(scenarios, Ms, strict=True)):
        col = np.empty(len(M["c"]), int)
        col[C] = np.arange(nc)
        col[R] = nc + w * nr + np.arange(nr)
        A = M["R"].constraint(len(M["c"])).A.tocoo()
        blocks.append(sp.csr_array((A.data, (A.row, col[A.col])), shape=(A.shape[0], N)))
        lo.append(M["R"].constraint(len(M["c"])).lb)
        hi.append(M["R"].constraint(len(M["c"])).ub)
        s = col[R]
        lb[s], ub[s], integ[s] = M["lb"][R], M["ub"][R], M["integ"][R]
        if worst:                                        # theta - C_w >= 0
            cost.append(sp.csr_array((np.r_[-M["c"][R], 1.0], (np.zeros(nr + 1, int),
                                      np.r_[s, N - 1])), shape=(1, N)))
        else:
            obj[s] = pw * M["c"][R]
        maps.append(col)
    if worst:
        lb[-1], ub[-1], obj[-1] = -np.inf, np.inf, 1.0
        blocks += cost
        lo += [np.zeros(1)] * len(cost)
        hi += [np.full(1, np.inf)] * len(cost)
    return dict(A=sp.vstack(blocks, format="csr"), lo=np.concatenate(lo),
                hi=np.concatenate(hi), lb=lb, ub=ub, integ=integ, c=obj, maps=maps, Ms=Ms)


def m4(c, v, scenarios, name="corridor", fixed=None, worst=False, time_limit=600.0, gap=1e-6):
    """M4 by HiGHS; every scenario's plan is replayed with its own consumption, and U is the
    replayed expected (or worst) cost."""
    J = join(c, v, scenarios, fixed, worst)
    t0 = time.perf_counter()
    res = milp(J["c"], constraints=LinearConstraint(J["A"], J["lo"], J["hi"]),
               integrality=J["integ"], bounds=Bounds(J["lb"], J["ub"]),
               options=dict(time_limit=time_limit, mip_rel_gap=gap))
    st = status(res)
    per, U = [], None
    if res.x is not None:
        costs = []
        for (pw, k), col, M in zip(scenarios, J["maps"], J["Ms"], strict=True):
            duties, plan, infra = solution(M, scen(v, k), res.x[col])
            rp = replay_energy(c, scen(v, k), duties, plan, infra)
            per.append(dict(kappa=k, weight=pw, ok=rp["ok"], cost=rp["cost"],
                            defects=rp["defects"], fleet=len(duties)))
            costs.append(rp["cost"])
        if all(p_["ok"] for p_ in per):
            U = max(costs) if worst else float(np.dot([pw for pw, _ in scenarios], costs))
    L = getattr(res, "mip_dual_bound", None) if st in ("optimal", "feasible_limit") else None
    return record("M4", name, st, U=U, L=L, solver=dict(code=int(res.status),
                  message=res.message), elapsed=time.perf_counter() - t0,
                  provenance=provenance(dict(name=name, sha256=c.get("source", {}).get(
                      "sha256")), scenarios=scenarios, worst=worst, fixed=fixed),
                  objective=None if res.x is None else float(res.fun), scenarios=per)
