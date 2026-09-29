"""TransLink static GTFS (Data §2), pinned to one weekly snapshot.

The feed at URL is replaced weekly; a read verifies the SHA-256 of the pinned snapshot and
refuses any other. A trip is a dict:
    id, route, headsign, direction, block, service, first, last (stop ids),
    dep, arr (seconds after midnight of the service day, possibly >= 86400), km (shape distance)
"""

import csv
import datetime as dt
import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path

URL = "https://gtfs-static.translink.ca/gtfs/google_transit.zip"
SNAPSHOT = dict(url=URL, sha256="d587d4d91ce1cb23c27087c270c9b241adfd5668e19c39cdd823ccf7efdd986d",
                feed_version="26SEP_20260925", bytes=16146377, retrieved="2026-09-29")
LEGEND = ("Route and arrival data used in this product or service is provided by permission of "
          "TransLink. TransLink assumes no responsibility for the accuracy or currency of the "
          "Data used in this product or service.")
FILE = Path(__file__).parent / "fetched" / "gtfs" / "translink.zip"


def load(path=FILE):
    """The pinned snapshot as a ZipFile; fetched if absent, refused if its SHA-256 differs."""
    path = Path(path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen(URL).read())
    if hashlib.sha256(path.read_bytes()).hexdigest() != SNAPSHOT["sha256"]:
        raise ValueError(f"{path}: not snapshot {SNAPSHOT['feed_version']}; the feed changes "
                         "weekly, so the pinned copy must be supplied")
    return zipfile.ZipFile(path)


def rows(z, name):
    with z.open(name) as h:
        yield from csv.DictReader(io.TextIOWrapper(h, "utf-8-sig"))


def secs(t):
    """'H:MM:SS' -> seconds; GTFS hours run past 24 for trips after midnight."""
    h, m, s = (int(x) for x in t.strip().split(":"))
    return 3600 * h + 60 * m + s


def services(z, date):
    """Service ids active on date: calendar by weekday and range, then calendar_dates
    (exception 1 adds, 2 removes)."""
    d, day = date.strftime("%Y%m%d"), date.strftime("%A").lower()
    S = {r["service_id"] for r in rows(z, "calendar.txt")
         if r[day] == "1" and r["start_date"] <= d <= r["end_date"]}
    for r in rows(z, "calendar_dates.txt"):
        if r["date"] == d:
            (S.add if r["exception_type"] == "1" else S.discard)(r["service_id"])
    return S


def trips(z, date, routes=None):
    """Trips of the service day, optionally only routes with these short names (leading zeros
    ignored), sorted by departure. One pass over stop_times."""
    S = services(z, date)
    name = {r["route_id"]: r["route_short_name"].lstrip("0") for r in rows(z, "routes.txt")}
    T = {r["trip_id"]: dict(id=r["trip_id"], route=name[r["route_id"]], headsign=r["trip_headsign"],
                            direction=int(r["direction_id"]), block=r["block_id"],
                            service=r["service_id"])
         for r in rows(z, "trips.txt")
         if r["service_id"] in S and (routes is None or name[r["route_id"]] in routes)}
    ends = {}
    for r in rows(z, "stop_times.txt"):
        if r["trip_id"] in T:
            k, e = int(r["stop_sequence"]), ends.setdefault(r["trip_id"], [None, None, 0.0])
            if e[0] is None or k < e[0][0]:
                e[0] = (k, r["stop_id"], secs(r["departure_time"]))
            if e[1] is None or k > e[1][0]:
                e[1] = (k, r["stop_id"], secs(r["arrival_time"]))
            e[2] = max(e[2], float(r["shape_dist_traveled"] or 0))
    for t, (f, l, km) in ends.items():
        T[t].update(first=f[1], dep=f[2], last=l[1], arr=l[2], km=km)
    return sorted((t for t in T.values() if "dep" in t), key=lambda t: (t["dep"], t["id"]))


def corridor(z, date, routes):
    """A self-describing, committable extract: trips, their end stops, source and legend."""
    T = trips(z, date, routes)
    used = {t["first"] for t in T} | {t["last"] for t in T}
    stops = {r["stop_id"]: dict(name=r["stop_name"], lat=float(r["stop_lat"]),
                                lon=float(r["stop_lon"]))
             for r in rows(z, "stops.txt") if r["stop_id"] in used}
    return dict(date=date.isoformat(), routes=sorted(routes), legend=LEGEND,
                source={k: SNAPSHOT[k] for k in ("url", "sha256", "feed_version", "retrieved")},
                trips=T, stops=dict(sorted(stops.items())))


if __name__ == "__main__":
    import json
    import sys
    d, R = dt.date.fromisoformat(sys.argv[1]), set(sys.argv[2:])
    print(json.dumps(corridor(load(), d, R), indent=1))
