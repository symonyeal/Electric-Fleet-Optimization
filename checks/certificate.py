"""Result contract (Algorithms §8).

A minimization result carries a feasible objective U, a valid lower bound L, and a gap only
when both are finite. A gap below -tolerance is a defect to investigate, never clamped.
"""

import math

STATUS = {"optimal", "feasible_limit", "no_incumbent", "infeasible", "unbounded",
          "local", "numerical", "stall", "limit"}


def _fin(v):
    return None if v is None or not math.isfinite(v) else float(v)


def certified(U, L, eps_abs=1e-6, eps_rel=1e-6):
    """U - L <= eps_abs + eps_rel max(1, |U|), with U and L finite."""
    U, L = _fin(U), _fin(L)
    return U is not None and L is not None and U - L <= eps_abs + eps_rel * max(1.0, abs(U))


def record(model, instance, status, U=None, L=None, eps_abs=1e-6, eps_rel=1e-6, **kw):
    """One solve as a JSON-serializable dict.

    INPUT   status ... one of STATUS
            U, L ..... feasible objective and valid lower bound; None or inf when absent
            kw ....... decisions, residuals, solver code and message, elapsed time, provenance
    """
    if status not in STATUS:
        raise ValueError(f"status {status!r} not in {sorted(STATUS)}")
    U, L = _fin(U), _fin(L)
    g = None if U is None or L is None else U - L
    tol = eps_abs + eps_rel * max(1.0, abs(U)) if U is not None else 0.0
    return dict(model=model, instance=instance, status=status, U=U, L=L, gap_abs=g,
                gap_rel=None if g is None else g / max(1.0, abs(U)),
                certified=certified(U, L, eps_abs, eps_rel),
                defect="negative gap" if g is not None and g < -tol else None, **kw)
