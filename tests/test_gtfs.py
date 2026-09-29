# The GTFS adapter (Data §2): times past midnight, service calendars, the pinned snapshot.

import datetime as dt
import json
import zipfile

import pytest

from data.gtfs import LEGEND, corridor, load, secs, services, trips

FIX = "tests/fixtures/route100.json"


def feed(tmp_path, files):
    f = tmp_path / "g.zip"
    with zipfile.ZipFile(f, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    return zipfile.ZipFile(f)


def test_secs_keeps_hours_past_midnight():
    assert secs(" 5:05:00") == 18300 and secs("25:10:30") == 90630


def test_services_apply_calendar_then_exceptions(tmp_path):
    z = feed(tmp_path, {
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,"
                        "start_date,end_date\nW,1,1,1,1,1,0,0,20260901,20261231\n"
                        "S,0,0,0,0,0,0,1,20260901,20261231\n",
        "calendar_dates.txt": "service_id,date,exception_type\nW,20260930,2\nS,20260930,1\n"})
    assert services(z, dt.date(2026, 10, 7)) == {"W"}
    assert services(z, dt.date(2026, 9, 30)) == {"S"}
    assert services(z, dt.date(2027, 1, 6)) == set()


@pytest.mark.data
def test_route_100_on_2026_10_07():
    T = trips(load(), dt.date(2026, 10, 7), routes={"100"})
    assert len(T) == 219 and len({t["block"] for t in T}) == 23
    assert all(t["dep"] < t["arr"] for t in T) and all(t["km"] > 0 for t in T)


@pytest.mark.data
def test_holiday_runs_sunday_service():
    """30 September 2026 swaps weekday service 1 for Sunday service 3 (166 trips on route 100)."""
    assert len(trips(load(), dt.date(2026, 9, 30), routes={"100"})) == 166


@pytest.mark.data
def test_fixture_matches_the_snapshot():
    with open(FIX, encoding="utf-8") as f:
        c = json.load(f)
    assert c["legend"] == LEGEND and c == corridor(load(), dt.date(2026, 10, 7), {"100"})


def test_fixture_is_self_describing():
    with open(FIX, encoding="utf-8") as f:
        c = json.load(f)
    assert c["legend"] == LEGEND and c["date"] == "2026-10-07" and len(c["trips"]) == 219
    assert {"sha256", "feed_version", "url"} <= set(c["source"])
    assert all(t["first"] in c["stops"] and t["last"] in c["stops"] for t in c["trips"])
