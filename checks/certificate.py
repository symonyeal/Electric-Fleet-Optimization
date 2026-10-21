"""Result contract (Algorithms §8).

A minimization result carries a feasible objective U, a valid lower bound L, and a gap only
when both are finite. Four fields keep apart what each party established:

    solver_status ......... the method's own termination (HiGHS, SciPy, the textbook IPM, OA)
    validation_status ..... replayed: U is the cost of a solution the independent replay
                            accepted; validation_failed: a candidate was rejected (U absent),
                            or the model's objective disagrees with the replayed cost (U kept,
                            the bound in doubt); not_available
    certificate_status .... certified: -tol <= U - L <= tol with a replayed U; open; invalid_bound:
                            L > U + tol; not_applicable: no bound is defined (infeasible, local)
    status ................ the public state, derived from the three: `optimal` iff certified

with tol = eps_abs + eps_rel max(1, |U|). A crossing within tol is floating-point noise and is
reported raw, never clamped; a larger one is a defect, never certified.
"""

import functools
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from importlib.metadata import version

SOLVER = {"optimal", "feasible_limit", "no_incumbent", "infeasible", "unbounded", "local",
          "numerical", "stall", "limit"}
STATUS = SOLVER | {"invalid_bound", "validation_failed"}
VALIDATION = {"replayed", "validation_failed", "not_available"}
CERTIFICATE = {"certified", "open", "invalid_bound", "not_applicable"}


def _fin(v):
    return None if v is None or not math.isfinite(v) else float(v)


def tol(U, eps_abs=1e-6, eps_rel=1e-6):
    """eps_abs + eps_rel max(1, |U|); eps_abs alone when U is absent."""
    U = _fin(U)
    return eps_abs + eps_rel * max(1.0, abs(U)) if U is not None else eps_abs


def gap_state(U, L, eps_abs=1e-6, eps_rel=1e-6):
    """The two-sided rule every stopping test uses: closed (|U - L| <= tol), crossed
    (L > U + tol, an invalid bound), or open (either side absent, or U - L > tol)."""
    U, L = _fin(U), _fin(L)
    if U is None or L is None:
        return "open"
    t = tol(U, eps_abs, eps_rel)
    return "crossed" if U - L < -t else "closed" if U - L <= t else "open"


def certified(U, L, eps_abs=1e-6, eps_rel=1e-6):
    """-tol <= U - L <= tol, with U and L finite."""
    return gap_state(U, L, eps_abs, eps_rel) == "closed"


def classify(solver_status, U, L, validation, eps_abs=1e-6, eps_rel=1e-6):
    """(certificate_status, status) from the solver's termination, the bounds and the replay."""
    g = gap_state(U, L, eps_abs, eps_rel)
    if g == "crossed":
        cert = "invalid_bound"
    elif g == "closed" and validation == "replayed":
        cert = "certified"
    elif _fin(U) is None and _fin(L) is None and solver_status in ("infeasible", "unbounded",
                                                                   "local"):
        cert = "not_applicable"
    else:
        cert = "open"
    if cert == "invalid_bound":
        return cert, "invalid_bound"
    if cert == "certified":
        return cert, "optimal"
    if validation == "validation_failed":
        return cert, "validation_failed"
    if solver_status in ("optimal", "feasible_limit"):
        return cert, "feasible_limit" if _fin(U) is not None else "no_incumbent"
    return cert, solver_status


def record(model, instance, status, U=None, L=None, *, solver, elapsed, provenance,
           eps_abs=1e-6, eps_rel=1e-6, validation=None, objective=None, bound_source=None,
           **kw):
    """One solve as a JSON-serializable dict.

    INPUT   status ....... the solver's termination, one of SOLVER
            U, L ......... feasible objective and valid lower bound; None or inf when absent
            validation ... one of VALIDATION; None means replayed when U is given, else
                           not_available
            objective .... the model's own objective at the returned solution; it must agree
                           with the replayed U within tol, or the record is validation_failed
            bound_source . what produced L (highs_dual, r22_exact_pricing, r24_exact_pricing,
                           oa_master_dual, ...)
            solver ....... the solver's own code and message
            elapsed ...... seconds; provenance: revision, data checksums, parameters
            kw ........... decisions, residuals
    """
    if status not in SOLVER:
        raise ValueError(f"solver status {status!r} not in {sorted(SOLVER)}")
    U, L = _fin(U), _fin(L)
    if validation is None:
        validation = "replayed" if U is not None else "not_available"
    if validation not in VALIDATION:
        raise ValueError(f"validation {validation!r} not in {sorted(VALIDATION)}")
    defects = []
    if objective is not None and U is not None and abs(objective - U) > tol(U, eps_abs, eps_rel):
        defects.append(f"objective {objective:.9g} disagrees with replayed {U:.9g}")
        validation = "validation_failed"          # U is still a replayed cost; L is in doubt
    cert, public = classify(status, U, L, validation, eps_abs, eps_rel)
    if cert == "invalid_bound":
        defects.append("negative gap")
    g = None if U is None or L is None else U - L
    return dict(model=model, instance=instance, status=public, solver_status=status,
                validation_status=validation, certificate_status=cert, U=U, L=L, gap_abs=g,
                gap_rel=None if g is None else g / max(1.0, abs(U)),
                certified=cert == "certified", defect="; ".join(defects) or None,
                bound_source=bound_source if L is not None else None,
                tolerances=dict(eps_abs=eps_abs, eps_rel=eps_rel), objective=objective,
                solver=solver, elapsed=elapsed, provenance=provenance, **kw)


def consistent(r):
    """The contract holds within a stored record: its public status, certificate and flags are
    what classify() derives from its own fields. OUTPUT the list of contradictions."""
    out = []
    t = r.get("tolerances") or dict(eps_abs=1e-6, eps_rel=1e-6)
    if r.get("certified") and r.get("defect"):
        out.append("certified with a defect")
    if (r.get("status") == "optimal") != bool(r.get("certified")):
        out.append(f"status {r.get('status')} with certified={r.get('certified')}")
    if "solver_status" in r:
        cert, st = classify(r["solver_status"], r.get("U"), r.get("L"),
                            r.get("validation_status"), t["eps_abs"], t["eps_rel"])
        if (cert, st) != (r.get("certificate_status"), r.get("status")):
            out.append(f"stored {r.get('certificate_status')}/{r.get('status')}, derived "
                       f"{cert}/{st}")
    elif gap_state(r.get("U"), r.get("L"), t["eps_abs"], t["eps_rel"]) == "crossed":
        out.append("negative gap")
    return out


@functools.cache
def revision():
    """Short git revision, with '+dirty' when the code differs from it (result bundles,
    planning notes and prose are not code; run_bench.py rewrites README.md between cases)."""
    git = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True,
                                    check=False).stdout.strip()
    code = git("status", "--porcelain", "--", ".", ":!docs/results", ":!.planning", ":!*.md")
    return git("rev-parse", "--short", "HEAD") + ("+dirty" if code else "")


REVISION = revision()                     # the code this process runs, fixed at import


def host():
    """The processor and toolchain a result was measured on: elapsed times and time-limited
    bounds are comparable only between results that share them."""
    cpu = platform.processor()
    if sys.platform == "win32":
        import winreg
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        cpu = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
    return dict(cpu=cpu, threads=os.cpu_count(), python=platform.python_version(),
                numpy=version("numpy"), scipy=version("scipy"))


HOST = host()


def digest(obj):
    """SHA-256 of obj as canonical JSON (sorted keys, no whitespace): the identity of a corridor,
    a scenario or a route set, independent of file formatting."""
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=float)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def provenance(p, **params):
    return dict(revision=REVISION, host=HOST, instance=p["name"], key=p.get("key"),
                sha256=p.get("sha256"), params=params)
