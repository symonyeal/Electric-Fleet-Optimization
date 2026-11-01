//! Independent route replay (Routing §1, §7): written from the report's rules and the instance
//! alone, it imports no formulation.
//!
//! Exchange format: one line per route, 1-based node identifiers of the instance file, the depot
//! at both ends. An interior depot visit ends one route and starts the next.

use super::Instance;
use crate::scenario::Recharge;
use serde::Serialize;
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

/// ok, defects (kind, detail), length, and per depot-to-depot route its load and least charge.
/// Kinds: unknown_node, endpoint, missing, repeat, overload, battery.
#[derive(Clone, Debug, Serialize)]
pub struct Replay {
    pub ok: bool,
    pub defects: Vec<(String, String)>,
    pub length: f64,
    pub load: Vec<f64>,
    pub low: Vec<f64>,
}

/// Check routes against the report's rules (full recharge at stations and the depot); with
/// battery false the charge is not checked.
pub fn replay(p: &Instance, routes: &[Vec<usize>], battery: bool) -> Replay {
    let n = p.x.len();
    let tol = 1e-9;
    let (mut defects, mut seen, mut load, mut low) =
        (Vec::new(), BTreeMap::new(), Vec::new(), Vec::new());
    let mut length = 0.0;
    let mut bad = |k: &str, s: String| defects.push((k.to_owned(), s));
    for r in routes {
        if r.iter().any(|&k| k == 0 || k > n) {
            bad("unknown_node", format!("{r:?}"));
            continue;
        }
        let v: Vec<usize> = r.iter().map(|k| k - 1).collect();
        if v.first() != Some(&p.o) || v.last() != Some(&p.o) {
            bad(
                "endpoint",
                format!("{r:?} does not start and end at depot {}", p.o + 1),
            );
        }
        let (mut q, mut y, mut m) = (0.0, p.q, p.q);
        if p.i.contains(&v[0]) {
            q = p.b[v[0]];
            *seen.entry(v[0]).or_insert(0) += 1;
        }
        for e in v.windows(2) {
            let (a, c) = (e[0], e[1]);
            let d = (p.x[c][0] - p.x[a][0]).hypot(p.x[c][1] - p.x[a][1]);
            length += d;
            y -= p.h * d;
            m = m.min(y);
            if battery && y < -tol {
                bad("battery", format!("{}->{} leaves {y:.6}", a + 1, c + 1));
            }
            if p.i.contains(&c) {
                q += p.b[c];
                *seen.entry(c).or_insert(0) += 1;
            }
            if c == p.o || p.f.contains(&c) {
                y = p.q;
            }
            if c == p.o {
                load.push(q);
                low.push(m);
                if q > p.cap + tol {
                    bad(
                        "overload",
                        format!("route ending at {} carries {q} > {}", c + 1, p.cap),
                    );
                }
                (q, m) = (0.0, p.q);
            }
        }
    }
    for &i in &p.i {
        match seen.get(&i) {
            None => bad("missing", format!("customer {}", i + 1)),
            Some(&k) if k > 1 => bad("repeat", format!("customer {} visited {k} times", i + 1)),
            _ => {}
        }
    }
    Replay {
        ok: defects.is_empty(),
        defects,
        length,
        load,
        low,
    }
}

/// cost = c_d length + c_e sum (q/eta + alpha q^2/tau) + c_tau sum tau, of R3 routes with partial
/// charges (Routing §5); ok and defects as replay's, with kinds energy, overcharge, power,
/// dwell and time in place of battery.
#[derive(Clone, Debug, Serialize)]
pub struct ChargeReplay {
    pub ok: bool,
    pub defects: Vec<(String, String)>,
    pub cost: f64,
    pub length: f64,
    pub grid: f64,
    pub dwell: f64,
}

/// INPUT charges: (route, position of the station in it) -> (q, tau), energy and hours.
pub fn replay_charge(
    p: &Instance,
    sc: &Recharge,
    routes: &[Vec<usize>],
    charges: &BTreeMap<(usize, usize), (f64, f64)>,
) -> ChargeReplay {
    let base = replay(p, routes, false);
    let mut defects = base.defects.clone();
    let tol = 1e-6;
    let (mut grid, mut dwell) = (0.0, 0.0);
    for (r, route) in routes.iter().enumerate() {
        if route.iter().any(|&k| k == 0 || k > p.x.len()) {
            continue;
        }
        let (mut e, mut clock) = (p.q, 0.0);
        for (pos, w) in route.windows(2).enumerate() {
            let (a, c) = (w[0] - 1, w[1] - 1);
            let d = (p.x[c][0] - p.x[a][0]).hypot(p.x[c][1] - p.x[a][1]);
            e -= p.h * d;
            clock += d / sc.time.speed;
            if e < -tol {
                defects.push((
                    "energy".into(),
                    format!("route {r} reaches node {} with {e:.6}", c + 1),
                ));
            }
            if p.f.contains(&c) {
                let (q, tau) = charges.get(&(r, pos + 1)).copied().unwrap_or((0.0, 0.0));
                if e + q > p.q + tol {
                    defects.push((
                        "overcharge".into(),
                        format!("route {r} station {}: {}", c + 1, e + q),
                    ));
                }
                if q > sc.charger.p * tau + tol {
                    defects.push((
                        "power".into(),
                        format!("route {r} station {}: {q} in {tau} h", c + 1),
                    ));
                }
                if tau < sc.time.tau_min - tol {
                    defects.push((
                        "dwell".into(),
                        format!("route {r} station {}: {tau} h", c + 1),
                    ));
                }
                e += q;
                clock += tau;
                dwell += tau;
                grid += q / sc.charger.eta
                    + if tau > 0.0 {
                        sc.charger.alpha * q * q / tau
                    } else {
                        0.0
                    };
            } else if c != p.o {
                clock += sc.time.service;
            }
        }
        if clock > sc.time.t + tol {
            defects.push((
                "time".into(),
                format!("route {r} returns at {clock:.6} h > {}", sc.time.t),
            ));
        }
    }
    ChargeReplay {
        ok: defects.is_empty(),
        defects,
        cost: sc.cost.distance * base.length + sc.cost.energy * grid + sc.cost.dwell * dwell,
        length: base.length,
        grid,
        dwell,
    }
}

pub fn read_routes(path: &Path) -> Result<Vec<Vec<usize>>, String> {
    let text = fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
    text.lines()
        .filter(|l| !l.trim().is_empty())
        .map(|l| {
            l.split_whitespace()
                .map(|t| {
                    t.parse()
                        .map_err(|e| format!("{}: {t}: {e}", path.display()))
                })
                .collect()
        })
        .collect()
}

pub fn routes_text(routes: &[Vec<usize>]) -> String {
    routes
        .iter()
        .map(|r| {
            r.iter()
                .map(|k| k.to_string())
                .collect::<Vec<_>>()
                .join(" ")
                + "\n"
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defects_are_named() {
        let p = crate::evrp::fixture("tiny.evrp");
        let ok = replay(&p, &[vec![1, 2, 6, 3, 6, 1], vec![1, 4, 1]], true);
        assert!(ok.ok && (ok.length - 33.211102550927976).abs() < 1e-12);
        let kinds = |r: &[Vec<usize>]| {
            replay(&p, r, true)
                .defects
                .into_iter()
                .map(|d| d.0)
                .collect::<Vec<_>>()
        };
        assert_eq!(
            kinds(&[vec![1, 2, 3, 4, 1]]),
            ["battery", "battery", "overload"]
        );
        assert_eq!(
            kinds(&[vec![1, 2, 1], vec![1, 2, 1]]),
            ["repeat", "missing", "missing"]
        );
        assert_eq!(
            kinds(&[vec![2, 1], vec![9]]),
            ["endpoint", "unknown_node", "missing", "missing"]
        );
    }
}
