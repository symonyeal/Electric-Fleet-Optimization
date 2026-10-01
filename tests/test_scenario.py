# Declared scenarios (Data §3): every value carries a unit and a source or `illustrative`.

import pytest

from data.scenario import load, slot

S = "data/scenarios/route100.toml"


def test_route100_loads_with_provenance():
    v, prov = load(S)
    assert v["battery"]["B"] == 250.0 and v["time"]["delta"] == 300.0
    assert v["sites"]["marpole"]["stops"] == ["745", "12027"]
    assert all(unit and src for unit, src in prov.values())
    assert prov["battery.B"] == ("kWh", "illustrative")


@pytest.mark.parametrize("bad", ['x = {value = 1.0, source = "illustrative"}',
                                 'x = {value = 1.0, unit = "kW"}',
                                 'x = {value = 1.0, unit = "kW", source = ""}',
                                 'x = 1.0'])
def test_values_need_unit_and_source(tmp_path, bad):
    f = tmp_path / "s.toml"
    f.write_text(f"[t]\n{bad}\n")
    with pytest.raises(ValueError):
        load(f)


def test_slot_is_floor_of_time_over_delta():
    assert slot(0, 300) == 0 and slot(299, 300) == 0 and slot(300, 300) == 1
    assert slot(95000, 300) == 316                      # past midnight stays on the grid


# Domains (Data §3): each rule refused on its own, before any row is built.

def _bad(path, value):
    import copy
    from data.scenario import load as ld
    v = copy.deepcopy(ld(S)[0])
    d = v
    for k in path[:-1]:
        d = d[k]
    d[path[-1]] = value
    return v


@pytest.mark.parametrize("path,value", [
    (("charger", "eta"), 0.0), (("charger", "eta"), 1.2),
    (("battery", "reserve"), -0.1), (("battery", "s0"), 0.1),        # s0 below the reserve
    (("battery", "smax"), 0.85), (("battery", "smax"), 1.1),         # smax below s0; above 1
    (("battery", "B"), 0.0), (("charger", "P"), -1.0), (("time", "delta"), 0.0),
    (("time", "window"), 0.0), (("deadhead", "speed"), 0.0), (("battery", "kappa"), -0.1),
    (("charger", "alpha"), -1e-5), (("charger", "gamma"), -1.0),
    (("cost", "energy"), -0.01), (("cost", "peak"), -0.5), (("cost", "rider"), -1.0),
    (("sites", "marpole", "nbar"), 2.5), (("sites", "marpole", "nbar"), float("inf")),
    (("sites", "marpole", "hbar"), float("inf")), (("sites", "marpole", "L"), -1.0),
    (("battery", "B"), float("nan")),
])
def test_values_outside_their_domain_are_refused(path, value):
    from data.scenario import validate
    with pytest.raises(ValueError, match=".".join(path[-1:])):
        validate(_bad(path, value))


@pytest.mark.parametrize("window", [(6.0, 6.0), (24.0, 6.0), (6.0, 0.0), (-1.0, 22.0),
                                    (6.0, 25.0)])
def test_billing_windows_must_be_whole_and_nonempty(window):
    from data.scenario import validate
    v = _bad(("cost", "peak_from"), window[0])
    v["cost"]["peak_to"] = window[1]
    with pytest.raises(ValueError):
        validate(v)


def test_billing_window_given_whole():
    from data.scenario import validate
    with pytest.raises(ValueError, match="together"):
        validate(_bad(("cost", "peak_from"), 6.0))


@pytest.mark.parametrize("window,inside,outside", [((6.0, 22.0), 7 * 3600, 23 * 3600),
                                                   ((22.0, 6.0), 23 * 3600, 7 * 3600),
                                                   ((0.0, 24.0), 23.9 * 3600, None)])
def test_billing_window_wraps_across_midnight(window, inside, outside):
    """22:00-06:00 holds 23:00 and 01:00 of the next day (seconds >= 86400), not 07:00."""
    from checks.schedule import billed as replayed
    from data.scenario import billed, validate
    v = _bad(("cost", "peak_from"), window[0])
    v["cost"]["peak_to"] = window[1]
    validate(v)
    w0, w1 = 3600 * window[0], 3600 * window[1]
    for f in (billed, replayed):
        assert f(inside, w0, w1) and f(inside + 86400, w0, w1)
        if outside is not None:
            assert not f(outside, w0, w1)


def test_a_stop_belongs_to_one_site():
    from data.scenario import validate
    v = _bad(("sites", "station22", "stops"), ["5989", "745"])       # 745 is Marpole's
    with pytest.raises(ValueError, match="745"):
        validate(v)


def test_every_committed_scenario_is_valid():
    from pathlib import Path
    for f in Path("data/scenarios").glob("*.toml"):
        load(f)


@pytest.mark.parametrize("sc", [[(1.0, 1.3)], [(0.25, 1.2), (0.5, 1.3), (0.25, 1.4)]])
def test_m4_weights_that_sum_to_one_pass(sc):
    from data.scenario import weights
    assert weights(sc) == sc
