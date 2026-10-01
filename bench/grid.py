"""OA-04, the charging-physics grid: M2 against M1 on Route 100 before 06:30, R3 against R1 on
E-n22-k4 restricted to its customers farthest from the depot, over declared loss coefficients
(illustrative). With the declared 250 kWh battery no bus charges before 06:30, so M2 = M1 there
at every alpha; the 100 kWh rows make the window charge. The eight-customer R3 row measures
where OA stops closing. Each row carries the formulation and code identity that produced it and
is written atomically when it finishes; with missing, rows bench/collect.py would admit are kept
and the rest recomputed.
"""

import copy
import json
from pathlib import Path

from bench import schema


def rows_of(v0, Q):
    K = [*[("M2 / M1", B, a) for B in (v0["battery"]["B"], 100.0)
           for a in (3.3e-5, 6.7e-5, 1.3e-4)],
         *[("R3 / R1", 6, a) for a in (0.0, 2.5e-4, 5e-4, 1e-3)], ("R3 / R1", 8, 0.0)]
    nm = lambda k: (f"route100 before 06:30, {k[1]:g} kWh" if k[0] == "M2 / M1"
                    else Q[k[1]]["name"])
    return K, nm


def grid(out, missing=False):
    """Recompute the grid rows into out/grid/grid.json. OUTPUT the rows written."""
    from bench.collect import grid as admitted
    from checks.certificate import HOST
    from checks.route import replay_charge
    from data.evrp import load, sub
    from data.scenario import load as scenario
    from models.charge import m2
    from models.fleet import m1
    from models.recharge import r3
    from models.route import r1
    code = schema.identity()
    fm = schema.formulations()
    c = json.loads(Path("tests/fixtures/route100.json").read_text(encoding="utf-8"))
    c = dict(c, trips=[t for t in c["trips"] if t["dep"] < 6.5 * 3600])
    v, _ = scenario("data/scenarios/route100.toml")
    v0 = copy.deepcopy(v)
    v0["charger"]["gamma"] = 0.0
    p = load("evrp-2019/E-n22-k4")
    far = sorted(p["I"], key=lambda i: -p["D"][p["depot"], i])
    Q = {n: sub(p, far[:n], p["F"]) for n in (6, 8)}
    sc, _ = scenario("data/scenarios/r3.toml")
    K, nm = rows_of(v0, Q)
    idx = {(k[0], nm(k), k[2]): j for j, k in enumerate(K)}
    key = lambda g: (g["pair"], g["instance"], g["alpha"])
    f = Path(out) / "grid" / "grid.json"
    G = [g for g in admitted(out, schema.manifest(out), []) if key(g) in idx] if missing else []
    have, base = {key(g) for g in G}, {}

    def put(g, r, b, model):
        G.append(dict(g, base_status=b["status"], U=r["U"], L=r["L"], gap=r["gap_rel"],
                      status=r["status"], elapsed=r["elapsed"], formulation=fm[model],
                      revision=code["commit"][:7], commit=code["commit"], dirty=code["dirty"],
                      source=code["source"], host=HOST))
        G.sort(key=lambda g: idx[key(g)])
        schema.write_text(f, json.dumps(G, indent=1) + "\n")

    for k in K:
        pair, z, a = k
        if (pair, nm(k), a) in have:
            continue
        if pair == "M2 / M1":
            w = copy.deepcopy(v0)
            w["battery"]["B"] = z
            b = base[k[:2]] = base.get(k[:2]) or m1(c, w, name="route100-until6.5h",
                                                    time_limit=600)
            w["charger"]["alpha"] = a
            r = m2(c, w, name="route100-until6.5h", max_iter=40, time_limit=1800)
            put(dict(pair=pair, instance=nm(k), measure="cost", alpha=a, base=b["U"],
                     loss=r["U"] if r["status"] == "optimal" else None), r, b, "M2")
            continue
        q = Q[z]
        b = base[k[:2]] = base.get(k[:2]) or r1(q)
        s = copy.deepcopy(sc)
        s["charger"]["alpha"] = a
        r = r3(q, s, max_iter=60, time_limit=1800)
        y = None
        if r["status"] == "optimal":
            y = replay_charge(q, s, r["routes"], {tuple(map(int, e.split(":"))): qt
                                                  for e, qt in r["charges"].items()})["length"]
        put(dict(pair=pair, instance=nm(k), measure="route length", alpha=a, base=b["U"],
                 loss=y), r, b, "R3")
    return G
