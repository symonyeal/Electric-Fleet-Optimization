//! Battery-electric bus scheduling and charging on a GTFS corridor (Models).
//!
//! The compiled Instance (Models §1, §4) holds everything M0, M1 and M2 read from a corridor and
//! a scenario, built once:
//!   arcs ..... (i, j, tau): trip j may follow trip i, arr_i + tau + layover <= dep_j, tau the
//!              deadhead seconds, great-circle km x detour / speed
//!   km ....... deadhead km on each arc; km0 from the depot to each trip, km1 from it back
//!   e ........ trip energies kappa km_j (kWh)
//!   win ...... per trip leaving a charging site, the slots t (of delta seconds) before dep_j
//!              within the charging window
//!   rb, top, s0b  reserve, ceiling and initial energy (kWh)

#[cfg(test)]
pub mod enumerate;
pub mod fleet;
pub mod m0;
pub mod replay;

use crate::scenario::{Place, Transit};
use serde::Deserialize;
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

#[derive(Clone, Debug, Deserialize)]
pub struct Trip {
    pub id: String,
    pub first: String,
    pub last: String,
    /// Seconds after midnight of the service day, possibly past 86400.
    pub dep: f64,
    pub arr: f64,
    pub km: f64,
    #[serde(default)]
    pub block: Option<String>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct Stop {
    pub lat: f64,
    pub lon: f64,
}

/// A GTFS extract: trips sorted by departure and their end stops (Data §2).
#[derive(Clone, Debug, Deserialize)]
pub struct Corridor {
    pub trips: Vec<Trip>,
    pub stops: BTreeMap<String, Stop>,
}

pub fn corridor(path: &Path) -> Result<Corridor, String> {
    let at = |e: &dyn std::fmt::Display| format!("{}: {e}", path.display());
    let c: Corridor =
        serde_json::from_str(&fs::read_to_string(path).map_err(|e| at(&e))?).map_err(|e| at(&e))?;
    for t in &c.trips {
        if !c.stops.contains_key(&t.first) || !c.stops.contains_key(&t.last) {
            return Err(at(&format!("trip {} names a stop the extract lacks", t.id)));
        }
        if !(t.dep.is_finite() && t.arr >= t.dep && t.km >= 0.0) {
            return Err(at(&format!("trip {} has invalid times or distance", t.id)));
        }
    }
    Ok(c)
}

/// Haversine distance (km) between two points given in degrees.
pub fn great_circle_km(a: (f64, f64), b: (f64, f64)) -> f64 {
    let (p1, p2) = (a.0.to_radians(), b.0.to_radians());
    let h = ((p2 - p1) / 2.0).sin().powi(2)
        + p1.cos() * p2.cos() * ((b.1 - a.1).to_radians() / 2.0).sin().powi(2);
    2.0 * 6371.0088 * h.sqrt().asin()
}

impl Stop {
    pub fn at(&self) -> (f64, f64) {
        (self.lat, self.lon)
    }
}

impl Place {
    pub fn at(&self) -> (f64, f64) {
        (self.lat, self.lon)
    }
}

pub struct Instance<'a> {
    pub c: &'a Corridor,
    pub v: &'a Transit,
    pub arcs: Vec<(usize, usize, f64)>,
    pub km: Vec<f64>,
    pub km0: Vec<f64>,
    pub km1: Vec<f64>,
    pub e: Vec<f64>,
    pub site: BTreeMap<String, String>,
    pub win: BTreeMap<usize, Vec<i64>>,
    pub rb: f64,
    pub top: f64,
    pub s0b: f64,
}

/// The instance of corridor c under scenario v. O(n^2) in the trips.
pub fn compile<'a>(c: &'a Corridor, v: &'a Transit) -> Instance<'a> {
    let t = &c.trips;
    let det = v.deadhead.detour;
    let km = |a: (f64, f64), b: (f64, f64)| great_circle_km(a, b) * det;
    let stop = |s: &str| c.stops[s].at();
    let mut arcs = Vec::new();
    let mut akm = Vec::new();
    for (i, a) in t.iter().enumerate() {
        for (j, b) in t.iter().enumerate() {
            let k = km(stop(&a.last), stop(&b.first));
            let tau = 3600.0 * k / v.deadhead.speed;
            if i != j && a.arr + tau + v.time.layover <= b.dep + 1e-9 {
                arcs.push((i, j, tau));
                akm.push(k);
            }
        }
    }
    let site: BTreeMap<String, String> = v
        .sites
        .iter()
        .flat_map(|(s, d)| d.stops.iter().map(move |x| (x.clone(), s.clone())))
        .collect();
    let (dl, w) = (v.time.delta, v.time.window);
    let win = t
        .iter()
        .enumerate()
        .filter(|(_, tr)| site.contains_key(&tr.first))
        .map(|(j, tr)| {
            (
                j,
                (((tr.dep - w) / dl).ceil() as i64..(tr.dep / dl).floor() as i64).collect(),
            )
        })
        .collect();
    let b = &v.battery;
    Instance {
        c,
        v,
        arcs,
        km: akm,
        km0: t
            .iter()
            .map(|tr| km(v.depot.at(), stop(&tr.first)))
            .collect(),
        km1: t
            .iter()
            .map(|tr| km(stop(&tr.last), v.depot.at()))
            .collect(),
        e: t.iter().map(|tr| b.kappa * tr.km).collect(),
        site,
        win,
        rb: b.reserve * b.b,
        top: b.smax * b.b,
        s0b: b.s0 * b.b,
    }
}

/// The corridor's trips departing before hour until.
pub fn until(c: &Corridor, hour: f64) -> Corridor {
    Corridor {
        trips: c
            .trips
            .iter()
            .filter(|t| t.dep < 3600.0 * hour)
            .cloned()
            .collect(),
        stops: c.stops.clone(),
    }
}

#[cfg(test)]
pub(crate) mod fixtures {
    use super::*;
    use crate::scenario::{data, transit};

    /// Departures of revision 89e967d's tests/test_fleet.py::tiny for seeds 0..5.
    pub const DEPS: [[f64; 5]; 6] = [
        [25200.0, 25200.0, 28800.0, 30000.0, 33600.0],
        [21600.0, 27600.0, 28800.0, 32400.0, 34800.0],
        [22800.0, 25200.0, 25200.0, 26400.0, 33600.0],
        [22800.0, 24000.0, 24000.0, 24000.0, 32400.0],
        [28800.0, 31200.0, 33600.0, 34800.0, 34800.0],
        [21600.0, 27600.0, 31200.0, 32400.0, 32400.0],
    ];

    /// Five trips from and to one stop `a`, the only site, beside the depot. Each trip uses 40%
    /// of the 250 kWh battery; a bus starting at 90% with a 20% reserve charges before a second.
    pub fn tiny(seed: usize) -> (Corridor, Transit) {
        let trips = DEPS[seed]
            .iter()
            .enumerate()
            .map(|(k, &d)| Trip {
                id: format!("t{k}"),
                first: "a".into(),
                last: "a".into(),
                dep: d,
                arr: d + 1500.0,
                km: 0.4 * 250.0 / 1.3,
                block: Some("b".into()),
            })
            .collect();
        let c = Corridor {
            trips,
            stops: [(
                "a".to_owned(),
                Stop {
                    lat: 49.2,
                    lon: -123.1,
                },
            )]
            .into(),
        };
        let mut v = transit(&data("route100.toml")).unwrap();
        let mut a = v.sites["marpole"].clone();
        (a.stops, a.nbar) = (vec!["a".into()], 2.0);
        v.sites = [("A".to_owned(), a)].into();
        (v.depot.lat, v.depot.lon) = (49.2, -123.1);
        (c, v)
    }

    pub fn route100() -> (Corridor, Transit) {
        let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        (
            corridor(&root.join("data/corridors/route100.json")).unwrap(),
            transit(&data("route100.toml")).unwrap(),
        )
    }
}
