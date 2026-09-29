# The EVRP reader and the pinned benchmark (Data §1).

from pathlib import Path

import numpy as np
import pytest

from data.evrp import KEYS, load, read, value

TINY = "tests/fixtures/tiny.evrp"


def test_tiny():
    p = read(TINY)
    assert p["name"] == "tiny" and p["depot"] == 0
    assert p["I"] == [1, 2, 3] and p["F"] == [4, 5]
    assert p["b"].tolist() == [0, 4, 3, 5, 0, 0]
    assert (p["C"], p["Q"], p["h"], p["K"], p["opt"]) == (10, 10, 1.0, 1, None)
    assert p["D"][0, 1] == 5.0 and p["D"][1, 2] == 5.0 and p["D"][0, 5] == pytest.approx(52**0.5)
    assert np.allclose(p["D"], p["D"].T)


def test_header_variants(tmp_path):
    """2019 files use `Name:` and EDGE_WEIGHT_FORMAT; 2022 files NAME: and EDGE_WEIGHT_TYPE."""
    s = Path(TINY).read_text()
    f = tmp_path / "old.evrp"
    f.write_text(s.replace("NAME:", "Name:").replace("EDGE_WEIGHT_TYPE", "EDGE_WEIGHT_FORMAT"))
    p, q = read(TINY), read(f)
    assert all(np.array_equal(p[k], q[k]) for k in ("X", "b", "I", "F", "D"))


@pytest.mark.parametrize("s,v", [("384.678035", 384.678035), ("0", None), ("-", None),
                                 ("857 (best known)", 857.0), ("740 (upper bound)", 740.0)])
def test_optimal_value(s, v):
    assert value(s) == v


@pytest.mark.parametrize("old,new", [("EUC_2D", "GEO"), ("DIMENSION: 6", "DIMENSION: 7"),
                                     ("STATIONS: 2", "STATIONS: 3"), ("1 0\n2 4", "2 4")])
def test_rejects(tmp_path, old, new):
    f = tmp_path / "bad.evrp"
    f.write_text(Path(TINY).read_text().replace(old, new, 1))
    with pytest.raises(ValueError):
        read(f)


def test_manifest_lists_both_sets():
    assert len(KEYS) == 41
    assert sum(k.startswith("evrp-2019/") for k in KEYS) == 17


@pytest.mark.data
def test_e_n22_k4():
    p = load("evrp-2019/E-n22-k4")
    assert len(p["I"]) == 21 and len(p["F"]) == 8 and p["b"].sum() == 22500
    assert p["X"][p["depot"]].tolist() == [145, 215]
    assert (p["C"], p["Q"], p["h"], p["K"], p["opt"]) == (6000, 94, 1.2, 4, 384.678035)


@pytest.mark.data
def test_all_files():
    """Every file verifies and parses; two 2022 files carry a NAME unlike their file name."""
    odd = {}
    for k in KEYS:
        p = load(k)
        assert len(p["I"]) + len(p["F"]) + 1 == len(p["X"])
        if k.startswith("evrp-2022/") and p["NAME"] != p["name"]:
            odd[p["name"]] = p["NAME"]
    assert odd == {"F-n140-k5-s5": "F-n140-k7-s5", "X-n221-k11-s7": "X-n221-k11-s9"}


@pytest.mark.data
def test_checksum_mismatch(tmp_path):
    f = tmp_path / "evrp-2019" / "E-n22-k4.evrp"
    f.parent.mkdir()
    f.write_bytes(Path("data/fetched/evrp-2019/E-n22-k4.evrp").read_bytes() + b"\n")
    with pytest.raises(ValueError, match="SHA-256"):
        load("evrp-2019/E-n22-k4", root=tmp_path)
