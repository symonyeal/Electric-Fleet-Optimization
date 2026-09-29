# The result contract of Algorithms §8: status taxonomy, bounds, and the gap rule.

import math

import pytest

from checks.certificate import STATUS, certified, record

KW = dict(solver=dict(code=0, message="test"), elapsed=0.5, provenance=dict(revision="t"))


def test_status_taxonomy():
    assert STATUS == {"optimal", "feasible_limit", "no_incumbent", "infeasible", "unbounded",
                      "local", "numerical", "stall", "limit"}
    with pytest.raises(ValueError):
        record("R1", "E-n22-k4", "solved", **KW)


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


def test_negative_gap_is_a_defect():
    r = record("R1", "x", "optimal", U=100.0, L=100.5, **KW)
    assert r["gap_abs"] == pytest.approx(-0.5)
    assert r["defect"] == "negative gap"
    assert record("R1", "x", "optimal", U=100.0, L=100.0 + 1e-9, **KW)["defect"] is None


def test_record_requires_solver_time_and_provenance():
    """FND-03: the solver's own code and message, elapsed time, and provenance are required."""
    with pytest.raises(TypeError):
        record("R1", "x", "optimal", U=1.0, L=1.0)
    r = record("R1", "x", "optimal", U=1.0, L=1.0, **KW)
    assert r["solver"] == KW["solver"] and r["elapsed"] == 0.5 and r["provenance"]["revision"]


def test_revision_is_fixed_at_import_and_ignores_results():
    """A bundle names the code that ran: result files and planning notes are not code."""
    from pathlib import Path
    from checks.certificate import REVISION, revision
    f = Path("docs/results/_probe.json")
    f.write_text("{}", encoding="utf-8")
    try:
        assert revision() == REVISION or not REVISION.endswith("+dirty")
        assert revision().endswith("+dirty") == REVISION.endswith("+dirty")
    finally:
        f.unlink()
