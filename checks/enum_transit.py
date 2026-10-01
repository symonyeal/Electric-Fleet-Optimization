"""Exhaustive M1 optimum for tiny timetables at one charging site (Validation §2). Imports
nothing from models/.

Setting: every trip starts and ends at one stop, which is the only charging site and where the
depot is, so no deadhead is driven; the site's plugs and grid upgrade are given. Every partition
of the trips into time-feasible chains is a candidate fleet; for each, the charging plan is a
small MILP written here from scratch (energy per trip and slot, one plug per charging bus), and
the least total cost over partitions is the optimum. Bell(6) = 203 partitions at most.

The open site's meter carries its base load L all day, so its billed demand is at least L, and
L must fit the site's capacity. The depot restores each chain's bus to s0 B overnight: the
restoration variable is max(0, s0 B - end energy), never a credit.
"""

import itertools
import math

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp


def partitions(items):
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for part in partitions(rest):
        yield [[first], *part]
        for k in range(len(part)):
            yield [*part[:k], [first, *part[k]], *part[k + 1:]]


def enum_m1(c, v, site, n_plugs, h_up):
    """OUTPUT (least cost, best partition as trip-id chains); (inf, None) if none is feasible."""
    T = {t["id"]: t for t in c["trips"]}
    b, ch, co, tm = v["battery"], v["charger"], v["cost"], v["time"]
    B, kap, eta, P, dl, W = b["B"], b["kappa"], ch["eta"], ch["P"], tm["delta"], tm["window"]
    rB, top, s0B, h = b["reserve"] * B, b["smax"] * B, b["s0"] * B, dl / 3600
    sd = v["sites"][site]
    if sd["L"] > sd["G0"] + h_up + 1e-9:              # the meter's base load cannot be served
        return math.inf, None
    rho = 1 + co.get("rider", 0.0)                    # the tariff's riders (Data §3)
    fixed = co["site"] + rho * co.get("basic", 0.0) + co["plug"] * n_plugs + co["upgrade"] * h_up
    best = (math.inf, None)
    for part in partitions(sorted(T, key=lambda k: T[k]["dep"])):
        chains = [sorted(ch_, key=lambda k: T[k]["dep"]) for ch_ in part]
        if any(T[a]["arr"] + tm["layover"] > T[z]["dep"] for q in chains
               for a, z in itertools.pairwise(q)):
            continue
        cost = charging(chains, T, B, kap, eta, P, dl, W, rB, top, s0B, h, sd, co,
                        n_plugs, h_up)
        total = co["F"] * len(chains) + cost + fixed
        if total < best[0]:
            best = (total, chains)
    return best


def charging(chains, T, B, kap, eta, P, dl, W, rB, top, s0B, h, sd, co, n_plugs, h_up):
    """Least charging, depot-restore and peak cost for fixed chains, or inf if infeasible.
    Variables per trip: departure energy y_j, and per window slot power p and plug u; per chain
    the end-of-day energy and the energy restored overnight, r >= s0 B - end, r >= 0; one peak
    variable D >= L, bounded below by the slots of the billing window [peak_from, peak_to) hours
    only (wrapping past midnight when peak_from > peak_to). Every electricity price carries the
    factor 1 + rider."""
    rho = 1 + co.get("rider", 0.0)
    w0, w1 = 3600 * co.get("peak_from", 0.0), 3600 * co.get("peak_to", 24.0)
    cols, lo, hi, integ, cost = {}, [], [], [], []

    def var(key, l, u, i=0, c=0.0):
        cols[key] = len(lo)
        lo.append(l)
        hi.append(u)
        integ.append(i)
        cost.append(c)

    rows, rlo, rhi = [], [], []

    def row(coef, l, u):
        rows.append(coef)
        rlo.append(l)
        rhi.append(u)

    slots = {}
    for q, ch_ in enumerate(chains):
        for k, j in enumerate(ch_):
            t = T[j]
            var(("y", j), rB + kap * t["km"], top)
            first = math.ceil((t["dep"] - W) / dl)
            here = -math.inf if k == 0 else T[ch_[k - 1]]["arr"]
            for s in range(first, math.floor(t["dep"] / dl)):
                if s * dl >= here:
                    var(("p", j, s), 0.0, P, 0, rho * co["energy"] * h / eta)
                    var(("u", j, s), 0.0, 1.0, 1)
                    row({cols["p", j, s]: 1.0, cols["u", j, s]: -P}, -np.inf, 0.0)
                    slots.setdefault(s, []).append(j)
            prev = s0B if k == 0 else None
            coef = {cols["y", j]: 1.0}
            for s in slots_of(cols, j):
                coef[cols["p", j, s]] = -h
            if prev is not None:                       # y_j = s0 B + h sum p
                row(coef, prev, prev)
            else:                                      # y_j = y_prev - E_prev + h sum p
                i = ch_[k - 1]
                coef[cols["y", i]] = -1.0
                row(coef, -kap * T[i]["km"], -kap * T[i]["km"])
                a = {cols["y", i]: 1.0}                # arrival energy >= rB
                row(a, rB + kap * T[i]["km"], np.inf)
        last = ch_[-1]
        var(("end", q), 0.0, top)
        var(("r", q), 0.0, np.inf, 0, rho * co["depot_energy"] / eta)
        row({cols["end", q]: 1.0, cols["y", last]: -1.0}, -kap * T[last]["km"],
            -kap * T[last]["km"])
        row({cols["end", q]: 1.0}, rB, np.inf)
        row({cols["r", q]: 1.0, cols["end", q]: 1.0}, s0B, np.inf)     # r >= s0 B - end
    var(("D",), sd["L"], np.inf, 0, rho * co["peak"])               # the base load is billed
    for s, js in slots.items():
        row({cols["u", j, s]: 1.0 for j in js}, -np.inf, n_plugs)
        row({**{cols["p", j, s]: 1 / eta for j in js}}, -np.inf, sd["G0"] + h_up - sd["L"])
        t = s * dl % 86400
        if (w0 <= t < w1) if w0 <= w1 else (t >= w0 or t < w1):
            row({**{cols["p", j, s]: 1 / eta for j in js}, cols["D",]: -1.0}, -np.inf, -sd["L"])
    A = np.zeros((len(rows), len(lo)))
    for r, coef in enumerate(rows):
        for k, val in coef.items():
            A[r, k] = val
    res = milp(np.array(cost), constraints=LinearConstraint(A, rlo, rhi), integrality=integ,
               bounds=Bounds(lo, hi))
    if res.status != 0:
        return math.inf
    return res.fun


def slots_of(cols, j):
    return sorted(k[2] for k in cols if k[0] == "p" and k[1] == j)
