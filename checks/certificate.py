"""Result contract (Algorithms §8).

A minimization result carries a feasible objective U, a valid lower bound L, and a gap only
when both are finite. A gap below -tolerance is a defect to investigate, never clamped.
"""

import functools
import math
import subprocess

STATUS = {"optimal", "feasible_limit", "no_incumbent", "infeasible", "unbounded",
          "local", "numerical", "stall", "limit"}


def _fin(v):
    return None if v is None or not math.isfinite(v) else float(v)


def certified(U, L, eps_abs=1e-6, eps_rel=1e-6):
    """U - L <= eps_abs + eps_rel max(1, |U|), with U and L finite."""
    U, L = _fin(U), _fin(L)
    return U is not None and L is not None and U - L <= eps_abs + eps_rel * max(1.0, abs(U))


def record(model, instance, status, U=None, L=None, *, solver, elapsed, provenance,
           eps_abs=1e-6, eps_rel=1e-6, **kw):
    """One solve as a JSON-serializable dict.

    INPUT   status ....... one of STATUS
            U, L ......... feasible objective and valid lower bound; None or inf when absent
            solver ....... the solver's own code and message
            elapsed ...... seconds; provenance: revision, data checksums, parameters
            kw ........... decisions, residuals
    """
    if status not in STATUS:
        raise ValueError(f"status {status!r} not in {sorted(STATUS)}")
    U, L = _fin(U), _fin(L)
    g = None if U is None or L is None else U - L
    tol = eps_abs + eps_rel * max(1.0, abs(U)) if U is not None else 0.0
    return dict(model=model, instance=instance, status=status, U=U, L=L, gap_abs=g,
                gap_rel=None if g is None else g / max(1.0, abs(U)),
                certified=certified(U, L, eps_abs, eps_rel),
                defect="negative gap" if g is not None and g < -tol else None,
                solver=solver, elapsed=elapsed, provenance=provenance, **kw)


@functools.cache
def revision():
    """Short git revision, with '+dirty' when the code differs from it (result bundles and
    planning notes are not code)."""
    git = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True,
                                    check=False).stdout.strip()
    code = git("status", "--porcelain", "--", ".", ":!docs/results", ":!.planning")
    return git("rev-parse", "--short", "HEAD") + ("+dirty" if code else "")


REVISION = revision()                     # the code this process runs, fixed at import


def provenance(p, **params):
    return dict(revision=REVISION, instance=p["name"], key=p.get("key"), sha256=p.get("sha256"),
                params=params)
