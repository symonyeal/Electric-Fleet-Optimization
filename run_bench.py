"""The experiment matrix of Validation §3: tables and figures from the committed result bundles.

    python run_bench.py            tables (docs/results/README.md) and figures (docs/results/fig)
    python run_bench.py --run      first recompute every benchmark and transit case
    python run_bench.py --grid     first recompute the charging-physics grid (M2/M1, R3/R1)

Every number in the tables is read from a bundle that names the revision that produced it.
"""

import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

OUT = Path("docs/results")
E = ["E-n22-k4", "E-n23-k3", "E-n30-k3", "E-n33-k4", "E-n51-k5", "E-n76-k7", "E-n101-k8"]
REPORT = {"E-n22-k4": 384.678035, "E-n23-k3": 573.130948, "E-n30-k3": 511.253921,
          "E-n33-k4": 869.892175, "E-n51-k5": 570.170703, "E-n76-k7": 723.367517,
          "E-n101-k8": 899.885589}                  # OPTIMAL_VALUE in the files (Data §1)
EVRP_PYTHON = {"E-n22-k4": 384.67, "E-n23-k3": 571.94, "E-n30-k3": 509.47,
               "E-n33-k4": 840.14, "E-n51-k5": 529.90, "E-n76-k7": 692.64,
               "E-n101-k8": 839.29}                 # README best of VNS, SA, GSGA; unreplayed
CASES = [*[("evrp", n, m, t, ()) for n in E for m, t in (("R0", 600), ("R1", 600),
                                                         ("R2-ipm", 1800), ("R2-simplex", 1800))],
         *[("transit", "route100", m, t, u) for u, t in ((("--until", "8"), 600),
                                                         (("--until", "10"), 900), ((), 1800))
           for m in ("M0", "M1")]]
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"   # validated, dataviz
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


TRANSIT = {"route100": "Route 100, full day", "route100-until10h": "Route 100 to 10:00",
           "route100-until8h": "Route 100 to 08:00"}


def transit(tag):
    """The M1 bundle of a Route 100 window, its corridor and its scenario."""
    from data.scenario import load
    with open("tests/fixtures/route100.json", encoding="utf-8") as f:
        c = json.load(f)
    if tag != "route100":
        h = int(tag.removeprefix("route100-until").removesuffix("h"))
        c = dict(c, trips=[t for t in c["trips"] if t["dep"] < h * 3600])
    return bundle(OUT / "transit" / f"{tag}-M1.json"), c, load("data/scenarios/route100.toml")[0]


def bundle(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def fmt(x, d=2):
    return "-" if x is None else f"{x:,.{d}f}"


def best(n):
    """The shortest replayed routes of instance n among all bundles: (length, routes, file)."""
    from checks.route import read_routes, replay
    from data.evrp import load
    p, b = load(f"evrp-2019/{n}"), None
    for f in sorted([*(OUT / "evrp").glob(f"{n}-*.routes"),
                     *(OUT / "baseline").glob(f"{n}-*.routes")]):
        R = read_routes(f)
        rp = replay(p, R)
        if rp["ok"] and (b is None or rp["length"] < b[0] - 1e-9):
            b = (rp["length"], R, f.name)
    return p, b


def runs(p, R):
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


def verdicts():
    rows, tol = [], 1e-6
    for n in E:
        r = {m: bundle(OUT / "evrp" / f"{n}-{m}.json") for m in ("R0", "R1", "R2-ipm",
                                                                 "R2-simplex")}
        gsga = [b for f in sorted((OUT / "baseline").glob(f"{n}-GSGA-*.json"))
                if (b := bundle(f)) and b.get("U") is not None]
        Ls = [b["L"] for m, b in r.items() if b and b.get("L") is not None and m != "R0"]
        if r["R0"] and r["R0"].get("certified"):
            Ls.append(r["R0"]["U"])                 # z(R0) <= z(R1) (Routing §3)
        Us = [b["U"] for m, b in r.items() if b and m != "R0" and b.get("U") is not None]
        Us += [b["U"] for b in gsga]
        L, U = (max(Ls) if Ls else None), (min(Us) if Us else None)
        V = REPORT[n]
        if U is not None and L is not None and U - L <= tol * (1 + abs(U)):
            v = "certified optimal"
        else:
            v = "bracketed" if U is not None and L is not None else "open"
        if U is not None and V > U + tol * (1 + V):
            v += "; report value not optimal"
        elif L is not None and V < L - tol * (1 + V):
            v += "; report value below a valid bound"
        rows.append((n, V, EVRP_PYTHON[n], min((b["U"] for b in gsga), default=None),
                     r["R0"]["U"] if r["R0"] and r["R0"].get("certified") else None,
                     L, U, None if L is None or U is None else (U - L) / max(1, abs(U)), v))
    return rows


def duals():
    rows = []
    for n in E:
        a, b = (bundle(OUT / "evrp" / f"{n}-R2-{d}.json") for d in ("ipm", "simplex"))
        if a and b:
            rows.append((n, *[(x["iterations"], x["pricing"], x["elapsed"], x["L"],
                               x["converged"]) for x in (a, b)]))
    return rows


def write_readme():
    from checks.schedule import replay_energy
    V = verdicts()
    lines = ["# Results", "",
             ("Regenerated by `python run_bench.py` from the bundles in this directory; each "
             "bundle records the revision, parameters and data checksums that produced it. "
             "Bundles written before 6b290be record the revision at completion rather than at "
             "start, and mark '+dirty' when any file differed, untracked bundles included."), "",
             "## 2019 E instances (Validation §3, EVRP-06)", "",
             ("L is the best valid lower bound (R1 and R2 dual bounds, and the certified R0 "
             "value, since z(R0) <= z(R1)); U the shortest replayed solution (R1, R2's "
             "restricted master, GSGA). evrp-python's README values are not replayed. The "
             "last column counts segments of U's routes that pass two or more stations in a "
             "row (Routing §4)."), "",
             ("| Instance | Report value | evrp-python (README) | GSGA replayed | R0 | L | U | "
             "Gap | Verdict | Multi-station segments |"),
             "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|"]
    for n, Vr, ep, g, r0, L, U, gap, v in V:
        p, B = best(n)
        lines.append(f"| {n} | {Vr:.6f} | {ep:.2f} | {fmt(g, 6)} | {fmt(r0, 6)} | "
                     f"{fmt(L, 6)} | {fmt(U, 6)} | "
                     f"{'-' if gap is None else f'{100 * gap:.3f}%'} | {v} | "
                     f"{'-' if B is None else runs(p, B[1])} |")
    D = duals()
    lines += ["", "## Interior versus simplex duals in R2 (CG-04)", "",
              ("| Instance | Iterations (IPM / simplex) | Pricing calls | Seconds | Bound "
              "(IPM / simplex) | Converged |"), "|---|---:|---:|---:|---:|---|"]
    for n, a, b in D:
        lines.append(f"| {n} | {a[0]} / {b[0]} | {a[1]} / {b[1]} | {a[2]:.1f} / {b[2]:.1f} | "
                     f"{fmt(a[3], 4)} / {fmt(b[3], 4)} | {a[4]} / {b[4]} |")
    lines += ["", "## Route 100 (Validation §3, TRN-09)", "",
              ("Illustrative battery, charger and cost parameters (data/scenarios/route100.toml);"
              " costs in illustrative CAD for the modeled window. M0 minimizes the fleet "
              "without batteries; its duties are replayed with the battery and no charging, "
              "which gives their deadhead, their cost where feasible, and the number of "
              "buses that fall below the reserve. M1 values are replayed schedules."), "",
              ("| Window | Trips | M0 fleet | M0 deadhead km | M0 buses below reserve | M0 cost | "
              "M1 fleet | M1 deadhead km | M1 cost U | M1 L | Gap | M1 status |"),
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for tag in reversed(TRANSIT):
        if not (a := bundle(OUT / "transit" / f"{tag}-M0.json")):
            continue
        b, c, v = transit(tag)
        r0 = replay_energy(c, v, a["duties"], {}, {})
        rB = v["battery"]["reserve"] * v["battery"]["B"]
        E = sum(min(e for _, e in tr) < rB - 1e-6 for tr in r0["trace"])
        dh = r0["parts"]["deadhead"] / v["cost"]["deadhead"]
        row = (f"| {TRANSIT[tag]} | {a['trips']} | {a['fleet']} | {dh:.1f} | {E} | "
               f"{fmt(r0['cost']) if not E else '-'} |")
        if b:
            dh1 = b["replay"]["parts"]["deadhead"] / v["cost"]["deadhead"]
            gap = "-" if b["gap_rel"] is None else f"{100 * b['gap_rel']:.3f}%"
            row += (f" {b['fleet']} | {dh1:.1f} | {fmt(b['U'])} | {fmt(b['L'])} | {gap} | "
                    f"{b['status']} |")
        else:
            row += " - | - | - | - | - | - |"
        lines.append(row)
    G = bundle(OUT / "grid" / "grid.json")
    if G:
        lines += ["", "## Charging physics (OA-04)", "",
                  ("Each row fixes the loss coefficient alpha (illustrative). M2 and R3 are "
                  "solved by outer approximation, M1 and R1 by HiGHS, on the same instance. "
                  "M2 against M1 compares cost; R3 against R1 compares the replayed route "
                  "length, since R3 also prices energy and dwell time."), "",
                  ("| Model pair | Instance | Measure | alpha | Without | With | Increase | "
                   "Status |"),
                  "|---|---|---|---:|---:|---:|---:|---|"]
        for g in G:
            inc = None if g["base"] is None or g["loss"] is None else g["loss"] - g["base"]
            lines.append(f"| {g['pair']} | {g['instance']} | {g['measure']} | {g['alpha']:g} | "
                         f"{fmt(g['base'], 3)} | {fmt(g['loss'], 3)} | {fmt(inc, 3)} | "
                         f"{g['status']} |")
    lines += ["", "## Figures", "", "![E-n22-k4](fig/routes-E-n22-k4.png)", "",
              "![R2 duals](fig/r2-duals-E-n22-k4.png)", ""]
    tag = next((t for t in TRANSIT if bundle(OUT / "transit" / f"{t}-M1.json")), None)
    if tag:
        lines += [f"![{TRANSIT[tag]} timeline](fig/timeline-{tag}.png)", "",
                  f"![{TRANSIT[tag]} energy](fig/energy-{tag}.png)", ""]
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


def summary():
    """The results block of the top-level README, between its markers."""
    from checks.schedule import replay_energy
    revs = sorted({(bundle(f).get("provenance") or {}).get("revision") or "unrecorded"
                   for f in OUT.glob("*/*.json") if f.parent.name != "grid"})
    L = [("Regenerated by `python run_bench.py` from the bundles in "
          "[docs/results](docs/results/README.md), which name the code revision of each run "
          f"({', '.join(revs)})."), "",
         "| Instance | Report value | U (replayed) | L | Gap | Verdict |",
         "|---|---:|---:|---:|---:|---|"]
    for n, Vr, _, _, _, lo, up, gap, v in verdicts():
        L.append(f"| {n} | {Vr:.6f} | {fmt(up, 6)} | {fmt(lo, 6)} | "
                 f"{'-' if gap is None else f'{100 * gap:.3f}%'} | {v} |")
    D = {n: (a, b) for n, a, b in duals()}
    if "E-n22-k4" in D:
        a, b = D["E-n22-k4"]
        L += ["", (f"Column generation on E-n22-k4 reached the bound {a[3]:.4f} with interior "
                   f"duals in {a[2]:.1f} s and {b[3]:.4f} with simplex duals in {b[2]:.1f} s.")]
    a = bundle(OUT / "transit" / "route100-M0.json")
    if a:
        _, c, v = transit("route100")
        r0 = replay_energy(c, v, a["duties"], {}, {})
        rB = v["battery"]["reserve"] * v["battery"]["B"]
        E = sum(min(e for _, e in tr) < rB - 1e-6 for tr in r0["trace"])
        L += ["", (f"Route 100 on {c.get('date', 'the service day')}: {a['trips']} trips need "
                   f"{a['fleet']} buses without batteries (M0). With the illustrative "
                   f"{v['battery']['B']:g} kWh battery and no charging, {E} of those "
                   f"{a['fleet']} duties fall below the reserve.")]
        b = bundle(OUT / "transit" / "route100-M1.json")
        if b:
            gap = "-" if b["gap_rel"] is None else f"{100 * b['gap_rel']:.2f}%"
            L[-1] += (f" M1 schedules the day with {b['fleet']} buses and "
                      f"{sum(i['n'] for i in b['infra'].values())} plugs at "
                      f"{len(b['infra'])} sites, cost {fmt(b['U'])} against the bound "
                      f"{fmt(b['L'])} (gap {gap}, {b['status']}).")
    return L


def write_summary():
    f = Path("README.md")
    s = f.read_text(encoding="utf-8")
    i, j = s.index("<!-- results:begin -->"), s.index("<!-- results:end -->")
    f.write_text(s[:i] + "<!-- results:begin -->\n" + "\n".join(summary()) + "\n" + s[j:],
                 encoding="utf-8")


def figures():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from checks.schedule import replay_energy
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True,
                         "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.facecolor": "#fcfcfb",
                         "axes.facecolor": "#fcfcfb"})
    (OUT / "fig").mkdir(parents=True, exist_ok=True)
    p, B = best("E-n22-k4")
    if B:
        fig, ax = plt.subplots(figsize=(6, 5.2))
        X = p["X"]
        ax.scatter(*X[p["I"]].T, s=18, color=INK2, zorder=3, label="customer")
        ax.scatter(*X[p["F"]].T, s=40, marker="^", color=INK, zorder=3, label="station")
        ax.scatter(*X[[p["depot"]]].T, s=60, marker="s", color=INK, zorder=4, label="depot")
        for k, r in enumerate(B[1]):
            v = np.array([X[z - 1] for z in r])
            col = [BLUE, ORANGE, AQUA, YELLOW][k % 4]
            ax.plot(*v.T, color=col, lw=2, zorder=2)
            far = v[np.argmax(((v - X[p["depot"]]) ** 2).sum(1))]
            ax.annotate(f"route {k + 1}", far, xytext=(4, 4), textcoords="offset points",
                        color=INK, fontsize=8)
        ax.set_title(f"E-n22-k4: shortest replayed solution, length {B[0]:.6f}",
                     color=INK, loc="left")
        ax.set_aspect("equal")
        ax.legend(frameon=False, loc="lower left", fontsize=8)
        fig.tight_layout()
        fig.savefig(OUT / "fig" / "routes-E-n22-k4.png", dpi=150)
        plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, d in zip(axes, ("ipm", "simplex"), strict=True):
        b = bundle(OUT / "evrp" / f"E-n22-k4-R2-{d}.json")
        if not b:
            continue
        T = b["trajectory"]
        t = [x["t"] for x in T]
        ax.plot(t, [x["f"] for x in T], color=BLUE, lw=2, label="master value")
        ax.plot([x["t"] for x in T if x["L"] is not None], [x["L"] for x in T
                if x["L"] is not None], color=ORANGE, lw=2, marker="o", ms=4,
                label="bound (R2.2)")
        ax.set_title(("interior" if d == "ipm" else "simplex") + " duals", color=INK, loc="left")
        ax.set_xlabel("seconds")
    axes[0].set_ylabel("length")
    axes[0].legend(frameon=False, fontsize=8)
    lo = [bundle(OUT / "evrp" / f"E-n22-k4-R2-{d}.json") for d in ("ipm", "simplex")]
    if all(lo):
        axes[0].set_ylim(min(b["L"] for b in lo) - 10, min(b["L"] for b in lo) + 60)
    fig.suptitle("E-n22-k4, R2: master value and bound", color=INK, x=0.02, ha="left")
    fig.tight_layout()
    fig.savefig(OUT / "fig" / "r2-duals-E-n22-k4.png", dpi=150)
    plt.close(fig)
    tag = next((t for t in TRANSIT if bundle(OUT / "transit" / f"{t}-M1.json")), None)
    if tag is None:
        return
    b, c, v = transit(tag)
    T = {t["id"]: t for t in c["trips"]}
    dl, n = v["time"]["delta"], len(b["duties"])
    fig, ax = plt.subplots(figsize=(9, 1.4 + 0.2 * n))
    for k, d in enumerate(b["duties"]):
        for tid in d:
            t = T[tid]
            ax.barh(k, (t["arr"] - t["dep"]) / 3600, left=t["dep"] / 3600, height=0.6,
                    color=BLUE, edgecolor="#fcfcfb", linewidth=1)
            for s_ in b["plan"].get(tid, {}):
                ax.barh(k, dl / 3600, left=int(s_) * dl / 3600, height=0.6, color=ORANGE,
                        edgecolor="#fcfcfb", linewidth=1)
    ax.set_yticks(range(n), [f"bus {k + 1}" for k in range(n)], fontsize=7)
    ax.margins(x=0.01)
    ax.invert_yaxis()
    ax.set_xlabel("hour of the service day")
    ax.legend([Patch(color=BLUE), Patch(color=ORANGE)], ["trip", "charging slot"], ncol=2,
              frameon=False, fontsize=8, loc="lower right", bbox_to_anchor=(1, 1))
    ax.set_title(f"{TRANSIT[tag]}, M1: buses, trips and charging (illustrative scenario)",
                 color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "fig" / f"timeline-{tag}.png", dpi=150)
    plt.close(fig)
    rp = replay_energy(c, v, b["duties"], {k: {int(s_): kw for s_, kw in d.items()}
                                           for k, d in b["plan"].items()}, b["infra"])
    B = v["battery"]["B"]
    if rp["load"]:
        fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 5.6), sharex=True,
                                     gridspec_kw=dict(height_ratios=(3, 2)))
    else:
        fig, a1 = plt.subplots(figsize=(9, 3.6))
    kwh = [sum(sum(b["plan"].get(t, {}).values()) for t in d) for d in b["duties"]]
    top = max(range(n), key=lambda k: kwh[k])
    for k, tr in enumerate(rp["trace"]):
        a1.plot([t / 3600 for t, _ in tr], [e for _, e in tr], color=BLUE if k == top else
                "#b7b5ae", lw=2 if k == top else 1, zorder=3 if k == top else 2)
    a1.axhline(v["battery"]["reserve"] * B, color=INK2, lw=1, ls="--")
    a1.text(a1.get_xlim()[0], v["battery"]["reserve"] * B, " reserve", va="bottom", color=INK2,
            fontsize=8)
    a1.set_ylabel("battery energy, kWh")
    who = f"bus {top + 1}, which charges most, in blue" if kwh[top] else "gray"
    a1.set_title(f"{TRANSIT[tag]}, M1 replayed: energy per bus ({who})"
                 + ("" if rp["load"] else "; no bus charges in this window"),
                 color=INK, loc="left")
    if not rp["load"]:
        a1.set_xlabel("hour of the service day")
    else:
        lo, hi = min(k[1] for k in rp["load"]), max(k[1] for k in rp["load"])
        Z = [s for s in v["sites"] if any(k[0] == s for k in rp["load"])]
        for s in Z:
            col = (ORANGE, AQUA)[list(v["sites"]).index(s)]
            y = [rp["load"].get((s, s_), (0, 0.0))[1] for s_ in range(lo, hi + 1)]
            a2.step([s_ * dl / 3600 for s_ in range(lo, hi + 2)], [*y, y[-1]], where="post",
                    color=col, lw=1.5, label=s)
        a2.set_ylabel("grid power, kW")
        a2.set_xlabel("hour of the service day")
        if len(Z) > 1:
            a2.legend(frameon=False, fontsize=8)
        else:
            a2.set_title(f"charging power drawn at {Z[0]}", color=INK2, loc="left", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "fig" / f"energy-{tag}.png", dpi=150)
    plt.close(fig)


def run():
    for track, n, m, t, u in CASES:
        subprocess.run([sys.executable, "run_case.py", track, n, m, "--time", str(t), *u],
                       check=False)


def grid():
    """OA-04: M2 against M1 on Route 100 before 06:30, R3 against R1 on an E-n22-k4
    sub-instance, over a declared grid of loss coefficients (illustrative)."""
    from checks.route import replay_charge
    from data.evrp import load, sub
    from data.scenario import load as scenario
    from models.charge import m2
    from models.fleet import m1
    from models.recharge import r3
    from models.route import r1
    out = []
    with open("tests/fixtures/route100.json", encoding="utf-8") as f:
        c = json.load(f)
    c = dict(c, trips=[t for t in c["trips"] if t["dep"] < 6.5 * 3600])
    v, _ = scenario("data/scenarios/route100.toml")
    v0 = copy.deepcopy(v)
    v0["charger"]["gamma"] = 0.0
    base = m1(c, v0, name="route100-until6.5h", time_limit=600)["U"]
    for a in (3.3e-5, 6.7e-5, 1.3e-4):
        w = copy.deepcopy(v0)
        w["charger"]["alpha"] = a
        r = m2(c, w, name="route100-until6.5h", max_iter=40, time_limit=1800)
        out.append(dict(pair="M2 / M1", instance="route100 before 06:30", measure="cost",
                        alpha=a, base=base, loss=r["U"] if r["status"] == "optimal" else None,
                        status=r["status"]))
    p = load("evrp-2019/E-n22-k4")
    q = sub(p, sorted(p["I"], key=lambda i: -p["D"][p["depot"], i])[:8], p["F"])
    sc, _ = scenario("data/scenarios/r3.toml")
    zr1 = r1(q)["U"]
    for a in (0.0, 2.5e-4, 5e-4, 1e-3):
        s = copy.deepcopy(sc)
        s["charger"]["alpha"] = a
        r = r3(q, s, max_iter=60, time_limit=1800)
        z = None
        if r["status"] == "optimal":
            z = replay_charge(q, s, r["routes"], {tuple(map(int, k.split(":"))): qt
                                                  for k, qt in r["charges"].items()})["length"]
        out.append(dict(pair="R3 / R1", instance=q["name"], measure="route length", alpha=a,
                        base=zr1, loss=z, cost=r["U"], status=r["status"]))
    (OUT / "grid").mkdir(parents=True, exist_ok=True)
    (OUT / "grid" / "grid.json").write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("--run", action="store_true")
    a.add_argument("--grid", action="store_true")
    x = a.parse_args()
    if x.run:
        run()
    if x.grid:
        grid()
    figures()
    write_readme()
    write_summary()
    print((OUT / "README.md").read_text(encoding="utf-8"))
