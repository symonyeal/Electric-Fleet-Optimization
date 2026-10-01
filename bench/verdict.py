"""Verdicts from admitted results, as pure functions: no file is read here.

An upper bound needs no provenance: a route set or schedule that the independent replay accepts
certifies its own cost, whoever produced it. A lower bound cannot be replayed, so it counts only
when its bundle passed bench/schema.check (or a migration entry retained it) and its source is
one this project trusts to bound the published problem. The textbook IPM node bounds and the
educational branch-and-bound are not among them (Algorithms §4): their results stay out of
every published verdict.
"""

from checks.certificate import gap_state

TRUSTED = {"highs_dual", "r22_exact_pricing", "oa_master_dual", "matching"}


def evrp(report, lower, upper, eps=1e-6):
    """The verdict on a published EVRP value.

    INPUT   report ... the value the benchmark publishes
            lower .... admitted lower bounds on R1 (R0's count: z(R0) <= z(R1), Routing §3)
            upper .... replayed route lengths
    OUTPUT  L (best), U (best), gap (relative), verdict
    """
    L, U = (max(lower) if lower else None), (min(upper) if upper else None)
    g = gap_state(U, L, eps, eps)
    v = {"closed": "certified optimal", "crossed": "inconsistent bounds"}.get(
        g, "bracketed" if U is not None and L is not None else "open")
    if U is not None and report > U + eps * (1 + report):
        v += "; report value not optimal"
    elif L is not None and report < L - eps * (1 + report):
        v += "; report value below a valid bound"
    return dict(L=L, U=U, gap=None if L is None or U is None else (U - L) / max(1, abs(U)),
                verdict=v)


def admitted_lower(results):
    """The lower bounds of admitted results [(model, record)] whose source is trusted."""
    return [r["L"] for _, r in results if r.get("L") is not None
            and r.get("bound_source", "highs_dual") in TRUSTED]
