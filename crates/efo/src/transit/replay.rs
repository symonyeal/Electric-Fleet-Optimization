//! Independent replay of bus schedules (Validation §2): written from the corridor and scenario
//! alone, it reads no model rows and recomputes every cost from the schedule.
//!
//! A duty is a list of trip ids in service order. It is time-connected if each next trip starts
//! no earlier than the previous one ends plus the deadhead between their stops and the layover:
//! arr_i + 3600 km / speed + layover <= dep_j, km = great-circle distance x detour.

use super::{Corridor, great_circle_km};
use crate::scenario::{Transit, billed};
use serde::Serialize;
use std::collections::{BTreeMap, HashMap};

/// Charging slots per trip: trip id -> slot -> battery-side kW, charged before the trip at its
/// first stop.
pub type Plan = BTreeMap<String, BTreeMap<i64, f64>>;

/// Opened sites: site -> (plugs, grid upgrade kW).
pub type Infra = BTreeMap<String, (f64, f64)>;

#[derive(Clone, Debug, Serialize)]
pub struct Replay {
    pub ok: bool,
    pub defects: Vec<(String, String)>,
    pub fleet: usize,
    pub deadhead_km: f64,
}

/// Kinds: unknown_trip, missing, repeat, time.
pub fn replay(c: &Corridor, duties: &[Vec<String>], v: &Transit) -> Replay {
    let trips: HashMap<&str, &super::Trip> = c.trips.iter().map(|t| (t.id.as_str(), t)).collect();
    let (mut defects, mut seen, mut dh) = (Vec::new(), HashMap::<&str, usize>::new(), 0.0);
    for d in duties {
        if let Some(bad) = d.iter().find(|k| !trips.contains_key(k.as_str())) {
            defects.push(("unknown_trip".to_owned(), bad.clone()));
            continue;
        }
        for k in d {
            *seen.entry(k.as_str()).or_default() += 1;
        }
        for e in d.windows(2) {
            let (a, b) = (trips[e[0].as_str()], trips[e[1].as_str()]);
            let km =
                great_circle_km(c.stops[&a.last].at(), c.stops[&b.first].at()) * v.deadhead.detour;
            dh += km;
            if a.arr + 3600.0 * km / v.deadhead.speed + v.time.layover > b.dep + 1e-9 {
                defects.push(("time".into(), format!("{} -> {}", a.id, b.id)));
            }
        }
    }
    for t in &c.trips {
        match seen.get(t.id.as_str()) {
            None => defects.push(("missing".into(), t.id.clone())),
            Some(&k) if k > 1 => defects.push(("repeat".into(), t.id.clone())),
            _ => {}
        }
    }
    Replay {
        ok: defects.is_empty(),
        defects,
        fleet: duties.len(),
        deadhead_km: dh,
    }
}

/// The schedule's cost recomputed from its parts, with the replay's verdict.
#[derive(Clone, Debug, Serialize)]
pub struct EnergyReplay {
    pub ok: bool,
    pub defects: Vec<(String, String)>,
    pub cost: f64,
    pub parts: BTreeMap<&'static str, f64>,
}

/// Replay an M1 (or, with loss, M2) schedule slot by slot (Models §3-§5).
///
/// The tariff (Data §3): 1 + rider multiplies energy, depot energy, demand and basic charges;
/// demand is the peak over the slots of the billing window. An open site's meter carries its base
/// load L all day: its demand is at least L and L must fit its grid capacity. The depot restores
/// each bus to s0 B overnight, max(0, s0 B - e) on return; nothing is bought back. With loss,
/// grid power is p/eta + alpha p^2 (10) and the taper p <= P (1 - e/B) (11) holds. Kinds: those
/// of replay, energy, overcharge, window, presence, power, site, plugs, grid, taper.
pub fn replay_energy(
    c: &Corridor,
    v: &Transit,
    duties: &[Vec<String>],
    plan: &Plan,
    infra: &Infra,
    loss: bool,
) -> EnergyReplay {
    let base = replay(c, duties, v);
    let mut defects = base.defects.clone();
    let tol = 1e-6;
    let trips: HashMap<&str, &super::Trip> = c.trips.iter().map(|t| (t.id.as_str(), t)).collect();
    let (b, ch, co, dl) = (&v.battery, &v.charger, &v.cost, v.time.delta);
    let (rb, top, s0b, h, det, speed) = (
        b.reserve * b.b,
        b.smax * b.b,
        b.s0 * b.b,
        dl / 3600.0,
        v.deadhead.detour,
        v.deadhead.speed,
    );
    let site: HashMap<&str, &str> = v
        .sites
        .iter()
        .flat_map(|(s, d)| d.stops.iter().map(move |x| (x.as_str(), s.as_str())))
        .collect();
    let mut bad = |k: &str, s: String| defects.push((k.to_owned(), s));
    let (mut use_, mut km_dh, mut kwh, mut restore) =
        (BTreeMap::<(String, i64), (f64, f64)>::new(), 0.0, 0.0, 0.0);
    for d in duties {
        if d.iter().any(|k| !trips.contains_key(k.as_str())) {
            continue;
        }
        let km = great_circle_km(v.depot.at(), c.stops[&trips[d[0].as_str()].first].at()) * det;
        km_dh += km;
        let mut e = s0b - b.kappa * km;
        let mut here: Option<f64> = None;
        if e < rb - tol {
            bad(
                "energy",
                format!("pull-out to {} arrives with {e:.6}", d[0]),
            );
        }
        for (q, k) in d.iter().enumerate() {
            let t = trips[k.as_str()];
            for (&s, &kw) in plan.get(k).into_iter().flatten() {
                let st = site.get(t.first.as_str()).copied();
                if st.is_none_or(|st| !infra.contains_key(st)) {
                    bad(
                        "site",
                        format!("{k} charges at {}, not an open site", t.first),
                    );
                }
                let (t0, t1) = (s as f64 * dl, (s + 1) as f64 * dl);
                if !(t0 >= t.dep - v.time.window - tol && t1 <= t.dep + tol) {
                    bad("window", format!("{k} slot {s}"));
                }
                if here.is_some_and(|a| t0 < a - tol) {
                    bad("presence", format!("{k} slot {s} before the bus arrives"));
                }
                if kw > ch.p + tol || kw < -tol {
                    bad("power", format!("{k} slot {s}: {kw:.6} kW"));
                }
                e += h * kw;
                let grid = kw / ch.eta + if loss { ch.alpha * kw * kw } else { 0.0 }; // (10)
                if loss && kw > ch.p * (1.0 - e / b.b) + tol {
                    bad("taper", format!("{k} slot {s}: {kw:.6} kW at {e:.6} kWh")); // (11)
                }
                kwh += h * grid;
                let u = use_.entry((st.unwrap_or("").to_owned(), s)).or_default();
                (u.0, u.1) = (u.0 + 1.0, u.1 + grid);
            }
            if e > top + tol {
                bad("overcharge", format!("{k} departs with {e:.6}"));
            }
            if e - b.kappa * t.km < rb - tol {
                bad("energy", format!("{k} would end below reserve"));
            }
            e -= b.kappa * t.km;
            let next = match d.get(q + 1) {
                Some(n) => c.stops[&trips[n.as_str()].first].at(),
                None => v.depot.at(),
            };
            let km = great_circle_km(c.stops[&t.last].at(), next) * det;
            km_dh += km;
            e -= b.kappa * km;
            here = Some(t.arr + 3600.0 * km / speed);
            if e < rb - tol {
                bad(
                    "energy",
                    format!("after {k} the bus reaches its next stop with {e:.6}"),
                );
            }
        }
        restore += (s0b - e).max(0.0) / ch.eta; // restored overnight, never sold back
    }
    let (rho, w0, w1) = co.tariff();
    let mut peak: BTreeMap<&str, f64> = infra.keys().map(|s| (s.as_str(), v.sites[s].l)).collect();
    for (s, &(_, up)) in infra {
        let d = &v.sites[s];
        if d.l > d.g0 + up + tol {
            bad("grid", format!("{s}: base load {} kW over capacity", d.l));
        }
    }
    for ((s, slot), &(k, kw)) in &use_ {
        let Some(&(plugs, up)) = infra.get(s) else {
            continue;
        };
        let d = &v.sites[s];
        if k > plugs {
            bad("plugs", format!("{s} slot {slot}: {k} > {plugs}"));
        }
        if d.l + kw > d.g0 + up + tol {
            bad("grid", format!("{s} slot {slot}: {} kW", d.l + kw));
        }
        if billed(*slot as f64 * dl, w0, w1) {
            let p = peak.get_mut(s.as_str()).unwrap();
            *p = p.max(d.l + kw);
        }
    }
    let nsites = infra.len() as f64;
    let parts = BTreeMap::from([
        ("buses", co.f * duties.len() as f64),
        ("deadhead", co.deadhead * km_dh),
        ("energy", rho * co.energy * kwh),
        ("depot_energy", rho * co.depot_energy * restore),
        ("sites", co.site * nsites),
        ("plugs", co.plug * infra.values().map(|i| i.0).sum::<f64>()),
        (
            "upgrade",
            co.upgrade * infra.values().map(|i| i.1).sum::<f64>(),
        ),
        ("peak", rho * co.peak * peak.values().sum::<f64>()),
        ("basic", rho * co.basic * nsites),
    ]);
    EnergyReplay {
        ok: defects.is_empty(),
        defects,
        cost: parts.values().sum(),
        parts,
    }
}
