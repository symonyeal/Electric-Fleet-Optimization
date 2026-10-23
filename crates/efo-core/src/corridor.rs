//! Transit corridors: the committed extract of TransLink static GTFS (Data §2), and its reader.
//!
//! Legend (a trip)
//!   id, block ..... GTFS trip and block ids     first, last .. end stop ids
//!   dep, arr ...... seconds after midnight of the service day (possibly >= 86400)
//!   km ............ shape distance
//!
//! A corridor keeps its JSON (`j`) beside the typed trips, since its digest is taken over the JSON
//! exactly as Python reads it (`dict(trips=T, stops=S)`).

use crate::jo;
use crate::json::{J, Obj};
use indexmap::IndexMap;
use std::collections::{HashMap, HashSet};
use std::io::Read;
use std::path::Path;

pub const URL: &str = "https://gtfs-static.translink.ca/gtfs/google_transit.zip";
pub const SNAPSHOT_SHA: &str = "d587d4d91ce1cb23c27087c270c9b241adfd5668e19c39cdd823ccf7efdd986d";
pub const FEED_VERSION: &str = "26SEP_20260925";
pub const RETRIEVED: &str = "2026-09-29";
pub const LEGEND: &str = "Route and arrival data used in this product or service is provided by permission of TransLink. TransLink assumes no responsibility for the accuracy or currency of the Data used in this product or service.";

#[derive(Clone, Debug)]
pub struct Trip {
    pub id: String,
    pub block: String,
    pub first: String,
    pub last: String,
    pub dep: f64,
    pub arr: f64,
    pub km: f64,
}

#[derive(Clone, Copy, Debug)]
pub struct Stop {
    pub lat: f64,
    pub lon: f64,
}

#[derive(Clone, Debug)]
pub struct Corridor {
    pub j: J,
    pub trips: Vec<Trip>,
    pub stops: IndexMap<String, Stop>,
}

fn s(j: &J, k: &str) -> String {
    match j.get(k) {
        Some(J::S(x)) => x.clone(),
        Some(J::I(x)) => x.to_string(),
        _ => String::new(),
    }
}

impl Corridor {
    pub fn from_j(j: J) -> Corridor {
        let trips = j
            .get("trips")
            .and_then(J::a)
            .map(|a| {
                a.iter()
                    .map(|t| Trip {
                        id: s(t, "id"),
                        block: s(t, "block"),
                        first: s(t, "first"),
                        last: s(t, "last"),
                        dep: t.get("dep").and_then(J::f).unwrap_or(0.0),
                        arr: t.get("arr").and_then(J::f).unwrap_or(0.0),
                        km: t.get("km").and_then(J::f).unwrap_or(0.0),
                    })
                    .collect()
            })
            .unwrap_or_default();
        let stops = j
            .get("stops")
            .and_then(J::o)
            .map(|o| {
                o.iter()
                    .map(|(k, v)| {
                        (
                            k.clone(),
                            Stop {
                                lat: v.get("lat").and_then(J::f).unwrap_or(0.0),
                                lon: v.get("lon").and_then(J::f).unwrap_or(0.0),
                            },
                        )
                    })
                    .collect()
            })
            .unwrap_or_default();
        Corridor { j, trips, stops }
    }

    pub fn read(path: &Path) -> Result<Corridor, String> {
        crate::json::read(path)
            .map(Corridor::from_j)
            .map_err(|e| format!("{}: {e}", path.display()))
    }

    /// Trips departing before hour h (`--until`).
    pub fn until(&self, h: f64) -> Corridor {
        let mut j = self.j.clone();
        let keep: Vec<J> = j
            .get("trips")
            .and_then(J::a)
            .unwrap()
            .iter()
            .filter(|t| t.get("dep").and_then(J::f).unwrap() < 3600.0 * h)
            .cloned()
            .collect();
        j.set("trips", J::A(keep));
        Corridor::from_j(j)
    }

    /// The pinned snapshot's digest recorded in the corridor's source, if any.
    pub fn sha256(&self) -> Option<String> {
        self.j.at("source.sha256").and_then(J::s).map(String::from)
    }

    /// `dict(trips=c["trips"], stops=c["stops"])`, the corridor identity.
    pub fn identity(&self) -> J {
        jo! {"trips" => self.j.get("trips").cloned().unwrap_or(J::Null), "stops" => self.j.get("stops").cloned().unwrap_or(J::Null)}
    }
}

/// The pinned snapshot's archive; refused if its SHA-256 differs (the feed changes weekly).
pub fn snapshot(path: &Path) -> Result<zip::ZipArchive<std::fs::File>, String> {
    let b = std::fs::read(path).map_err(|e| format!("{}: {e}", path.display()))?;
    if crate::digest::sha256_hex(&b) != SNAPSHOT_SHA {
        return Err(format!(
            "{}: not snapshot {FEED_VERSION}; the feed changes weekly, so the pinned copy must be supplied",
            path.display()
        ));
    }
    let f = std::fs::File::open(path).map_err(|e| e.to_string())?;
    zip::ZipArchive::new(f).map_err(|e| e.to_string())
}

fn rows(
    z: &mut zip::ZipArchive<std::fs::File>,
    name: &str,
) -> Result<Vec<HashMap<String, String>>, String> {
    let mut f = z.by_name(name).map_err(|e| format!("{name}: {e}"))?;
    let mut t = String::new();
    f.read_to_string(&mut t)
        .map_err(|e| format!("{name}: {e}"))?;
    let t = t.strip_prefix('\u{feff}').unwrap_or(&t);
    let mut r = csv::ReaderBuilder::new()
        .flexible(true)
        .from_reader(t.as_bytes());
    let h: Vec<String> = r
        .headers()
        .map_err(|e| e.to_string())?
        .iter()
        .map(String::from)
        .collect();
    let mut out = Vec::new();
    for rec in r.records() {
        let rec = rec.map_err(|e| e.to_string())?;
        out.push(
            h.iter()
                .cloned()
                .zip(rec.iter().map(String::from))
                .collect(),
        );
    }
    Ok(out)
}

/// 'H:MM:SS' -> seconds; GTFS hours run past 24 for trips after midnight.
pub fn secs(t: &str) -> i64 {
    let v: Vec<i64> = t
        .trim()
        .split(':')
        .map(|x| x.parse().unwrap_or(0))
        .collect();
    3600 * v[0] + 60 * v[1] + v[2]
}

/// Day of the week (0 = Monday) of a proleptic Gregorian date.
pub fn weekday(y: i64, m: i64, d: i64) -> usize {
    let (y, m) = if m < 3 { (y - 1, m + 12) } else { (y, m) };
    let k = y % 100;
    let j = y / 100;
    let h = (d + 13 * (m + 1) / 5 + k + k / 4 + j / 4 + 5 * j) % 7; // 0 = Saturday
    ((h + 5) % 7) as usize
}

const DAYS: [&str; 7] = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
];

/// Service ids active on date "YYYY-MM-DD": calendar by weekday and range, then calendar_dates
/// (exception 1 adds, 2 removes).
pub fn services(z: &mut zip::ZipArchive<std::fs::File>, date: &str) -> Result<Vec<String>, String> {
    let ymd: Vec<i64> = date.split('-').map(|x| x.parse().unwrap()).collect();
    let d = date.replace('-', "");
    let day = DAYS[weekday(ymd[0], ymd[1], ymd[2])];
    let mut s: Vec<String> = rows(z, "calendar.txt")?
        .into_iter()
        .filter(|r| r[day] == "1" && r["start_date"] <= d && d <= r["end_date"])
        .map(|r| r["service_id"].clone())
        .collect();
    for r in rows(z, "calendar_dates.txt")? {
        if r["date"] == d {
            if r["exception_type"] == "1" {
                if !s.contains(&r["service_id"]) {
                    s.push(r["service_id"].clone());
                }
            } else {
                s.retain(|x| *x != r["service_id"]);
            }
        }
    }
    Ok(s)
}

/// The committable extract of `routes` on `date`, as `data/gtfs.py corridor` writes it.
pub fn corridor(
    z: &mut zip::ZipArchive<std::fs::File>,
    date: &str,
    routes: &[String],
) -> Result<J, String> {
    let sv: HashSet<String> = services(z, date)?.into_iter().collect();
    let name: HashMap<String, String> = rows(z, "routes.txt")?
        .into_iter()
        .map(|r| {
            (
                r["route_id"].clone(),
                r["route_short_name"].trim_start_matches('0').to_string(),
            )
        })
        .collect();
    let mut t: IndexMap<String, Obj> = IndexMap::new();
    for r in rows(z, "trips.txt")? {
        let nm = &name[&r["route_id"]];
        if sv.contains(&r["service_id"]) && routes.contains(nm) {
            let mut o = Obj::new();
            o.insert("id".into(), J::S(r["trip_id"].clone()));
            o.insert("route".into(), J::S(nm.clone()));
            o.insert("headsign".into(), J::S(r["trip_headsign"].clone()));
            o.insert(
                "direction".into(),
                J::I(r["direction_id"].parse().unwrap_or(0)),
            );
            o.insert("block".into(), J::S(r["block_id"].clone()));
            o.insert("service".into(), J::S(r["service_id"].clone()));
            t.insert(r["trip_id"].clone(), o);
        }
    }
    type End = Option<(i64, String, i64)>;
    let mut ends: IndexMap<String, (End, End, f64)> = IndexMap::new();
    for r in rows(z, "stop_times.txt")? {
        if !t.contains_key(&r["trip_id"]) {
            continue;
        }
        let k: i64 = r["stop_sequence"].parse().unwrap();
        let e = ends
            .entry(r["trip_id"].clone())
            .or_insert((None, None, 0.0));
        if e.0.as_ref().is_none_or(|x| k < x.0) {
            e.0 = Some((k, r["stop_id"].clone(), secs(&r["departure_time"])));
        }
        if e.1.as_ref().is_none_or(|x| k > x.0) {
            e.1 = Some((k, r["stop_id"].clone(), secs(&r["arrival_time"])));
        }
        let km: f64 = if r["shape_dist_traveled"].is_empty() {
            0.0
        } else {
            r["shape_dist_traveled"].parse().unwrap()
        };
        e.2 = e.2.max(km);
    }
    for (id, (f, l, km)) in ends {
        let (f, l) = (f.unwrap(), l.unwrap());
        let o = t.get_mut(&id).unwrap();
        o.insert("first".into(), J::S(f.1));
        o.insert("dep".into(), J::I(f.2));
        o.insert("last".into(), J::S(l.1));
        o.insert("arr".into(), J::I(l.2));
        o.insert("km".into(), J::F(km));
    }
    let mut tr: Vec<Obj> = t.into_values().filter(|o| o.contains_key("dep")).collect();
    tr.sort_by(|a, b| {
        a["dep"]
            .i()
            .cmp(&b["dep"].i())
            .then(a["id"].s().cmp(&b["id"].s()))
    });
    let used: HashSet<String> = tr
        .iter()
        .flat_map(|o| {
            [
                o["first"].s().unwrap().to_string(),
                o["last"].s().unwrap().to_string(),
            ]
        })
        .collect();
    let mut stops: Vec<(String, J)> = rows(z, "stops.txt")?
        .into_iter()
        .filter(|r| used.contains(&r["stop_id"]))
        .map(|r| (r["stop_id"].clone(), jo! {"name" => r["stop_name"].clone(), "lat" => r["stop_lat"].parse::<f64>().unwrap(), "lon" => r["stop_lon"].parse::<f64>().unwrap()}))
        .collect();
    stops.sort_by(|a, b| a.0.cmp(&b.0));
    let mut rs: Vec<String> = routes.to_vec();
    rs.sort();
    Ok(jo! {
        "date" => date,
        "routes" => rs,
        "legend" => LEGEND,
        "source" => jo!{"url" => URL, "sha256" => SNAPSHOT_SHA, "feed_version" => FEED_VERSION, "retrieved" => RETRIEVED},
        "trips" => J::A(tr.into_iter().map(J::O).collect()),
        "stops" => J::O(stops.into_iter().collect()),
    })
}
