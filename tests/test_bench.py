# The experiment matrix and its report: case naming, segment counting, and the fail-closed
# bundle checks of bench/schema.py.

import pytest

from bench import cases, schema
from bench.collect import segments
from bench.verdict import evrp


def test_segments_counts_runs_of_two_or_more_stations():
    p = dict(F=[0, 4, 5, 6], depot=0)                  # the depot is also a station
    R = [[1, 2, 5, 6, 3, 1],                           # one segment through stations 5, 6
         [1, 5, 6, 7, 4, 1],                           # one segment through three
         [1, 5, 2, 6, 1]]                              # single stations only
    assert segments(p, R) == 2


def test_case_bundles_are_named_as_run_case_writes_them():
    k = {(c.instance, c.model, c.until, c.scenario): c for c in cases.CASES}
    assert cases.path(k["E-n22-k4", "R2-ipm", None, None]).name == "E-n22-k4-R2-ipm.json"
    assert cases.path(k["route100", "M1", 8.0, None]).name == "route100-until8h-M1.json"
    assert cases.path(k["route100", "M0", None, None]).name == "route100-M0.json"
    assert [cases.path(c).name for c in cases.CASES if c.scenario] == [
        "route100-rs1640-stress-M1.json", "route100-rs1650-stress-M1.json",
        "route100-rs1640-M1.json", "route100-rs1650-M1.json"]


def test_command_reaches_the_same_bundle(tmp_path):
    c = cases.Case("transit", "route100", "M1", 600, until=8.0, scenario="rs1640")
    cmd = cases.command(c, tmp_path)
    assert cmd[2:5] == ["transit", "route100", "M1"]
    assert cmd[cmd.index("--out") + 1] == str(tmp_path / "transit")
    assert cmd[cmd.index("--until") + 1] == "8" and cmd[cmd.index("--scenario") + 1] == "rs1640"


def test_case_rejects_a_model_of_the_other_track():
    with pytest.raises(ValueError):
        cases.Case("transit", "route100", "R1", 60)


def test_inputs_read_the_scenario_of_the_case():
    _, v, files = schema.inputs(cases.Case("transit", "route100", "M1", 600,
                                           scenario="rs1640"))
    assert v["cost"]["peak_from"] == 6.0 and "data/scenarios/route100-rs1640.toml" in files
    c, v, _ = schema.inputs(cases.Case("transit", "route100", "M1", 600, until=8.0))
    assert "peak_from" not in v["cost"] and len(c["trips"]) == 54


def test_source_digest_ignores_line_endings(tmp_path):
    for d in schema.CODE:
        (tmp_path / d).mkdir()
    (tmp_path / "models" / "a.py").write_bytes(b"x = 1\r\ny = 2\r\n")
    a = schema.source_digest(tmp_path)
    (tmp_path / "models" / "a.py").write_bytes(b"x = 1\ny = 2\n")
    assert schema.source_digest(tmp_path) == a
    (tmp_path / "models" / "a.py").write_bytes(b"x = 1\ny = 3\n")
    assert schema.source_digest(tmp_path) != a


def test_atomic_write_leaves_no_partial(tmp_path):
    f = tmp_path / "x" / "b.json"
    schema.write(f, dict(a=1), routes=[[1, 2, 1]])
    assert schema.read(f) == dict(a=1) and f.with_suffix(".routes").exists()
    assert not list(tmp_path.rglob("*.partial"))


def test_verdicts_use_the_two_sided_rule():
    assert evrp(500.0, [400.0], [400.0])["verdict"] == "certified optimal; report value not optimal"
    assert evrp(500.0, [450.0], [400.0])["verdict"].startswith("inconsistent bounds")
    assert evrp(380.0, [390.0], [])["verdict"] == "open; report value below a valid bound"
    v = evrp(384.678035, [380.5], [384.678093])
    assert v["verdict"] == "bracketed" and v["gap"] == pytest.approx(0.010861, abs=1e-6)


def test_legacy_bundles_need_a_retaining_migration_entry():
    k = cases.Case("evrp", "E-n23-k3", "R2-ipm", 1800)
    b = dict(status="feasible_limit", U=571.9, L=561.7, certified=False, defect=None,
             provenance=dict(revision="9c00dc3", key="evrp-2019/E-n23-k3",
                             sha256="0" * 64))
    assert schema.legacy(b, None, k) == ["no migration entry"]
    e = dict(decision="retained", formulation="R2/1", bound_source="r22_exact_pricing")
    assert schema.legacy(b, e, k) == ["inputs"]                  # the instance file differs
    assert "provenance-limited" in schema.legacy(
        dict(b, provenance=dict(b["provenance"], revision="x+dirty")),
        dict(e, decision="provenance-limited"), k)
