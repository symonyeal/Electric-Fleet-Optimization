"""CEC-2020 EVRP benchmark files (Data §1), pinned to evrp-python commit 16d3499.

An instance is a dict. Node k is file identifier k+1; the depot is the DEPOT_SECTION node.
    X ..... N x 2 coordinates          D ..... N x N unrounded Euclidean distances
    I, F .. customer and station indices   b ..... demand per node (0 off customers)
    C, Q, h  load capacity, battery capacity, consumption per unit distance
    K ..... VEHICLES, the report's minimum number of routes
    opt ... OPTIMAL_VALUE as a number, None when 0, '-' or absent
"""

import hashlib
import re
import urllib.request
from pathlib import Path

import numpy as np

COMMIT = "16d3499799ab7aa7bc3f11a5eaf8604947389462"
URL = f"https://raw.githubusercontent.com/NeiH4207/evrp-python/{COMMIT}/benchmarks/"
HERE = Path(__file__).parent
FETCHED = HERE / "fetched"
SHA = dict(reversed(l.split()) for l in (HERE / "evrp.sha256").read_text().splitlines())
KEYS = sorted(k.removesuffix(".evrp") for k in SHA)
SECTIONS = ("NODE_COORD_SECTION", "DEMAND_SECTION", "STATIONS_COORD_SECTION", "DEPOT_SECTION")


def value(s):
    """OPTIMAL_VALUE: leading number; 0 and '-' mean unknown."""
    m = re.match(r"\s*([0-9.]+)", s)
    v = float(m.group(1)) if m else 0.0
    return v or None


def dist(X):
    return np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(-1))


def read(path):
    path = Path(path)
    head, sec, cur = {}, {s: [] for s in SECTIONS}, None
    for line in path.read_text().splitlines():
        t = line.split()
        if not t or t[0] == "EOF":
            continue
        if t[0] in sec:
            cur = t[0]
        elif cur is None:
            k, _, v = line.partition(":")
            head[k.strip().upper()] = v.strip()
        else:
            sec[cur].append(t)
    ew = head.get("EDGE_WEIGHT_TYPE", head.get("EDGE_WEIGHT_FORMAT"))
    if ew != "EUC_2D":
        raise ValueError(f"{path.name}: edge weight {ew!r}, only EUC_2D is read")
    N, S = int(head["DIMENSION"]), int(head["STATIONS"])
    xy = sec["NODE_COORD_SECTION"]
    if [int(t[0]) for t in xy] != list(range(1, N + 1)):
        raise ValueError(f"{path.name}: {len(xy)} coordinates, DIMENSION {N}")
    F = [int(t[0]) - 1 for t in sec["STATIONS_COORD_SECTION"]]
    depot = [int(t[0]) - 1 for t in sec["DEPOT_SECTION"] if t[0] != "-1"]
    dem = {int(t[0]) - 1: float(t[1]) for t in sec["DEMAND_SECTION"]}
    if len(F) != S or len(depot) != 1:
        raise ValueError(f"{path.name}: {len(F)} stations for STATIONS {S}, {len(depot)} depots")
    depot = depot[0]
    I = [k for k in range(N) if k not in F and k != depot]
    if sorted(dem) != sorted(I + [depot]) or dem[depot] != 0:
        raise ValueError(f"{path.name}: demands do not cover the depot and customers")
    X = np.array([[float(t[1]), float(t[2])] for t in xy])
    b = np.zeros(N)
    b[I] = [dem[i] for i in I]
    return dict(name=path.stem, NAME=head.get("NAME", "").removesuffix(".evrp"), X=X, D=dist(X),
                depot=depot, I=I, F=F, b=b, C=float(head["CAPACITY"]),
                Q=float(head["ENERGY_CAPACITY"]), h=float(head["ENERGY_CONSUMPTION"]),
                K=int(head["VEHICLES"]), opt=value(head.get("OPTIMAL_VALUE", "0")))


def fetch(keys=KEYS, root=FETCHED):
    for k in keys:
        f = Path(root) / f"{k}.evrp"
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(urllib.request.urlopen(URL + f"{k}.evrp").read())


def load(key, root=FETCHED):
    """Fetch if absent, verify SHA-256 against the committed manifest, read."""
    f = Path(root) / f"{key}.evrp"
    if not f.exists():
        fetch([key], root)
    if hashlib.sha256(f.read_bytes()).hexdigest() != SHA[f"{key}.evrp"]:
        raise ValueError(f"{key}: SHA-256 differs from data/evrp.sha256")
    return dict(read(f), key=key, sha256=SHA[f"{key}.evrp"])


def sub(p, I, F):
    """The instance restricted to the depot, customers I and stations F, renumbered in that
    order; VEHICLES becomes the capacity bound ceil(sum b / C)."""
    v = [p["depot"], *I, *F]
    X, b = p["X"][v], p["b"][v]
    return dict(name=f"{p['name']}[{','.join(str(k + 1) for k in I)}]", NAME="", X=X, D=dist(X),
                depot=0, I=list(range(1, len(I) + 1)), F=list(range(len(I) + 1, len(v))), b=b,
                C=p["C"], Q=p["Q"], h=p["h"], K=int(np.ceil(b.sum() / p["C"] - 1e-9)), opt=None)
