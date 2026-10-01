"""The experiment matrix of Validation §3: tables and figures from the admitted result bundles.

    python run_bench.py            tables (docs/results/README.md) and figures (docs/results/fig)
    python run_bench.py --run      first run every case of bench/cases.py
    python run_bench.py --grid     first recompute the charging-physics grid (M2/M1, R3/R1)
        --missing                  only the cases and grid rows with no valid matching bundle
        --only KEY                 only this case (repeatable), e.g. transit/route100/M0/until8
        --jobs N                   N cases at a time (elapsed times are then under shared load)

Fail-closed: if a requested case exits nonzero or writes a bundle that does not pass the schema
check, the command fails and rewrites no report. Cases and the grid refuse a dirty tree. The
work is split: bench/cases.py runs cases, bench/schema.py defines and checks bundles,
bench/collect.py admits them and replays every U, bench/verdict.py decides, bench/report.py and
bench/plots.py render.
"""

import argparse
from pathlib import Path

from bench import cases, schema
from bench.collect import collect
from bench.plots import figures
from bench.report import results, summary


def parse(argv):
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--run", action="store_true")
    a.add_argument("--grid", action="store_true")
    a.add_argument("--missing", action="store_true")
    a.add_argument("--only", action="append", default=[])
    a.add_argument("--jobs", type=int, default=1)
    return a.parse_args(argv)


def write_summary(readme, lines):
    s = Path(readme).read_text(encoding="utf-8")
    i, j = s.index("<!-- results:begin -->"), s.index("<!-- results:end -->")
    schema.write_text(readme, s[:i] + "<!-- results:begin -->\n" + "\n".join(lines) + "\n"
                      + s[j:])


def main(argv=None, out=cases.OUT, readme=Path("README.md")):
    x = parse(argv)
    out = Path(out)
    todo = cases.select(cases.CASES, x.only)
    if (x.run or x.grid) and schema.identity()["dirty"] and out.resolve() == \
            cases.OUT.resolve():
        raise SystemExit("refusing to run cases into docs/results from a dirty tree; commit first")
    if x.run:
        if x.missing:
            todo = cases.missing(todo, out)
        failed = cases.run(todo, x.jobs, out)
        if failed:
            for k, why in failed:
                print(f"FAILED {k.key}: {why}")
            raise SystemExit(f"{len(failed)} of {len(todo)} requested cases failed; no report "
                             "was rewritten")
    if x.grid:
        from bench.grid import grid
        grid(out, x.missing)
    D = collect(out)
    figures(D, out)
    schema.write_text(out / "README.md", results(D))
    write_summary(readme, summary(D))
    print((out / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
