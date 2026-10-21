"""The experiment matrix of Validation §3: which cases exist, where each writes its bundle, and
how a set of them is run. Running is fail-closed: a child process that exits nonzero, or a
bundle that does not pass bench/schema.check, fails the whole request.
"""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

OUT = Path("docs/results")
E = ["E-n22-k4", "E-n23-k3", "E-n30-k3", "E-n33-k4", "E-n51-k5", "E-n76-k7", "E-n101-k8"]
PAIRS = {"evrp": ("R0", "R1", "R1-TR", "R2-ipm", "R2-simplex", "R2-rcc"), "transit": ("M0", "M1")}


@dataclass(frozen=True)
class Case:
    """One run of run_case.py: track, instance, model, its time limit in seconds, and for transit
    the cut-off hour `until` and the scenario suffix (data/scenarios/<instance>-<scenario>.toml)."""
    track: str
    instance: str
    model: str
    time: float
    until: float | None = None
    scenario: str | None = None

    def __post_init__(self):
        if self.model not in PAIRS.get(self.track, ()):
            raise ValueError(f"model {self.model} does not belong to track {self.track}")

    @property
    def key(self):
        """track/instance/model[/untilH][/scenario], the name --only selects by."""
        k = f"{self.track}/{self.instance}/{self.model}"
        k += f"/until{self.until:g}" if self.until is not None else ""
        return k + (f"/{self.scenario}" if self.scenario else "")

    def signature(self):
        return asdict(self)


CASES = [*[Case("evrp", n, m, t) for n in E for m, t in (("R0", 600), ("R1", 600),
                                                          ("R2-ipm", 1800), ("R2-simplex", 1800),
                                                          ("R2-rcc", 1800))],
         *[Case("transit", "route100", m, t, until=u) for u, t in ((8.0, 600), (10.0, 900),
                                                                   (None, 1800))
           for m in ("M0", "M1")],
         *[Case("transit", "route100", "M1", t, scenario=s) for s, t in (
             ("rs1640-stress", 1800), ("rs1650-stress", 1800), ("rs1640", 600), ("rs1650", 600))]]


def stem(case):
    """The bundle's file stem: <instance>[-<scenario>][-until<H>h]-<model>."""
    n = case.instance + (f"-{case.scenario}" if case.scenario else "")
    n += f"-until{case.until:g}h" if case.until is not None else ""
    return f"{n}-{case.model}"


def path(case, out=OUT):
    return Path(out) / case.track / f"{stem(case)}.json"


def command(case, out=OUT):
    """The run_case.py call that writes case's bundle under out."""
    cmd = [sys.executable, "run_case.py", case.track, case.instance, case.model,
           "--time", f"{case.time:g}", "--out", str(Path(out) / case.track)]
    if case.until is not None:
        cmd += ["--until", f"{case.until:g}"]
    if case.scenario:
        cmd += ["--scenario", case.scenario]
    return cmd


def launch(cmd):
    """Run one child process; its exit code."""
    return subprocess.run(cmd, check=False).returncode


def missing(cases, out=OUT):
    """The cases with no valid matching bundle under out: absent, unreadable, legacy, stale or
    contradictory bundles are all rerun."""
    from bench.schema import check, read
    return [k for k in cases if (b := read(path(k, out))) is None or check(b, k, out)]


def run(cases, jobs=1, out=OUT):
    """Run cases, jobs at a time. OUTPUT [(case, problem)] for every child that failed or wrote a
    bundle that does not pass the schema check; empty when all succeeded."""
    from bench.schema import check, read

    def one(k):
        code = launch(command(k, out))
        if code != 0:
            return k, f"run_case.py exited with {code}"
        b = read(path(k, out))
        if b is None:
            return k, "no readable bundle was written"
        bad = check(b, k, out)
        return (k, "bundle fails the check: " + ", ".join(bad)) if bad else None

    with ThreadPoolExecutor(jobs) as X:
        return [r for r in X.map(one, cases) if r]


def select(cases, only):
    """The cases whose key is in only (all when only is empty); an unknown key is an error."""
    if not only:
        return list(cases)
    keys = {k.key: k for k in cases}
    if bad := [o for o in only if o not in keys]:
        raise SystemExit(f"unknown case {bad}; known: {sorted(keys)}")
    return [keys[o] for o in only]
