"""One instance, one model, one result bundle.

    python run_case.py evrp E-n22-k4 R1 [--time 600]
    python run_case.py transit route100 M1 [--until 8] [--time 600]

Writes docs/results/<track>/<instance>-<model>.json (the result record), and for routing the
routes in exchange format, and prints status, U, L and the gap. The transit corridor is the
committed fixture tests/fixtures/<instance>.json with data/scenarios/<instance>.toml.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from checks.route import read_routes, replay, write_routes
from data.evrp import KEYS, load
from data.scenario import load as scenario
from models.colgen import colgen
from models.fleet import m1
from models.network import m0
from models.route import r0, r1, r1tr


def r2(p, duals, time_limit):
    """R2 seeded with every replayed baseline route on disk for the instance."""
    init = [r for f in sorted(Path("docs/results/baseline").glob(f"{p['name']}-*.routes"))
            if replay(p, R := read_routes(f))["ok"] for r in R]
    return colgen(p, duals=duals, init_routes=init, time_limit=time_limit)


MODELS = {"R0": r0, "R1": r1, "R1-TR": r1tr,
          "R2-ipm": lambda p, time_limit: r2(p, "ipm", time_limit),
          "R2-simplex": lambda p, time_limit: r2(p, "simplex", time_limit)}


def key(name):
    k = [k for k in KEYS if k.endswith("/" + name)]
    if len(k) != 1:
        raise SystemExit(f"{name}: {len(k)} instances match; use set/name, e.g. evrp-2019/{name}")
    return k[0]


def save(r, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(r, indent=1, default=lambda v: v.item()
                                        if isinstance(v, np.generic) else str(v)) + "\n")
    if r.get("routes"):
        write_routes(out.with_suffix(".routes"), r["routes"])


def transit(x):
    with open(f"tests/fixtures/{x.instance}.json", encoding="utf-8") as f:
        c = json.load(f)
    v, prov = scenario(f"data/scenarios/{x.instance}.toml")
    name = x.instance
    if x.until:
        c = dict(c, trips=[t for t in c["trips"] if t["dep"] < 3600 * x.until])
        name = f"{x.instance}-until{x.until:g}h"
    sc = dict(speed=v["deadhead"]["speed"], detour=v["deadhead"]["detour"],
              layover=v["time"]["layover"])
    if x.model == "M0":
        r = dict(model="M0", instance=name, trips=len(c["trips"]), **m0(c, sc))
    else:
        r = m1(c, v, name=name, time_limit=x.time)
    r["scenario"] = {k: list(u) for k, u in prov.items()}
    save(r, Path(x.out or "docs/results/transit") / f"{name}-{x.model}")
    print(f"{name} {x.model}: " + ", ".join(f"{k}={r.get(k)}" for k in (
        "status", "fleet", "U", "L", "gap_rel", "certified", "elapsed") if k in r))


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("track", choices=["evrp", "transit"])
    a.add_argument("instance")
    a.add_argument("model", choices=[*MODELS, "M0", "M1"])
    a.add_argument("--time", type=float, default=600.0, help="solver time limit, seconds")
    a.add_argument("--until", type=float, default=None, help="transit: trips departing before")
    a.add_argument("--out", default=None)
    x = a.parse_args()
    if x.track == "transit":
        return transit(x)
    x.out = x.out or "docs/results/evrp"
    p = load(x.instance if "/" in x.instance else key(x.instance))
    r = MODELS[x.model](p, time_limit=x.time)
    save(r, Path(x.out) / f"{p['name']}-{x.model}")
    print(f"{p['name']} {x.model}: {r['status']}  U={r['U']}  L={r['L']}  gap={r['gap_rel']}  "
          f"certified={r['certified']}  {r['elapsed']:.1f}s")


if __name__ == "__main__":
    main()
