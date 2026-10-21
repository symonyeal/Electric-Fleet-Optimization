"""One instance, one model, one result bundle.

    python run_case.py evrp E-n22-k4 R1 [--time 600]      R0 | R1 | R1-TR | R2-ipm | R2-simplex
                                                          | R2-rcc
    python run_case.py transit route100 M1 [--until 8] [--time 600] [--scenario rs1640]   M0 | M1

The (track, model) pair is checked before any data is read. Writes the schema-2 bundle of
bench/schema.py to docs/results/<track>/<stem>.json, with the routes beside it for routing,
atomically, and prints status, U, L and the gap. The transit corridor is the committed fixture
tests/fixtures/<instance>.json with data/scenarios/<instance>.toml, or with
data/scenarios/<instance>-<scenario>.toml under --scenario. A dirty tree may not write into
docs/results: commit first, or write elsewhere with --out.
"""

import argparse
import json
import sys
from pathlib import Path

from bench import cases, schema
from bench.cases import PAIRS, Case
from data.evrp import KEYS


def key(name):
    k = [k for k in KEYS if k.endswith("/" + name)]
    if len(k) != 1:
        raise SystemExit(f"{name}: {len(k)} instances match; use set/name, e.g. evrp-2019/{name}")
    return k[0]


def load_evrp(instance):
    from data.evrp import load
    return load(instance if "/" in instance else key(instance))


def load_transit(instance, scenario, until):
    from data.scenario import load
    with open(f"tests/fixtures/{instance}.json", encoding="utf-8") as f:
        c = json.load(f)
    v, _ = load(f"data/scenarios/{instance}" + (f"-{scenario}" if scenario else "") + ".toml")
    if until is not None:
        c = dict(c, trips=[t for t in c["trips"] if t["dep"] < 3600 * until])
    return c, v


def r2(p, duals, time_limit, rcc=False):
    """R2 seeded with every replayed baseline route on disk for the instance."""
    from checks.route import read_routes, replay
    from models.colgen import colgen
    init = [r for f in sorted(Path("docs/results/baseline").glob(f"{p['name']}-*.routes"))
            if replay(p, R := read_routes(f))["ok"] for r in R]
    return colgen(p, duals=duals, init_routes=init, time_limit=time_limit, rcc=rcc)


def solve(x, name):
    """The result record of the case."""
    if x.track == "evrp":
        from models.route import r0, r1, r1tr
        p = load_evrp(x.instance)
        f = {"R0": r0, "R1": r1, "R1-TR": r1tr,
             "R2-ipm": lambda p, time_limit: r2(p, "ipm", time_limit),
             "R2-simplex": lambda p, time_limit: r2(p, "simplex", time_limit),
             "R2-rcc": lambda p, time_limit: r2(p, "simplex", time_limit, rcc=True)}[x.model]
        return f(p, time_limit=x.time)
    c, v = load_transit(x.instance, x.scenario, x.until)
    if x.model == "M0":
        from models.network import m0_record
        return m0_record(c, v, name=name)
    from models.fleet import m1
    return m1(c, v, name=name, time_limit=x.time)


def parse(argv):
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("track", choices=sorted(PAIRS))
    a.add_argument("instance")
    a.add_argument("model", choices=sorted({m for ms in PAIRS.values() for m in ms}))
    a.add_argument("--time", type=float, default=600.0, help="solver time limit, seconds")
    a.add_argument("--until", type=float, default=None, help="transit: trips departing before")
    a.add_argument("--scenario", default=None,
                   help="transit: data/scenarios/<instance>-<this>.toml")
    a.add_argument("--out", default=None, help="directory of the bundle (default "
                   "docs/results/<track>)")
    x = a.parse_args(argv)
    if x.model not in PAIRS[x.track]:
        a.error(f"model {x.model} does not belong to track {x.track} (valid: "
                f"{', '.join(PAIRS[x.track])})")
    if x.track == "evrp" and (x.until is not None or x.scenario):
        a.error("--until and --scenario apply to the transit track only")
    return x


def main(argv=None):
    x = parse(argv)
    case = Case(x.track, x.instance, x.model, x.time, x.until, x.scenario)
    out = Path(x.out or cases.OUT / x.track)
    code = schema.identity()
    if code["dirty"] and out.resolve().is_relative_to(cases.OUT.resolve()):
        raise SystemExit("refusing to write a result from a dirty tree into docs/results: "
                         "commit first, or pass --out elsewhere")
    name = schema.name(case)
    r = solve(x, name)
    f = out / f"{cases.stem(case)}.json"
    schema.write(f, schema.bundle(r, case, command=sys.argv if argv is None else argv,
                                  code=code), routes=r.get("routes"))
    print(f"{name} {x.model}: " + ", ".join(f"{k}={r.get(k)}" for k in (
        "status", "solver_status", "fleet", "U", "L", "gap_rel", "certified", "elapsed")
        if k in r))


if __name__ == "__main__":
    main()
