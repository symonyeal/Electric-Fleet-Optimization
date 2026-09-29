"""Declared engineering scenarios (Data §3).

A scenario is a TOML file. Every numerical entry is a table {value, unit, source}, where source is
a citation recorded in docs/SOURCES.md or the word `illustrative`; strings and lists (names, stop
ids) are structure and carry neither. load() returns the values with the tables stripped, and a
provenance map "path.to.key" -> (unit, source).
"""

import math
import tomllib


def _walk(d, path, prov):
    out = {}
    for k, v in d.items():
        p = f"{path}.{k}" if path else k
        if isinstance(v, dict) and "value" in v:
            if not v.get("unit") or not v.get("source"):
                raise ValueError(f"{p}: a value needs a unit and a source")
            out[k], prov[p] = float(v["value"]), (v["unit"], v["source"])
        elif isinstance(v, dict):
            out[k] = _walk(v, p, prov)
        elif isinstance(v, (str, list)):
            out[k] = v
        else:
            raise ValueError(f"{p}: bare number; write {{value, unit, source}}")
    return out


def load(path):
    with open(path, "rb") as f:
        prov = {}
        return _walk(tomllib.load(f), "", prov), prov


def slot(t, delta):
    """Slot index of time t (seconds after midnight of the service day, possibly >= 86400)."""
    return math.floor(t / delta)
