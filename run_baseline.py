"""Run evrp-python's GSGA from an outside checkout and replay its solutions (Routing §9).

    python run_baseline.py --repo PATH E-n22-k4 [--seeds 0 1 2] [--generations 200]

The checkout must be at commit 16d3499. Its requirements pin numpy 1.24, which cannot install
on Python 3.14, so it runs against the installed numpy; loguru, matplotlib and pandas, which it
imports but does not need for solving, are replaced by inert modules. Each run's printed tours
are converted to the exchange format and replayed by checks.route; the replayed length, not
GSGA's own fitness, is the result. A replayed route set certifies its own length, so these
bundles supply upper bounds whatever their provenance; they never supply a lower bound.
"""

import argparse
import io
import random
import subprocess
import sys
import time
import types
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np

from bench import schema
from checks.certificate import REVISION, provenance
from checks.route import from_evrp_python, replay
from data.evrp import COMMIT, FETCHED, load
from run_case import key


class Inert:
    """Accepts any attribute, call or unpacking; stands in for plotting and logging."""

    def __getattr__(self, k):
        return Inert()

    def __call__(self, *a, **k):
        return Inert()

    def __iter__(self):
        return iter((Inert(), Inert()))


def stub(name):
    m = types.ModuleType(name)
    m.__getattr__ = lambda k: Inert()
    sys.modules[name] = m


def main():
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("instance")
    a.add_argument("--repo", required=True, help="evrp-python checkout at commit 16d3499")
    a.add_argument("--seeds", type=int, nargs="+", default=[0])
    a.add_argument("--generations", type=int, default=200)
    a.add_argument("--out", default="docs/results/baseline")
    x = a.parse_args()
    head = subprocess.run(["git", "-C", x.repo, "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=False).stdout.strip()
    if head != COMMIT:
        raise SystemExit(f"{x.repo} is at {head or 'no commit'}, not {COMMIT}")
    for m in ("loguru", "matplotlib", "matplotlib.pyplot", "pandas"):
        stub(m)
    sys.path.insert(0, x.repo)
    from algorithms.GSGA import GSGA              # third-party, imported after stubbing
    from objects.problem import Problem

    k = x.instance if "/" in x.instance else key(x.instance)
    p = load(k)
    for s in x.seeds:
        random.seed(s)
        np.random.seed(s)
        g = GSGA(population_size=100, generations=x.generations, crossover_prob=0.85,
                 mutation_prob=0.75, elite_rate=0.2)
        t = time.perf_counter()
        with redirect_stdout(io.StringIO()):
            sol = g.solve(Problem(str(FETCHED / f"{k}.evrp")))
        dt = time.perf_counter() - t
        routes = from_evrp_python(repr(sol), depot=p["depot"])
        rp = replay(p, routes)
        r = dict(model="GSGA", instance=p["name"], seed=s, generations=x.generations,
                 fitness=float(sol.get_tour_length()), U=rp["length"] if rp["ok"] else None,
                 replay=dict(ok=rp["ok"], defects=rp["defects"], routes=rp["routes"]),
                 routes=routes, elapsed=dt, provenance=dict(provenance(p), evrp_python=COMMIT,
                                                            revision=REVISION))
        r["bundle"] = dict(schema=schema.SCHEMA, code=schema.identity(), command=sys.argv,
                           inputs={f"data/fetched/{k}.evrp": p["sha256"]},
                           artifacts=schema.artifacts(r))
        schema.write(Path(x.out) / f"{p['name']}-GSGA-seed{s}.json", r, routes=routes)
        print(f"{p['name']} GSGA seed {s}: fitness {r['fitness']:.6f}  replay "
              f"{'ok' if rp['ok'] else rp['defects']}  length {rp['length']:.6f}  {dt:.1f}s")


if __name__ == "__main__":
    main()
