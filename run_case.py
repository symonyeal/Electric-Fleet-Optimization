"""One instance, one model, one result bundle.

    python run_case.py evrp E-n22-k4 R1 [--time 600]

Writes docs/results/evrp/<instance>-<model>.json (the result record) and .routes (exchange
format), and prints status, U, L and the gap.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from checks.route import read_routes, replay, write_routes
from data.evrp import KEYS, load
from models.colgen import colgen
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


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("track", choices=["evrp"])
    a.add_argument("instance")
    a.add_argument("model", choices=list(MODELS))
    a.add_argument("--time", type=float, default=600.0, help="solver time limit, seconds")
    a.add_argument("--out", default="docs/results/evrp")
    x = a.parse_args()
    p = load(x.instance if "/" in x.instance else key(x.instance))
    r = MODELS[x.model](p, time_limit=x.time)
    save(r, Path(x.out) / f"{p['name']}-{x.model}")
    print(f"{p['name']} {x.model}: {r['status']}  U={r['U']}  L={r['L']}  gap={r['gap_rel']}  "
          f"certified={r['certified']}  {r['elapsed']:.1f}s")


if __name__ == "__main__":
    main()
