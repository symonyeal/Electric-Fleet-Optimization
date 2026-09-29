# Report helpers of run_bench.py.

from run_bench import runs


def test_runs_counts_segments_with_two_or_more_stations():
    p = dict(F=[0, 4, 5, 6], depot=0)                  # the depot is also a station
    R = [[1, 2, 5, 6, 3, 1],                           # one segment through stations 5, 6
         [1, 5, 6, 7, 4, 1],                           # one segment through three
         [1, 5, 2, 6, 1]]                              # single stations only
    assert runs(p, R) == 2


def test_case_bundles_are_named_as_run_case_writes_them():
    """--missing skips a case by its bundle path; the committed bundles fix the naming."""
    from run_bench import CASES, out
    k = {(c[1], c[2], c[4]): c for c in CASES}
    assert out(k["E-n22-k4", "R2-ipm", ()]).exists()
    assert out(k["route100", "M1", ("--until", "8")]).exists()
    assert out(k["route100", "M0", ()]).exists()
