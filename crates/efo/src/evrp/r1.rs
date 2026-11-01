//! R1 (Routing §2): the EVRP on the station-path multigraph, solved by HiGHS.
//!
//! x_p binary per path p in P = paths(p), u_i in [b_i, C] the load delivered up to and including
//! customer i, y_i in [alpha_i, Q] the charge on arrival at i:
//!
//! ```text
//! min  sum l_p x_p                                                             (R1.1)
//! sum_{delta+(i)} x = sum_{delta-(i)} x = 1                                    (R1.2)
//! u_j - u_i >= b_j - C (1 - X_ij) + (C - b_i - b_j) X_ji,  X_ij = sum_{P_ij} x (R1.3)
//! y_i >= sum_{delta+(i)} a_p x_p                                               (R1.4)
//! y_j <= Q - sum_{delta-(j) \ D} w_p x_p                                       (R1.5)
//! y_j <= y_i - e_ij x_ij + (Q - alpha_i)(1 - x_ij),  (i, j) direct             (R1.6)
//! sum_{delta+(0)} x >= ceil(sum b / C)
//! ```
//!
//! (R1.3) is the MTZ row lifted by Desrochers and Laporte (1991); alpha_i = min_{delta+(i)} a_p
//! bounds y_i below and tightens (R1.6). D is the set of direct arcs not leaving the depot.

use super::Instance;
use super::paths::{Path, paths};
use super::replay::replay;
use crate::cert::{Outcome, Record, record};
use crate::lp::Lp;
use serde_json::json;
use std::collections::BTreeMap;
use std::time::Instant;

pub const FORMULATION: &str = "R1/1";

/// The R1 program over arcs, or the customers that no admissible path enters or leaves.
fn rows(p: &Instance, arcs: &[Path]) -> Result<Lp, Vec<usize>> {
    let n = p.i.len();
    let mut out: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
    let mut inn: BTreeMap<usize, Vec<usize>> = BTreeMap::new();
    let mut pair: BTreeMap<(usize, usize), Vec<usize>> = BTreeMap::new();
    for (k, a) in arcs.iter().enumerate() {
        out.entry(a.i).or_default().push(k);
        inn.entry(a.j).or_default().push(k);
        pair.entry((a.i, a.j)).or_default().push(k);
    }
    let cut: Vec<usize> =
        p.i.iter()
            .copied()
            .filter(|i| !out.contains_key(i) || !inn.contains_key(i))
            .collect();
    if !cut.is_empty() {
        return Err(cut);
    }
    let alpha: BTreeMap<usize, f64> =
        p.i.iter()
            .map(|&i| {
                (
                    i,
                    out[&i]
                        .iter()
                        .map(|&k| arcs[k].a)
                        .fold(f64::INFINITY, f64::min),
                )
            })
            .collect();
    let mut m = Lp::default();
    for a in arcs {
        m.var(a.l, 0.0, 1.0, true);
    }
    let u0 = m.n();
    for &i in &p.i {
        m.var(0.0, p.b[i], p.cap, false);
    }
    let y0 = m.n();
    for &i in &p.i {
        m.var(0.0, alpha[&i], p.q, false);
    }
    let (u, y) = (|k: usize| u0 + k, |k: usize| y0 + k);
    let ones = |ks: &[usize]| ks.iter().map(|&k| (k, 1.0)).collect::<Vec<_>>();
    for &i in &p.i {
        m.eq(ones(&out[&i]), 1.0); // (R1.2)
        m.eq(ones(&inn[&i]), 1.0);
    }
    m.ge(
        ones(&out[&p.o]),
        (p.i.iter().map(|&i| p.b[i]).sum::<f64>() / p.cap - 1e-9).ceil(),
    );
    let none = Vec::new();
    for (ki, &i) in p.i.iter().enumerate() {
        for (kj, &j) in p.i.iter().enumerate() {
            if i != j {
                // (R1.3), lifted
                let mut a = vec![(u(kj), 1.0), (u(ki), -1.0)];
                a.extend(
                    pair.get(&(i, j))
                        .unwrap_or(&none)
                        .iter()
                        .map(|&k| (k, -p.cap)),
                );
                a.extend(
                    pair.get(&(j, i))
                        .unwrap_or(&none)
                        .iter()
                        .map(|&k| (k, -(p.cap - p.b[i] - p.b[j]))),
                );
                m.ge(a, p.b[j] - p.cap);
            }
        }
    }
    let at: BTreeMap<usize, usize> = p.i.iter().enumerate().map(|(k, &i)| (i, k)).collect();
    for (k, &i) in p.i.iter().enumerate() {
        let mut a = vec![(y(k), 1.0)]; // (R1.4)
        a.extend(out[&i].iter().map(|&e| (e, -arcs[e].a)));
        m.ge(a, 0.0);
    }
    for (k, &j) in p.i.iter().enumerate() {
        let mut a = vec![(y(k), 1.0)]; // (R1.5)
        a.extend(
            inn[&j]
                .iter()
                .filter(|&&e| !arcs[e].direct() || arcs[e].i == p.o)
                .map(|&e| (e, arcs[e].w)),
        );
        m.le(a, p.q);
    }
    for (e, a) in arcs.iter().enumerate() {
        if a.direct() && a.i != p.o && a.j != p.o {
            let big = p.q - alpha[&a.i]; // (R1.6)
            m.le(
                vec![(y(at[&a.j]), 1.0), (y(at[&a.i]), -1.0), (e, a.a + big)],
                big,
            );
        }
    }
    debug_assert_eq!(m.n(), arcs.len() + 2 * n);
    Ok(m)
}

/// Depot-to-depot routes (1-based) of the arcs chosen by x.
pub fn routes(o: usize, arcs: &[Path], x: &[f64]) -> Vec<Vec<usize>> {
    let succ: BTreeMap<usize, &Path> = arcs
        .iter()
        .zip(x)
        .filter(|(a, v)| **v > 0.5 && a.i != o)
        .map(|(a, _)| (a.i, a))
        .collect();
    let mut out = Vec::new();
    for (a, v) in arcs.iter().zip(x) {
        if *v > 0.5 && a.i == o {
            let mut r = a.nodes.clone();
            while let Some(next) = succ.get(r.last().unwrap()) {
                r.extend(&next.nodes[1..]);
            }
            out.push(r.iter().map(|k| k + 1).collect());
        }
    }
    out
}

/// R1 by HiGHS within time seconds at relative gap gap. U is the replayed length of the routes,
/// L HiGHS's dual bound.
pub fn r1(p: &Instance, time: f64, gap: f64) -> Record {
    let t0 = Instant::now();
    let arcs = paths(p);
    let m = match rows(p, &arcs) {
        Ok(m) => m,
        Err(cut) => {
            return record(
                "R1",
                &p.name,
                Outcome {
                    solver_status: "infeasible",
                    u: None,
                    l: None,
                    replayed: None,
                    objective: None,
                    bound_source: "highs_dual",
                    message: format!(
                        "customers {:?} have no admissible path in or out",
                        cut.iter().map(|k| k + 1).collect::<Vec<_>>()
                    ),
                    elapsed: t0.elapsed().as_secs_f64(),
                    detail: json!({"formulation": FORMULATION, "paths": arcs.len()}),
                },
            );
        }
    };
    let s = m.solve(time, gap);
    let r = s.x.as_ref().map(|x| routes(p.o, &arcs, x));
    let rp = r.as_ref().map(|r| replay(p, r, true));
    record(
        "R1",
        &p.name,
        Outcome {
            solver_status: s.status,
            u: rp.as_ref().filter(|rp| rp.ok).map(|rp| rp.length),
            l: s.bound,
            replayed: rp.as_ref().map(|rp| rp.ok),
            objective: s.f,
            bound_source: "highs_dual",
            message: format!("HiGHS {}", s.status),
            elapsed: t0.elapsed().as_secs_f64(),
            detail: json!({"formulation": FORMULATION, "time_limit": time, "mip_rel_gap": gap, "paths": arcs.len(),
            "rows": m.rows.len(), "nodes": s.nodes, "routes": r, "replay": rp.map(|rp| json!({"ok": rp.ok, "defects": rp.defects}))}),
        },
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::evrp::{enumerate::enumerate, fixture};

    #[test]
    fn r1_equals_enumeration_on_fixtures() {
        // Values of revision 89e967d (R1 and checks/enum.py agreed on each).
        for (name, z) in [
            ("tiny.evrp", 33.211102550927976),
            ("rand0.evrp", 310.6165226392452),
            ("rand1.evrp", 332.4344350835016),
            ("rand2.evrp", 317.73661544443394),
            ("rand3.evrp", 383.5573047794533),
        ] {
            let p = fixture(name);
            let r = r1(&p, 60.0, 1e-7);
            assert!(r.certified, "{name}: {r:?}");
            assert!((r.u.unwrap() - z).abs() < 1e-6, "{name}");
            assert!((enumerate(&p).0 - z).abs() < 1e-6, "{name}");
        }
    }

    #[test]
    fn a_short_battery_is_infeasible() {
        let mut p = fixture("rand0.evrp");
        p.q = 0.9 * p.i.iter().map(|&i| p.d[p.o][i]).fold(0.0, f64::max);
        let r = r1(&p, 60.0, 1e-7);
        assert_eq!(r.solver_status, "infeasible");
        assert!(enumerate(&p).0.is_infinite());
    }
}
