"""Independent replay of transit vehicle schedules (Validation §2). Imports nothing from models/.

A duty is a list of trip ids in service order. It is time-connected if each next trip starts no
earlier than the previous one ends plus the deadhead between their stops and the layover:
    arr_i + deadhead(last_i, first_j) + layover <= dep_j,
    deadhead = great-circle distance x detour / speed    (a declared scenario, Data §3).
"""

import itertools
import math


def great_circle_km(a, b):
    """Haversine distance between two stops given as dicts with lat, lon (degrees)."""
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dp, dl = p2 - p1, math.radians(b["lon"] - a["lon"])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def replay(c, duties, sc, tol=1e-9):
    """OUTPUT  ok, defects [(kind, detail)], fleet, deadhead_km. Kinds: unknown_trip, missing,
    repeat, time."""
    T = {t["id"]: t for t in c["trips"]}
    S, D, seen, dh = c["stops"], [], {}, 0.0
    for d in duties:
        if bad := [k for k in d if k not in T]:
            D.append(("unknown_trip", f"{bad}"))
            continue
        for k in d:
            seen[k] = seen.get(k, 0) + 1
        for a, b in itertools.pairwise(d):
            km = great_circle_km(S[T[a]["last"]], S[T[b]["first"]]) * sc["detour"]
            dh += km
            if T[a]["arr"] + 3600 * km / sc["speed"] + sc["layover"] > T[b]["dep"] + tol:
                D.append(("time", f"{a} -> {b}"))
    for k in T:
        if seen.get(k, 0) != 1:
            D.append(("missing" if k not in seen else "repeat", k))
    return dict(ok=not D, defects=D, fleet=len(duties), deadhead_km=dh)
