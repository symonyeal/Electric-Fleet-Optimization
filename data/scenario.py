"""Declared engineering scenarios (Data §3).

A scenario is a TOML file. Every numerical entry is a table {value, unit, source}, where source is
a citation recorded in docs/SOURCES.md or the word `illustrative`; strings and lists (names, stop
ids) are structure and carry neither. load() returns the values with the tables stripped, and a
provenance map "path.to.key" -> (unit, source), after validate() has checked every domain the
models assume. A value outside its domain is refused before any row is built.
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


# (table, key): (test, the domain in words). A rule applies when its table and key are present.
POSITIVE = lambda x: x > 0
NONNEG = lambda x: x >= 0
RULES = {
    ("time", "delta"): (POSITIVE, "> 0"), ("time", "window"): (POSITIVE, "> 0"),
    ("time", "layover"): (NONNEG, ">= 0"), ("time", "speed"): (POSITIVE, "> 0"),
    ("time", "service"): (NONNEG, ">= 0"), ("time", "T"): (POSITIVE, "> 0"),
    ("time", "tau_min"): (POSITIVE, "> 0"),
    ("deadhead", "speed"): (POSITIVE, "> 0"), ("deadhead", "detour"): (POSITIVE, "> 0"),
    ("battery", "B"): (POSITIVE, "> 0"), ("battery", "kappa"): (NONNEG, ">= 0"),
    ("charger", "P"): (POSITIVE, "> 0"), ("charger", "eta"): (lambda x: 0 < x <= 1, "in (0, 1]"),
    ("charger", "alpha"): (NONNEG, ">= 0"), ("charger", "gamma"): (NONNEG, ">= 0"),
    ("cost", "rider"): (lambda x: x > -1, "> -1 (a credit below 100%)"),
    ("cost", "peak_from"): (lambda x: 0 <= x < 24, "in [0, 24)"),
    ("cost", "peak_to"): (lambda x: 0 < x <= 24, "in (0, 24]"),
}
SITE = {"nbar": (lambda x: x >= 0 and x == int(x), "a nonnegative integer"),
        "hbar": (NONNEG, ">= 0"), "G0": (NONNEG, ">= 0"), "L": (NONNEG, ">= 0")}


def validate(v):
    """Raise ValueError naming every value of scenario v outside its domain:
    every number finite; delta, window, speeds, B, P, T, tau_min > 0; 0 < eta <= 1;
    0 <= reserve <= s0 <= smax <= 1; kappa, alpha, gamma, layover, service >= 0; cost
    coefficients >= 0 except the rider (> -1); the billing window [peak_from, peak_to) given
    whole, 0 <= peak_from < 24, 0 < peak_to <= 24, peak_from != peak_to (peak_from >
    peak_to wraps across midnight; 0 and 24 is the whole day); per site,
    nbar a nonnegative integer, hbar, G0 and L finite and >= 0, and every stop owned by one
    site only."""
    err = []

    def walk(d, path):
        for k, x in d.items():
            if isinstance(x, dict):
                walk(x, f"{path}{k}.")
            elif isinstance(x, float) and not math.isfinite(x):
                err.append(f"{path}{k} = {x}: not finite")

    walk(v, "")
    for (t, k), (ok, words) in RULES.items():
        x = v.get(t, {}).get(k)
        if isinstance(x, float) and math.isfinite(x) and not ok(x):
            err.append(f"{t}.{k} = {x:g}: must be {words}")
    b = v.get("battery", {})
    if {"reserve", "s0", "smax"} <= set(b) and not 0 <= b["reserve"] <= b["s0"] <= b["smax"] <= 1:
        err.append(f"battery: needs 0 <= reserve <= s0 <= smax <= 1, got {b['reserve']:g}, "
                   f"{b['s0']:g}, {b['smax']:g}")
    for k, x in v.get("cost", {}).items():
        if k not in ("rider", "peak_from", "peak_to") and isinstance(x, float) and x < 0:
            err.append(f"cost.{k} = {x:g}: a cost coefficient must be >= 0")
    co = v.get("cost", {})
    if ("peak_from" in co) != ("peak_to" in co):
        err.append("cost: peak_from and peak_to are given together or not at all")
    elif "peak_from" in co and co["peak_from"] == co["peak_to"]:
        err.append("cost: the billing window [peak_from, peak_to) is empty")
    owner = {}
    for s, d in v.get("sites", {}).items():
        for k, (ok, words) in SITE.items():
            if k in d and math.isfinite(d[k]) and not ok(d[k]):
                err.append(f"sites.{s}.{k} = {d[k]:g}: must be {words}")
        for stop in d.get("stops", []):
            if stop in owner:
                err.append(f"stop {stop} belongs to sites {owner[stop]} and {s}")
            owner.setdefault(stop, s)
    if err:
        raise ValueError("invalid scenario: " + "; ".join(err))
    return v


def weights(scenarios):
    """M4's scenario set [(weight, kappa)]: nonempty, weights finite, >= 0 and summing to one,
    consumptions finite and >= 0 (Models §7). Returns it, or raises ValueError."""
    if not scenarios:
        raise ValueError("M4 needs at least one scenario")
    w = [p for p, _ in scenarios]
    if not all(math.isfinite(p) and p >= 0 for p in w):
        raise ValueError(f"M4 weights must be finite and >= 0, got {w}")
    if abs(math.fsum(w) - 1.0) > 1e-9:
        raise ValueError(f"M4 weights must sum to one, got {math.fsum(w)!r}")
    if not all(math.isfinite(k) and k >= 0 for _, k in scenarios):
        raise ValueError("M4 consumptions must be finite and >= 0")
    return scenarios


def load(path):
    with open(path, "rb") as f:
        prov = {}
        return validate(_walk(tomllib.load(f), "", prov)), prov


def slot(t, delta):
    """Slot index of time t (seconds after midnight of the service day, possibly >= 86400)."""
    return math.floor(t / delta)


def billed(t, w0, w1):
    """t (seconds, possibly past midnight) lies in the billing window [w0, w1) of its day;
    w0 > w1 wraps across midnight."""
    s = t % 86400
    return w0 <= s < w1 if w0 <= w1 else s >= w0 or s < w1
