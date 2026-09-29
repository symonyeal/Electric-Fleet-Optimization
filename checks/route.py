"""Independent EVRP replay (Routing §1, §9). Imports nothing from models/ or methods/.

Exchange format: one line per route, 1-based node identifiers of the instance file, with the
depot at both ends. An interior depot visit ends one route and starts the next.
"""

import math
from itertools import pairwise
import re


def replay_charge(p, sc, routes, charges, tol=1e-6):
    """Replay R3 routes with partial charges (Routing §6), independently of models/.

    INPUT   routes .. 1-based node lists, depot at both ends, stations included
            charges . {(route, position of the station in it): (q, tau)}
    OUTPUT  ok, defects, cost = c_d length + c_e sum (q/eta + alpha q^2/tau) + c_tau sum tau.
            Kinds: those of replay() except battery, and energy, overcharge, power, dwell, time.
    """
    base = replay(dict(p, Q=math.inf), routes)            # coverage, load, endpoints, length
    D = [d for d in base["defects"] if d[0] != "battery"]
    X, o, F, Q, h = p["X"], p["depot"], set(p["F"]), p["Q"], p["h"]
    t, ch, co = sc["time"], sc["charger"], sc["cost"]
    grid = dwell = 0.0
    for r, route in enumerate(routes):
        v = [k - 1 for k in route]
        e, clock = Q, 0.0
        for pos, (a, c) in enumerate(pairwise(v), start=1):
            d = math.hypot(X[c][0] - X[a][0], X[c][1] - X[a][1])
            e -= h * d
            clock += d / t["speed"]
            if e < -tol:
                D.append(("energy", f"route {r} reaches node {c + 1} with {e:.6g}"))
            if c in F:
                q, tau = charges.get((r, pos), (0.0, 0.0))
                if e + q > Q + tol:
                    D.append(("overcharge", f"route {r} station {c + 1}: {e + q:.6g} > {Q:g}"))
                if q > ch["P"] * tau + tol:
                    D.append(("power", f"route {r} station {c + 1}: {q:.6g} in {tau:.6g} h"))
                if tau < t["tau_min"] - tol:
                    D.append(("dwell", f"route {r} station {c + 1}: {tau:.6g} h"))
                e += q
                clock += tau
                dwell += tau
                grid += q / ch["eta"] + (ch["alpha"] * q * q / tau if tau > 0 else 0.0)
            elif c != o:
                clock += t["service"]
        if clock > t["T"] + tol:
            D.append(("time", f"route {r} returns at {clock:.6g} h > {t['T']:g}"))
    cost = co["distance"] * base["length"] + co["energy"] * grid + co["dwell"] * dwell
    return dict(ok=not D, defects=D, cost=cost, length=base["length"], grid=grid, dwell=dwell)


def replay(p, routes, tol=1e-9):
    """Check routes against the report's rules; recompute length from coordinates.

    INPUT   p ....... instance (data.evrp.read)
            routes .. lists of 1-based identifiers
    OUTPUT  ok, defects [(kind, detail)], length, routes (count), load and low (least battery)
            per depot-to-depot route. Kinds: endpoint, unknown_node, missing, repeat, overload,
            battery.
    """
    X, N, o = p["X"], len(p["X"]), p["depot"]
    I, F = set(p["I"]), set(p["F"])
    D, seen, load, low, length = [], {}, [], [], 0.0
    for r in routes:
        v = [k - 1 for k in r]
        if bad := [k for k in r if not 1 <= k <= N]:
            D.append(("unknown_node", f"{bad} in {r}"))
            continue
        if v[0] != o or v[-1] != o:
            D.append(("endpoint", f"{r} does not start and end at depot {o + 1}"))
        q, y, m = 0.0, p["Q"], p["Q"]          # load, battery, least battery on arrival
        if v[0] in I:
            q, seen[v[0]] = p["b"][v[0]], seen.get(v[0], 0) + 1
        for a, c in pairwise(v):
            d = math.hypot(X[c][0] - X[a][0], X[c][1] - X[a][1])
            length += d
            y -= p["h"] * d
            m = min(m, y)
            if y < -tol:
                D.append(("battery", f"{a + 1}->{c + 1} leaves {y:.6g}"))
            if c in I:
                q += p["b"][c]
                seen[c] = seen.get(c, 0) + 1
            if c in F or c == o:
                y = p["Q"]
            if c == o:
                load.append(q)
                low.append(m)
                if q > p["C"] + tol:
                    D.append(("overload", f"route ending at {c + 1} carries {q:g} > {p['C']:g}"))
                q, m = 0.0, p["Q"]
    for i in sorted(I):
        if seen.get(i, 0) == 0:
            D.append(("missing", f"customer {i + 1}"))
        elif seen[i] > 1:
            D.append(("repeat", f"customer {i + 1} visited {seen[i]} times"))
    return dict(ok=not D, defects=D, length=length, routes=len(load), load=load, low=low)


def read_routes(path):
    with open(path) as f:
        return [[int(t) for t in l.split()] for l in f if l.split()]


def write_routes(path, routes):
    with open(path, "w") as f:
        f.writelines(" ".join(map(str, r)) + "\n" for r in routes)


def from_evrp_python(text, depot):
    """evrp-python's printed tours ('Tour k: a -> b -> ...', 0-based) in the exchange format."""
    out = []
    for m in re.finditer(r"^Tour \d+:(.*)$", text, re.MULTILINE):
        v = [int(t) for t in re.findall(r"\d+", m.group(1))]
        v = ([] if v and v[0] == depot else [depot]) + v + ([] if v and v[-1] == depot else [depot])
        out.append([k + 1 for k in v])
    return out
