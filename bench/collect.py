"""What the report may say, read from the result bundles: every bundle is checked against its
case (bench/schema.py) before anything is taken from it, and every U is recomputed by the
independent replay of its routes or schedule. Nothing here writes a file.
"""

import json
from pathlib import Path

from bench import cases, schema
from bench.verdict import TRUSTED, evrp

REPORT = {"E-n22-k4": 384.678035, "E-n23-k3": 573.130948, "E-n30-k3": 511.253921,
          "E-n33-k4": 869.892175, "E-n51-k5": 570.170703, "E-n76-k7": 723.367517,
          "E-n101-k8": 899.885589}                  # OPTIMAL_VALUE in the files (Data §1)
EVRP_PYTHON = {"E-n22-k4": 384.67, "E-n23-k3": 571.94, "E-n30-k3": 509.47,
               "E-n33-k4": 840.14, "E-n51-k5": 529.90, "E-n76-k7": 692.64,
               "E-n101-k8": 839.29}                 # README best of VNS, SA, GSGA; unreplayed
TRANSIT = {None: "Route 100, full day", 10.0: "Route 100 to 10:00", 8.0: "Route 100 to 08:00"}
SOURCED = {"rs1640": "594 kWh pack, BC Hydro RS 1640 (Overnight Rate) at every meter",
           "rs1650": "594 kWh pack, RS 1650 (Demand Transition) on route, RS 1640 at the depot",
           "rs1640-stress": "285.8 kWh stress pack (derived, not the installed pack), RS 1640 "
                            "at every meter",
           "rs1650-stress": "285.8 kWh stress pack (derived, not the installed pack), RS 1650 "
                            "on route, RS 1640 at the depot"}


def case(track, instance, model, until=None, scenario=None):
    """The matrix case with these coordinates."""
    return next(k for k in cases.CASES if (k.track, k.instance, k.model, k.until, k.scenario)
                == (track, instance, model, until, scenario))


def rel(path, out):
    return Path(path).relative_to(out).as_posix()


def load(k, out, man, excluded):
    """The record of case k if it is admitted, else None; a bundle on disk that is not admitted
    is listed in excluded with its reasons."""
    f = cases.path(k, out)
    b = schema.read(f)
    if b is None:
        if f.exists():
            excluded.append(dict(file=rel(f, out), reasons=["unreadable"], decision=None))
        return None
    if "bundle" in b:
        bad = schema.check(b, k, out)
        if not bad:
            return b
        excluded.append(dict(file=rel(f, out), reasons=bad, decision=None,
                             revision=b["bundle"]["code"].get("commit", "")[:7]))
        return None
    e = man.get(rel(f, out))
    bad = schema.legacy(b, e, k)
    if not bad:
        return dict(b, bound_source=e["bound_source"], legacy=True)
    excluded.append(dict(file=rel(f, out), reasons=bad, decision=(e or {}).get("decision"),
                         revision=(b.get("provenance") or {}).get("revision")))
    return None


def replayed_routes(p, out, n):
    """[(length, routes, file)] of every route file of instance n that the replay accepts."""
    from checks.route import read_routes, replay
    got = []
    for f in sorted([*(Path(out) / "evrp").glob(f"{n}-*.routes"),
                     *(Path(out) / "baseline").glob(f"{n}-*.routes")]):
        R = read_routes(f)
        rp = replay(p, R)
        if rp["ok"]:
            got.append((rp["length"], R, f.name))
    return got


def segments(p, R):
    """Segments (between customers or the depot) that visit two or more stations in a row
    (Phase 9, criterion 4; Routing §4: R1 allows them through station paths)."""
    F = set(p["F"]) - {p["depot"]}
    k = 0
    for r in R:
        run = 0
        for z in r:
            run = run + 1 if z - 1 in F else 0
            k += run == 2
    return k


def routing(out, man, excluded):
    """One row per 2019 E instance, and the R2 dual comparison of the admitted pairs."""
    from data.evrp import load as load_evrp
    rows, duals = [], []
    for n in cases.E:
        recs = {m: load(case("evrp", n, m), out, man, excluded)
                for m in ("R0", "R1", "R2-ipm", "R2-simplex")}
        p = load_evrp(f"evrp-2019/{n}")
        got = replayed_routes(p, out, n)
        lower = [r["L"] for r in recs.values() if r and r.get("L") is not None
                 and r.get("bound_source") in TRUSTED]
        v = evrp(REPORT[n], lower, [g[0] for g in got])
        gsga = [g[0] for g in got if "-GSGA-" in g[2]]
        best = min(got, key=lambda g: g[0]) if got else None
        r0 = recs["R0"]
        rows.append(dict(instance=n, report=REPORT[n], evrp_python=EVRP_PYTHON[n],
                         gsga=min(gsga) if gsga else None,
                         r0=r0["U"] if r0 and r0.get("certified") else None,
                         segments=None if best is None else segments(p, best[1]),
                         best=best, p=p,
                         sources=sorted({_rev(r) for r in recs.values() if r}), **v))
        a, b = recs["R2-ipm"], recs["R2-simplex"]
        if a and b:
            duals.append(dict(instance=n, ipm=a, simplex=b))
    return rows, duals


def _rev(r):
    if "bundle" in r:
        return r["bundle"]["code"]["commit"][:7]
    return (r.get("provenance") or {}).get("revision") or "unrecorded"


def transit(out, man, excluded):
    """Route 100 rows: the illustrative windows (M0 and M1) and the sourced scenarios (M1), each
    M1 cost recomputed by the replay from the bundle's schedule under the current scenario."""
    from checks.certificate import tol
    from checks.schedule import replay_energy
    rows, sourced = [], []

    def m1(k):
        b = load(k, out, man, excluded)
        if b is None:
            return None, None, None
        c, v, _ = schema.inputs(k)
        plan = {t: {int(s): kw for s, kw in d.items()} for t, d in (b["plan"] or {}).items()}
        rp = replay_energy(c, v, b["duties"], plan, b["infra"])
        if not rp["ok"] or b["U"] is None or abs(rp["cost"] - b["U"]) > tol(b["U"]):
            excluded.append(dict(file=rel(cases.path(k, out), out), reasons=["replay"],
                                 decision=None, revision=_rev(b)))
            return None, None, None
        return dict(b, U=rp["cost"], replayed=rp), c, v

    for until, label in TRANSIT.items():
        k0 = case("transit", "route100", "M0", until)
        a = load(k0, out, man, excluded)
        if a is None:
            continue
        c, v, _ = schema.inputs(k0)
        r0 = replay_energy(c, v, a["duties"], {}, {})
        rB = v["battery"]["reserve"] * v["battery"]["B"]
        below = sum(min(e for _, e in tr) < rB - 1e-6 for tr in r0["trace"])
        b, _, _ = m1(case("transit", "route100", "M1", until))
        rows.append(dict(label=label, until=until, m0=a, trips=a["trips"],
                         deadhead=r0["parts"]["deadhead"] / v["cost"]["deadhead"], below=below,
                         m0_cost=None if below else r0["cost"], m1=b, v=v, c=c,
                         tag=schema.name(case("transit", "route100", "M1", until))))
    full = load(case("transit", "route100", "M0"), out, man, [])
    for sc, what in SOURCED.items():
        b, c, v = m1(case("transit", "route100", "M1", scenario=sc))
        if b is None:
            continue
        below = None
        if full:
            r0 = replay_energy(c, v, full["duties"], {}, {})
            rB = v["battery"]["reserve"] * v["battery"]["B"]
            below = sum(min(e for _, e in tr) < rB - 1e-6 for tr in r0["trace"])
        sourced.append(dict(scenario=sc, what=what, m1=b, c=c, v=v, below=below,
                            m0_fleet=full["fleet"] if full else None,
                            tag=schema.name(case("transit", "route100", "M1", scenario=sc))))
    return rows, sourced


def grid(out, man, excluded):
    """The charging-physics grid rows that may be shown: rows written under the current
    formulation from a clean tree, or legacy rows the migration manifest retains."""
    f = Path(out) / "grid" / "grid.json"
    if not f.exists():
        return []
    G = json.loads(f.read_text(encoding="utf-8"))
    fm = schema.formulations()
    keep = []
    for g in G:
        model = g["pair"].split(" / ")[0]
        k = f"grid/grid.json#{g['pair']}|{g['instance']}|{g['alpha']:g}"
        if "formulation" in g:
            bad = [r for r, ok in (("formulation", g["formulation"] == fm[model]),
                                   ("dirty", not g.get("dirty", True))) if not ok]
        else:
            e = man.get(k) or {}
            bad = [] if (e.get("decision") == "retained" and e.get("formulation") == fm[model]
                         and "+dirty" not in g.get("revision", "+dirty")) else \
                [e.get("decision") or "no migration entry"]
        if bad:
            excluded.append(dict(file=k, reasons=bad, decision=(man.get(k) or {}).get(
                "decision"), revision=g.get("revision")))
        else:
            keep.append(g)
    return keep


def collect(out=cases.OUT):
    """Everything the report and figures read, and the list of bundles not admitted."""
    out = Path(out)
    man, excluded = schema.manifest(out), []
    rows, duals = routing(out, man, excluded)
    tr, sourced = transit(out, man, excluded)
    return dict(routing=rows, duals=duals, transit=tr, sourced=sourced,
                grid=grid(out, man, excluded), excluded=excluded, manifest=man)
