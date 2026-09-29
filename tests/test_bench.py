# Report helpers of run_bench.py.

from run_bench import runs


def test_runs_counts_segments_with_two_or_more_stations():
    p = dict(F=[0, 4, 5, 6], depot=0)                  # the depot is also a station
    R = [[1, 2, 5, 6, 3, 1],                           # one segment through stations 5, 6
         [1, 5, 6, 7, 4, 1],                           # one segment through three
         [1, 5, 2, 6, 1]]                              # single stations only
    assert runs(p, R) == 2
