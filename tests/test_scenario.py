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
