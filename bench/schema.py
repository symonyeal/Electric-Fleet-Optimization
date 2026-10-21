"""Result bundles, schema 2: what a stored result must carry to be reproduced and admitted.

A bundle is the result record of checks/certificate.py with one more key, `bundle`:

    schema ........ 2 (bundles without the key are legacy, schema 1)
    case .......... the Case signature that produced it (track, instance, model, time, until,
                    scenario)
    formulation ... the model's formulation version (VERSION in its module); a bound is compared
                    only with the formulation that produced it
    code .......... full commit hash, dirty flag, and the SHA-256 of the executed source and
                    configuration (CRLF read as LF, so a checkout's line endings do not matter)
    command ....... argv of the run
    inputs ........ SHA-256 of every input file (instance or corridor, scenario, seed routes)
    scenario ...... the complete scenario values and their digest (transit)
    versions, host  Python, numpy, SciPy (which bundles HiGHS), processor
    seeds ......... none is set: HiGHS runs at its default seed
    tolerances, time_limit (requested, the run's own budget, seconds spent)
    artifacts ..... digests of the routes (EVRP) or of the duties, plan and infrastructure
                    (transit), checked against the files on disk

check(b, case) lists every reason a bundle cannot stand for case; an empty list admits it.
A bundle from a dirty tree is never admitted, so run_case.py refuses to write one into
docs/results. Legacy bundles are admitted only through the migration manifest
docs/results/MIGRATION.json, which records for each the decision taken on 1 October 2026
(retained, provenance-limited, stale, invalid, rerun-required) and its evidence; only
`retained` admits, and only for a clean revision whose formulation is still current.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from checks.certificate import HOST, consistent, digest

SCHEMA = 2
ROOT = Path(__file__).resolve().parent.parent
CODE = ("bench", "checks", "data", "methods", "models")
CONFIG = ("run_case.py", "run_bench.py", "pyproject.toml", "requirements.txt")
MANIFEST = "MIGRATION.json"


def formulations():
    """model -> formulation version, read from the model modules."""
    from models.charge import VERSION as M2
    from models.colgen import RCC, VERSION as R2
    from models.fleet import VERSION as M1
    from models.network import VERSION as M0
    from models.recharge import VERSION as R3
    from models.route import VERSION as R
    return {**R, "R2-ipm": R2, "R2-simplex": R2, "R2-rcc": RCC, "M0": M0, "M1": M1, "M2": M2,
            "R3": R3}


def sha256(path):
    """SHA-256 of a file, CRLF read as LF for text (a Windows checkout of the same commit hashes
    the same); raw bytes for the fetched benchmark files."""
    b = Path(path).read_bytes()
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def source_digest(root=ROOT):
    """SHA-256 over (path, sha256) of every executed source and configuration file."""
    files = sorted(p for d in CODE for p in (Path(root) / d).rglob("*.py")
                   if "__pycache__" not in p.parts)
    files += [Path(root) / f for f in CONFIG if (Path(root) / f).exists()]
    return digest([[p.relative_to(root).as_posix(), sha256(p)] for p in files])


def identity(root=ROOT):
    """The code a run executes: full commit, dirty flag (result bundles, planning notes and
    prose are not code), source digest."""
    git = lambda *a: subprocess.run(["git", "-C", str(root), *a], capture_output=True,
                                    text=True, check=False).stdout.strip()
    dirty = git("status", "--porcelain", "--", ".", ":!docs/results", ":!.planning", ":!*.md")
    return dict(commit=git("rev-parse", "HEAD"), dirty=bool(dirty), source=source_digest(root))


def name(case):
    """The instance name a run records: the EVRP name, or route100[-scenario][-untilHh]."""
    if case.track == "evrp":
        return case.instance.rsplit("/", 1)[-1]
    n = case.instance + (f"-{case.scenario}" if case.scenario else "")
    return n + (f"-until{case.until:g}h" if case.until is not None else "")


def inputs(case, out=None):
    """(instance data, scenario values or None, {input file: sha256}) for case. R2's seed routes
    are always docs/results/baseline, where run_case.py reads them."""
    if case.track == "evrp":
        from data.evrp import KEYS, SHA, load
        k = case.instance if "/" in case.instance else next(
            k for k in KEYS if k.endswith("/" + case.instance))
        p = load(k)
        files = {f"data/fetched/{k}.evrp": SHA[f"{k}.evrp"]}
        if case.model.startswith("R2"):                 # run_case seeds R2 with these routes
            for f in sorted(Path("docs/results/baseline").glob(f"{p['name']}-*.routes")):
                files[f.as_posix()] = sha256(f)
        return p, None, files
    from data.scenario import load
    fx = Path(f"tests/fixtures/{case.instance}.json")
    c = json.loads(fx.read_text(encoding="utf-8"))
    sc = Path(f"data/scenarios/{case.instance}"
              + (f"-{case.scenario}" if case.scenario else "") + ".toml")
    v, _ = load(sc)
    if case.until is not None:
        c = dict(c, trips=[t for t in c["trips"] if t["dep"] < 3600 * case.until])
    return c, v, {fx.as_posix(): sha256(fx), sc.as_posix(): sha256(sc)}


def canon(x):
    """x as it reads back from JSON (tuples become lists, integer keys strings)."""
    return json.loads(json.dumps(x, default=_plain))


def _plain(v):
    return v.item() if hasattr(v, "item") else str(v)


def artifacts(r):
    """Digests of what a verdict replays: the routes, or the duties, plan and infrastructure."""
    a = {}
    if r.get("routes"):
        a["routes"] = digest(canon(r["routes"]))
    if r.get("duties") is not None:
        a["schedule"] = digest(canon(dict(duties=r["duties"], plan=r.get("plan"),
                                          infra=r.get("infra"))))
    return a


def bundle(r, case, command, code=None, out=None):
    """The record r of case as a schema-2 bundle."""
    import numpy
    import scipy
    _, v, files = inputs(case, out)
    return dict(r, bundle=dict(
        schema=SCHEMA, case=case.signature(), formulation=formulations()[case.model],
        code=code or identity(), command=list(command), inputs=files,
        scenario=None if v is None else dict(values=v, digest=digest(v)),
        versions=dict(python=sys.version.split()[0], numpy=numpy.__version__,
                      scipy=scipy.__version__, highs="bundled with SciPy"),
        host=HOST, seeds=dict(highs="default"), tolerances=r.get("tolerances"),
        time_limit=dict(requested=case.time, budget=r.get("time_budget"), spent=r.get("elapsed")),
        artifacts=artifacts(r)))


def check(b, case, out=None):
    """Every reason bundle b cannot stand for case; [] admits it. Reasons: legacy, case,
    formulation, dirty, inputs, scenario, contract, status, artifact."""
    if not isinstance(b, dict) or "bundle" not in b:
        return ["legacy"]
    m, bad = b["bundle"], []
    if m.get("schema") != SCHEMA:
        bad.append("legacy")
    if m.get("case") != case.signature():
        bad.append("case")
    if m.get("formulation") != formulations().get(case.model):
        bad.append("formulation")
    if (m.get("code") or {}).get("dirty", True):
        bad.append("dirty")
    _, v, files = inputs(case, out)
    if m.get("inputs") != files:
        bad.append("inputs")
    if v is not None and (m.get("scenario") or {}).get("digest") != digest(v):
        bad.append("scenario")
    if consistent(b) or b.get("defect"):
        bad.append("contract")
    if b.get("status") in ("invalid_bound", "validation_failed"):
        bad.append("status")
    if m.get("artifacts") != artifacts(_with_routes(b, case, out)):
        bad.append("artifact")
    return bad


def _with_routes(b, case, out):
    """b with its routes read back from the .routes file beside it, when it has one."""
    if not b.get("routes"):
        return b
    from bench.cases import path
    from checks.route import read_routes
    f = path(case, out or "docs/results").with_suffix(".routes")
    return dict(b, routes=read_routes(f) if f.exists() else None)


def legacy(b, entry, case):
    """Reasons a legacy bundle cannot be admitted under its migration entry; [] admits it.
    Admission needs the decision `retained`, the formulation still current, a clean revision,
    the instance file it names, no contradiction in its own fields, and its routes unchanged."""
    if not entry:
        return ["no migration entry"]
    bad = []
    if entry.get("decision") != "retained":
        bad.append(entry.get("decision", "no decision"))
    if entry.get("formulation") != formulations().get(case.model):
        bad.append("formulation")
    pv = b.get("provenance") or {}
    if "+dirty" in (pv.get("revision") or "+dirty"):
        bad.append("dirty")
    if case.track == "evrp":
        from data.evrp import SHA
        k = pv.get("key") or ""
        if pv.get("sha256") != SHA.get(f"{k}.evrp"):
            bad.append("inputs")
    if consistent(b) or b.get("defect"):
        bad.append("contract")
    if entry.get("artifacts", {}).get("routes") and b.get("routes") and \
            digest(canon(b["routes"])) != entry["artifacts"]["routes"]:
        bad.append("artifact")
    return bad


def manifest(out=None):
    f = Path(out or "docs/results") / MANIFEST
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def read(path):
    """The bundle at path, or None if absent or unreadable."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write(path, b, routes=None):
    """Write the bundle (and its routes) atomically: each file goes to an adjacent .partial file
    first and is moved into place, so an interrupted run never leaves a half-written bundle."""
    from checks.route import write_routes
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if routes:
        f = path.with_suffix(".routes")
        tmp = f.with_name(f.name + ".partial")
        write_routes(tmp, routes)
        os.replace(tmp, f)
    tmp = path.with_name(path.name + ".partial")
    tmp.write_text(json.dumps(b, indent=1, default=_plain) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_text(path, text):
    """A report written atomically, the same way."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".partial")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
