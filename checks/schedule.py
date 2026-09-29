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


def replay_energy(c, v, duties, plan, infra, tol=1e-6, loss=False):
    """Replay an M1 (or, with loss, M2) schedule slot by slot, independently of its rows
    (Models §3-§4).

    INPUT   duties .. trip ids per bus; plan .. {trip id: {slot: battery kW}} charged before
            that trip at its first stop; infra .. {site: dict(n=plugs, h=kW upgrade)}
            loss .... grid power p/eta + alpha p^2 (10), and the taper p <= P (1 - e/B) (11)
    OUTPUT  ok, defects, cost (recomputed from the schedule alone), parts, fleet,
            trace ... per bus, the points (seconds, kWh) where its energy changes
            load .... {(site, slot): (buses charging, grid kW)}
            Kinds: those of replay(), energy, overcharge, window, presence, power, site, plugs,
            grid, taper.
    """
    base = replay(c, duties, dict(speed=v["deadhead"]["speed"], detour=v["deadhead"]["detour"],
                                  layover=v["time"]["layover"]))
    D = list(base["defects"])
    T, S = {t["id"]: t for t in c["trips"]}, c["stops"]
    b, ch, co, dl = v["battery"], v["charger"], v["cost"], v["time"]["delta"]
    B, kap, eta, det = b["B"], b["kappa"], ch["eta"], v["deadhead"]["detour"]
    rB, top, s0B, h = b["reserve"] * B, b["smax"] * B, b["s0"] * B, dl / 3600
    depot = dict(lat=v["depot"]["lat"], lon=v["depot"]["lon"])
    site = {stop: s for s, d in v["sites"].items() for stop in d["stops"]}
    use, km_dh, kwh, restore, trace = {}, 0.0, 0.0, 0.0, []
    for d in duties:
        if any(k not in T for k in d):
            continue
        km = great_circle_km(depot, S[T[d[0]]["first"]]) * det
        km_dh, e, here = km_dh + km, s0B - kap * km, None
        t0 = min([s_ * dl for s_ in plan.get(d[0], {})] + [T[d[0]]["dep"]])
        t0 -= 3600 * km / v["deadhead"]["speed"]
        tr = [(t0, s0B), (t0 + 3600 * km / v["deadhead"]["speed"], e)]
        if e < rB - tol:
            D.append(("energy", f"pull-out to {d[0]} arrives with {e:.6g}"))
        for q, k in enumerate(d):
            t = T[k]
            for s_, kw in sorted(plan.get(k, {}).items()):
                s = site.get(t["first"])
                if s is None or s not in infra:
                    D.append(("site", f"{k} charges at {t['first']}, not an open site"))
                if not (s_ * dl >= t["dep"] - v["time"]["window"] - tol
                        and (s_ + 1) * dl <= t["dep"] + tol):
                    D.append(("window", f"{k} slot {s_}"))
                if here is not None and s_ * dl < here - tol:
                    D.append(("presence", f"{k} slot {s_} before the bus arrives"))
                if kw > ch["P"] + tol or kw < -tol:
                    D.append(("power", f"{k} slot {s_}: {kw:.6g} kW"))
                tr.append((s_ * dl, e))
                e += h * kw
                tr.append(((s_ + 1) * dl, e))
                grid = kw / eta + (ch["alpha"] * kw * kw if loss else 0.0)       # (10)
                if loss and kw > ch["P"] * (1 - e / B) + tol:                    # (11)
                    D.append(("taper", f"{k} slot {s_}: {kw:.6g} kW at {e:.6g} kWh"))
                kwh += h * grid
                u = use.setdefault((s, s_), [0, 0.0])
                u[0], u[1] = u[0] + 1, u[1] + grid
            if e > top + tol:
                D.append(("overcharge", f"{k} departs with {e:.6g}"))
            if e - kap * t["km"] < rB - tol:
                D.append(("energy", f"{k} would end below reserve"))
            tr.append((t["dep"], e))
            e -= kap * t["km"]
            tr.append((t["arr"], e))
            nxt = S[T[d[q + 1]]["first"]] if q + 1 < len(d) else depot
            km = great_circle_km(S[t["last"]], nxt) * det
            km_dh, e = km_dh + km, e - kap * km
            here = t["arr"] + 3600 * km / v["deadhead"]["speed"]
            tr.append((here, e))
            if e < rB - tol:
                D.append(("energy", f"after {k} the bus reaches its next stop with {e:.6g}"))
        restore += (s0B - e) / eta
        trace.append(tr)
    peak = {s: v["sites"][s]["L"] for s in infra}
    for (s, s_), (k, kw) in sorted(use.items(), key=lambda z: (str(z[0][0]), z[0][1])):
        if s not in infra:
            continue
        L = v["sites"][s]["L"]
        if k > infra[s]["n"]:
            D.append(("plugs", f"{s} slot {s_}: {k} > {infra[s]['n']}"))
        if L + kw > v["sites"][s]["G0"] + infra[s]["h"] + tol:
            D.append(("grid", f"{s} slot {s_}: {L + kw:.6g} kW"))
        peak[s] = max(peak[s], L + kw)
    parts = dict(buses=co["F"] * len(duties), deadhead=co["deadhead"] * km_dh,
                 energy=co["energy"] * kwh, depot_energy=co["depot_energy"] * restore,
                 sites=co["site"] * len(infra),
                 plugs=co["plug"] * sum(i["n"] for i in infra.values()),
                 upgrade=co["upgrade"] * sum(i["h"] for i in infra.values()),
                 peak=co["peak"] * sum(peak.values()))
    return dict(ok=not D, defects=D, cost=sum(parts.values()), parts=parts, fleet=len(duties),
                trace=trace, load={k: tuple(u) for k, u in use.items()})
