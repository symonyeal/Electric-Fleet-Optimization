"""The compiled transit instance (Models §1, §3a): everything M0, M1 and M1's extensions read
from a corridor and a scenario, built once and never rebuilt inside an iterative method.

    great_circle_km(a, b) ... haversine distance between two stops (dicts with lat, lon)
    compat(c, sc) ........... [(i, j, tau_ij)]: trip j may follow trip i,
                              arr_i + tau_ij + layover <= dep_j, tau = km x detour / speed. O(n^2)
    compile(c, v) ........... the immutable instance below; v is validated first (Data §3)

The instance holds the trips T, the compatibility arcs P, deadhead distances (km_ij on P, km0
from the depot, km1 to it), trip energies E = kappa km, the charging window win[j] (slots
before trip j's departure at a candidate site), the arrival times on each arc, the battery and
charger constants, and the digests of the corridor and the scenario that identify a result.
Arrays are read-only and the maps are views: a method that needs other bounds copies them.
"""

import copy
import math
from types import MappingProxyType

import numpy as np

from checks.certificate import digest
from data.scenario import validate


def great_circle_km(a, b):
    p1, p2 = np.radians(a["lat"]), np.radians(b["lat"])
    h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(
        np.radians(b["lon"] - a["lon"]) / 2) ** 2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(h))


def compat(c, sc):
    """[(i, j, tau_ij)] over trip indices with arr_i + tau_ij + layover <= dep_j (seconds);
    tau = great-circle km x detour / speed. O(n^2)."""
    T, S = c["trips"], c["stops"]
    ends = {(t["last"], u["first"]) for t in T for u in T}
    tau = {(a, b): 3600 * great_circle_km(S[a], S[b]) * sc["detour"] / sc["speed"] for a, b in ends}
    return [(i, j, tau[t["last"], u["first"]]) for i, t in enumerate(T) for j, u in enumerate(T)
            if t["arr"] + tau[t["last"], u["first"]] + sc["layover"] <= u["dep"] + 1e-9]


def _frozen(a):
    a = np.array(a, dtype=float)
    a.flags.writeable = False
    return a


def compile(c, v):
    """The instance of corridor c under scenario v, as a read-only mapping."""
    validate(v)
    T, S = c["trips"], c["stops"]
    dh, b, ch, t = v["deadhead"], v["battery"], v["charger"], v["time"]
    sc = dict(speed=dh["speed"], detour=dh["detour"], layover=t["layover"])
    site = {stop: s for s, d in v["sites"].items() for stop in d["stops"]}
    depot = dict(lat=v["depot"]["lat"], lon=v["depot"]["lon"])
    km = lambda a, z: float(great_circle_km(a, z) * dh["detour"])
    P = tuple(compat(c, sc))
    D, W = t["delta"], t["window"]
    win = {j: tuple(range(math.ceil((tr["dep"] - W) / D), math.floor(tr["dep"] / D)))
           for j, tr in enumerate(T) if site.get(tr["first"])}
    return MappingProxyType(dict(
        T=tuple(T), n=len(T), P=P, site=MappingProxyType(site), sites=tuple(v["sites"]),
        win=MappingProxyType(win), E=_frozen([b["kappa"] * tr["km"] for tr in T]),
        km_ij=_frozen([km(S[T[i]["last"]], S[T[j]["first"]]) for i, j, _ in P]),
        km0=_frozen([km(depot, S[tr["first"]]) for tr in T]),
        km1=_frozen([km(S[tr["last"]], depot) for tr in T]),
        arrive=MappingProxyType({(i, j): T[i]["arr"] + tau for i, j, tau in P}),
        v=copy.deepcopy(v), D=D, P_max=ch["P"], eta=ch["eta"], B=b["B"], rB=b["reserve"] * b["B"],
        top=b["smax"] * b["B"], s0B=b["s0"] * b["B"], kappa=b["kappa"],
        corridor=digest(dict(trips=T, stops=S)), scenario=digest(v)))
