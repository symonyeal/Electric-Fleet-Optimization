"""Figures from collected results (bench/collect.py): the shortest replayed E-n22-k4 routes, the
R2 bound trajectories, and for each drawn Route 100 run its timeline and replayed energy."""

from pathlib import Path

import numpy as np

from bench.report import drawn

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"   # validated, dataviz
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def figures(D, out):
    """Write every figure the results page links, into out/fig. OUTPUT the files written."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK2,
                         "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True,
                         "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.facecolor": "#fcfcfb",
                         "axes.facecolor": "#fcfcfb"})
    fig_dir = Path(out) / "fig"
    fig_dir.mkdir(parents=True, exist_ok=True)
    made = []
    r = next((r for r in D["routing"] if r["instance"] == "E-n22-k4" and r["best"]), None)
    if r:
        p, (length, R, _) = r["p"], r["best"]
        fig, ax = plt.subplots(figsize=(6, 5.2))
        X = p["X"]
        ax.scatter(*X[p["I"]].T, s=18, color=INK2, zorder=3, label="customer")
        ax.scatter(*X[p["F"]].T, s=40, marker="^", color=INK, zorder=3, label="station")
        ax.scatter(*X[[p["depot"]]].T, s=60, marker="s", color=INK, zorder=4, label="depot")
        for k, rt in enumerate(R):
            v = np.array([X[z - 1] for z in rt])
            ax.plot(*v.T, color=[BLUE, ORANGE, AQUA, YELLOW][k % 4], lw=2, zorder=2)
            far = v[np.argmax(((v - X[p["depot"]]) ** 2).sum(1))]
            ax.annotate(f"route {k + 1}", far, xytext=(4, 4), textcoords="offset points",
                        color=INK, fontsize=8)
        ax.set_title(f"E-n22-k4: shortest replayed solution, length {length:.6f}",
                     color=INK, loc="left")
        ax.set_aspect("equal")
        ax.legend(frameon=False, loc="lower left", fontsize=8)
        fig.tight_layout()
        made.append(_save(fig, fig_dir / "routes-E-n22-k4.png", plt))
    d = next((d for d in D["duals"] if d["instance"] == "E-n22-k4"), None)
    if d:
        fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
        for ax, k in zip(axes, ("ipm", "simplex"), strict=True):
            T = d[k]["trajectory"]
            ax.plot([x["t"] for x in T], [x["f"] for x in T], color=BLUE, lw=2,
                    label="master value")
            ax.plot([x["t"] for x in T if x["L"] is not None],
                    [x["L"] for x in T if x["L"] is not None], color=ORANGE, lw=2, marker="o",
                    ms=4, label="bound (R2.2)")
            ax.set_title(("interior" if k == "ipm" else "simplex") + " duals", color=INK,
                         loc="left")
            ax.set_xlabel("seconds")
        axes[0].set_ylabel("length")
        axes[0].legend(frameon=False, fontsize=8)
        lo = min(d[k]["L"] for k in ("ipm", "simplex"))
        axes[0].set_ylim(lo - 10, lo + 60)
        fig.suptitle("E-n22-k4, R2: master value and bound", color=INK, x=0.02, ha="left")
        fig.tight_layout()
        made.append(_save(fig, fig_dir / "r2-duals-E-n22-k4.png", plt))
    runs = {r["tag"]: r for r in D["transit"] if r["m1"]} | {r["tag"]: r for r in D["sourced"]}
    for tag, label in drawn(D):
        made += draw(runs[tag], tag, label, fig_dir, plt, Patch)
    return made


def _save(fig, f, plt):
    fig.savefig(f, dpi=150)
    plt.close(fig)
    return f


def draw(r, tag, label, fig_dir, plt, Patch):
    """Timeline, and replayed energy with site power, of one admitted Route 100 M1 run."""
    b, c, v, rp = r["m1"], r["c"], r["v"], r["m1"]["replayed"]
    T = {t["id"]: t for t in c["trips"]}
    dl, n = v["time"]["delta"], len(b["duties"])
    sourced = "scenario" in r
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
    ax.set_title(f"{label}, M1: buses, trips and charging ("
                 + ("sourced parameters)" if sourced else "illustrative scenario)"),
                 color=INK, loc="left")
    fig.tight_layout()
    made = [_save(fig, fig_dir / f"timeline-{tag}.png", plt)]
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
    a1.set_title(f"{label}, M1 replayed: energy per bus ({who})"
                 + ("" if rp["load"] else "; no bus charges in this window"),
                 color=INK, loc="left")
    if not rp["load"]:
        a1.set_xlabel("hour of the service day")
    else:
        lo, hi = min(k[1] for k in rp["load"]), max(k[1] for k in rp["load"])
        Z = [s for s in v["sites"] if any(k[0] == s for k in rp["load"])]
        for s in Z:
            col = (ORANGE, AQUA)[list(v["sites"]).index(s) % 2]
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
    made.append(_save(fig, fig_dir / f"energy-{tag}.png", plt))
    return made
