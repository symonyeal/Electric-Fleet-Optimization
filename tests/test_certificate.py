# The result contract of Algorithms §8: status taxonomy, bounds, and the gap rule.

import math

import pytest

from checks.certificate import STATUS, certified, record

KW = dict(solver=dict(code=0, message="test"), elapsed=0.5, provenance=dict(revision="t"))


def test_status_taxonomy():
    """A solver reports one of SOLVER; the public status adds the two states only the contract
    can assign."""
    from checks.certificate import SOLVER
    assert SOLVER == {"optimal", "feasible_limit", "no_incumbent", "infeasible", "unbounded",
                      "local", "numerical", "stall", "limit"}
    assert STATUS == SOLVER | {"invalid_bound", "validation_failed"}
    with pytest.raises(ValueError):
        record("R1", "E-n22-k4", "solved", **KW)
    with pytest.raises(ValueError):
        record("R1", "E-n22-k4", "invalid_bound", **KW)       # a public state, not a solver's


@pytest.mark.parametrize("solver,U,L,val,public", [
    ("optimal", 10.0, 10.0, "replayed", "optimal"),
    ("feasible_limit", 10.0, 10.0, "replayed", "optimal"),     # the certificate decides
    ("optimal", 10.0, 9.0, "replayed", "feasible_limit"),
    ("optimal", None, 9.0, "not_available", "no_incumbent"),
    ("optimal", None, 9.0, "validation_failed", "validation_failed"),
    ("feasible_limit", 10.0, 11.0, "replayed", "invalid_bound"),
    ("infeasible", None, None, "not_available", "infeasible"),
    ("stall", 10.0, 9.0, "replayed", "stall"),
])
def test_public_status_is_derived(solver, U, L, val, public):
    r = record("R1", "x", solver, U=U, L=L, validation=val, **KW)
    assert r["status"] == public and r["solver_status"] == solver
    assert r["certified"] == (public == "optimal")
    from checks.certificate import consistent
    assert consistent(r) == []


def test_stored_contradictions_are_found():
    """The E-n22-k4 R2 bundles of eff961f: status optimal, certified false, 1.086% gap."""
    from checks.certificate import consistent
    legacy = dict(status="optimal", U=384.678, L=380.5005, certified=False, defect=None)
    assert consistent(legacy)
    r = record("R2", "x", "feasible_limit", U=384.678, L=380.5005, **KW)
    assert consistent(r) == [] and r["status"] == "feasible_limit"
    r["status"] = "optimal"
    assert consistent(r)


def test_gap_needs_both_bounds():
    r = record("R1", "x", "feasible_limit", U=10.0, **KW)
    assert r["U"] == 10.0 and r["L"] is None
    assert r["gap_abs"] is None and r["gap_rel"] is None
    r = record("R1", "x", "numerical", U=math.inf, L=3.0, **KW)
    assert r["U"] is None and r["gap_abs"] is None


def test_gap_values():
    r = record("R1", "x", "feasible_limit", U=200.0, L=150.0, **KW)
    assert r["gap_abs"] == 50.0 and r["gap_rel"] == pytest.approx(0.25)
    r = record("R1", "x", "feasible_limit", U=0.5, L=0.0, **KW)
    assert r["gap_rel"] == pytest.approx(0.5)          # max(1, |U|) = 1


def test_certification_rule():
    assert certified(100.0, 100.0 - 1e-7)
    assert not certified(100.0, 99.0)
    assert certified(100.0, 99.0, eps_abs=0, eps_rel=0.011)
    assert not certified(None, 1.0)
    assert not certified(100.0, 100.5)                  # two-sided: a crossed bound
    assert certified(100.0, 101.0, eps_abs=0, eps_rel=0.011)  # crossing within tol = 1.1
    assert not certified(100.0, 101.2, eps_abs=0, eps_rel=0.011)


def test_negative_gap_is_a_defect():
    r = record("R1", "x", "optimal", U=100.0, L=100.5, **KW)
    assert r["gap_abs"] == pytest.approx(-0.5)
    assert r["defect"] == "negative gap" and not r["certified"]
    r = record("R1", "x", "optimal", U=100.0, L=100.0 + 1e-9, **KW)
    assert r["defect"] is None and r["certified"]


def test_record_requires_solver_time_and_provenance():
    """FND-03: the solver's own code and message, elapsed time, and provenance are required."""
    with pytest.raises(TypeError):
        record("R1", "x", "optimal", U=1.0, L=1.0)
    r = record("R1", "x", "optimal", U=1.0, L=1.0, **KW)
    assert r["solver"] == KW["solver"] and r["elapsed"] == 0.5 and r["provenance"]["revision"]


def test_revision_is_fixed_at_import_and_ignores_results():
    """A bundle names the code that ran: result files, planning notes and prose are not code."""
    from pathlib import Path
    from checks.certificate import REVISION, revision
    F = [Path("docs/results/_probe.json"), Path("_probe.md")]
    for f in F:
        f.write_text("{}", encoding="utf-8")
    try:
        assert revision() == REVISION
        assert revision.__wrapped__() == REVISION   # recomputed, not the cached value
    finally:
        for f in F:
            f.unlink()


def test_provenance_names_the_host():
    """Elapsed times from different machines are not comparable; each bundle names its own."""
    from checks.certificate import provenance
    h = provenance(dict(name="x"))["host"]
    assert h["cpu"] and h["threads"] >= 1 and h["python"] and h["numpy"] and h["scipy"]
