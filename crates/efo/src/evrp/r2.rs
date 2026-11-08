//! R2: set-partitioning bound by column generation with rounded capacity cuts (Routing §3, §4;
//! BT §6.1).
//!
//! Master over routes r with length c_r, visit counts a_ir and cut coefficients beta_S(r):
//!
//! ```text
//! min sum c_r lam_r   s.t.   sum_r a_ir lam_r = 1  (i in I),                     (R2.1)
//!                            sum_r beta_S(r) lam_r >= kappa(S) = ceil(b(S)/C),   (R2.3)
//!                            lam >= 0,
//! ```
//!
//! beta_S(r) the arcs of r's customer sequence 0, visits, 0 that enter S (Laporte, Nobert and
//! Desrochers 1985, in the robust form of Fukasawa et al. 2006). Every partition into feasible
//! elementary routes satisfies (R2.3). For any duals pi, sigma >= 0 and the exact least reduced
//! cost cbar* over ng-routes, cbar_r = c_r - sum_i a_ir pi_i - sum_S sigma_S beta_S(r),
//!
//! ```text
//! z* >= z_LP >= sum_i pi_i + sum_S sigma_S kappa(S) + n min(0, cbar*)            (R2.4)
//! ```
//!
//! (Lagrangean duality with the redundant row sum lam <= n). The bound needs exact pricing, not an
//! exact master; a pricing call stopped by its limit is not exact and updates nothing. Cuts are
//! separated at each convergence; the run converges when exact pricing finds no column, the
//! master meets (R2.4) within eps, and no cut is violated. The restricted master as a MILP over
//! the elementary columns gives a heuristic upper bound, replayed.

use super::Instance;
use super::paths::{Path, paths};
use super::replay::replay;
use crate::cert::{Gap, Outcome, Record, gap, record};
use crate::lp::Lp;
use efo_kernels::price::{Arc, Graph};
use serde_json::json;
use std::collections::{BTreeSet, HashSet};
use std::time::Instant;

pub const FORMULATION: &str = "R2-RCC/1";

/// A route: length, customers in order, all nodes from depot to depot (0-based).
#[derive(Clone, Debug)]
struct Col {
    cost: f64,
    visits: Vec<usize>,
    nodes: Vec<usize>,
}

/// ng-sets and labels are u128 bitmasks over the customers: at most 128 of them.
pub fn fits(n: usize) -> Result<(), String> {
    if n > 128 {
        return Err(format!("R2 handles at most 128 customers, not {n}"));
    }
    Ok(())
}

/// N_i: customer i and its nu - 1 nearest customers, as bitmasks over positions in I.
fn ng(p: &Instance, nu: usize) -> Vec<u128> {
    let mut out = vec![0u128; p.x.len()];
    for &i in &p.i {
        let mut near: Vec<usize> = (0..p.i.len()).collect();
        near.sort_by(|&a, &b| p.d[i][p.i[a]].total_cmp(&p.d[i][p.i[b]]));
        out[i] = near.iter().take(nu).fold(0, |m, &k| m | 1u128 << k);
    }
    out
}

fn graph(p: &Instance, arcs: &[Path]) -> Graph {
    let mut pos = vec![None; p.x.len()];
    for (k, &i) in p.i.iter().enumerate() {
        pos[i] = Some(k);
    }
    let a = arcs
        .iter()
        .map(|a| Arc {
            i: a.i,
            j: a.j,
            l: a.l,
            a: a.a,
            w: a.w,
            direct: a.direct(),
        })
        .collect();
    Graph::new(p.x.len(), p.o, pos, p.b.clone(), p.cap, p.q, a, ng(p, 8))
}

/// One out-and-back route per customer: the least l1 + l2 over P_0i x P_i0 whose charge on
/// arrival at i covers the first leg home.
fn initial(p: &Instance, arcs: &[Path]) -> Vec<Col> {
    let mut cols = Vec::new();
    for &i in &p.i {
        let go = arcs.iter().filter(|a| a.i == p.o && a.j == i);
        let best = go
            .flat_map(|a| {
                arcs.iter()
                    .filter(move |z| z.i == i && z.j == p.o && p.q - a.w >= z.a - 1e-9)
                    .map(move |z| (a, z))
            })
            .min_by(|x, y| (x.0.l + x.1.l).total_cmp(&(y.0.l + y.1.l)));
        if let Some((a, z)) = best {
            cols.push(Col {
                cost: a.l + z.l,
                visits: vec![i],
                nodes: [&a.nodes[..], &z.nodes[1..]].concat(),
            });
        }
    }
    cols
}

/// beta_S(r): arcs of 0, visits, 0 entering S.
fn beta(p: &Instance, s: &BTreeSet<usize>, c: &Col) -> f64 {
    let q: Vec<usize> = std::iter::once(p.o)
        .chain(c.visits.iter().copied())
        .chain(std::iter::once(p.o))
        .collect();
    q.windows(2)
        .filter(|e| !s.contains(&e[0]) && s.contains(&e[1]))
        .count() as f64
}

/// The master over cols with cuts (S, kappa): f, pi per node, lam, sigma >= 0; f = inf when
/// HiGHS does not return an optimum (pi and sigma are then zero, which still bound).
fn master(
    p: &Instance,
    cols: &[Col],
    cuts: &[(BTreeSet<usize>, f64)],
    time: f64,
) -> (f64, Vec<f64>, Option<Vec<f64>>, Vec<f64>) {
    let mut m = Lp::default();
    for c in cols {
        m.var(c.cost, 0.0, f64::INFINITY, false);
    }
    let mut rows = vec![Vec::new(); p.i.len()];
    for (r, c) in cols.iter().enumerate() {
        for v in &c.visits {
            rows[p.i.iter().position(|i| i == v).unwrap()].push((r, 1.0));
        }
    }
    for a in rows {
        m.eq(a, 1.0);
    }
    for (s, kappa) in cuts {
        m.ge(
            cols.iter()
                .enumerate()
                .map(|(r, c)| (r, beta(p, s, c)))
                .filter(|e| e.1 != 0.0)
                .collect(),
            *kappa,
        );
    }
    let s = m.solve(time, 0.0);
    let mut pi = vec![0.0; p.x.len()];
    let Some(f) = s.f.filter(|_| s.status == "optimal") else {
        return (f64::INFINITY, pi, None, vec![0.0; cuts.len()]);
    };
    for (k, &i) in p.i.iter().enumerate() {
        pi[i] = s.y[k];
    }
    let sigma = s.y[p.i.len()..].iter().map(|y| y.max(0.0)).collect();
    (f, pi, s.x, sigma)
}

/// Violated (R2.3) by greedy growth (Lysgaard, Letchford and Eglese 2004, §4): from each seed, S
/// grows by the customer with the largest flow to and from S; each S met is tested against the
/// flow entering it. Up to add new cuts, most violated first. O(n^3).
fn separate(
    p: &Instance,
    cols: &[Col],
    lam: &[f64],
    old: &[(BTreeSet<usize>, f64)],
    add: usize,
) -> Vec<(BTreeSet<usize>, f64)> {
    let tol = 1e-6;
    let nn = p.x.len();
    let mut x = vec![vec![0.0; nn]; nn];
    for (c, &l) in cols.iter().zip(lam) {
        if l > tol {
            let q: Vec<usize> = std::iter::once(p.o)
                .chain(c.visits.iter().copied())
                .chain(std::iter::once(p.o))
                .collect();
            for e in q.windows(2) {
                x[e[0]][e[1]] += l;
            }
        }
    }
    let known: HashSet<&BTreeSet<usize>> = old.iter().map(|c| &c.0).collect();
    let mut found: Vec<(BTreeSet<usize>, f64, f64)> = Vec::new();
    for &seed in &p.i {
        let mut s = vec![seed];
        while s.len() < p.i.len() {
            let rest = p.i.iter().copied().filter(|j| !s.contains(j));
            let w = |j: usize| s.iter().map(|&a| x[a][j] + x[j][a]).sum::<f64>();
            let next = rest.fold(None, |b: Option<(usize, f64)>, j| {
                if b.is_none_or(|b| w(j) > b.1) {
                    Some((j, w(j)))
                } else {
                    b
                }
            });
            s.push(next.unwrap().0);
            let set: BTreeSet<usize> = s.iter().copied().collect();
            let k = (s.iter().map(|&i| p.b[i]).sum::<f64>() / p.cap - tol).ceil();
            let into: f64 = (0..nn)
                .filter(|u| !set.contains(u))
                .map(|u| s.iter().map(|&v| x[u][v]).sum::<f64>())
                .sum();
            if k - into > tol && !known.contains(&set) && !found.iter().any(|f| f.0 == set) {
                found.push((set, k - into, k));
            }
        }
    }
    found.sort_by(|a, b| b.1.total_cmp(&a.1));
    found
        .into_iter()
        .take(add)
        .map(|(s, _, k)| (s, k))
        .collect()
}

/// Set partitioning over the elementary columns: (U, routes, replay ok) if an incumbent replays.
fn restricted(
    p: &Instance,
    cols: &[Col],
    time: f64,
) -> (
    Option<f64>,
    Option<Vec<Vec<usize>>>,
    Option<serde_json::Value>,
) {
    let e: Vec<&Col> = cols
        .iter()
        .filter(|c| c.visits.iter().collect::<BTreeSet<_>>().len() == c.visits.len())
        .collect();
    let mut m = Lp::default();
    for c in &e {
        m.var(c.cost, 0.0, 1.0, true);
    }
    for &i in &p.i {
        m.eq(
            e.iter()
                .enumerate()
                .filter(|(_, c)| c.visits.contains(&i))
                .map(|(r, _)| (r, 1.0))
                .collect(),
            1.0,
        );
    }
    let Some(x) = m.solve(time, 1e-9).x else {
        return (None, None, None);
    };
    let routes: Vec<Vec<usize>> = e
        .iter()
        .zip(&x)
        .filter(|(_, v)| **v > 0.5)
        .map(|(c, _)| c.nodes.iter().map(|k| k + 1).collect())
        .collect();
    let rp = replay(p, &routes, true);
    (
        rp.ok.then_some(rp.length),
        Some(routes),
        Some(json!({"ok": rp.ok, "defects": rp.defects})),
    )
}

/// R2 within time seconds, seeded with the replayed routes init (1-based).
pub fn r2(p: &Instance, init: &[Vec<usize>], time: f64) -> Record {
    let (eps, add, labels, price_time, max_iter) = (1e-6, 20, 10, 600.0_f64, 1000);
    let t0 = Instant::now();
    let milp_time = (0.1 * time).min(300.0);
    let left = || (time - milp_time - t0.elapsed().as_secs_f64()).max(0.0);
    let arcs = paths(p);
    let g = graph(p, &arcs);
    let n = p.i.len() as f64;
    let mut cols = initial(p, &arcs);
    for r in init {
        let v: Vec<usize> = r.iter().map(|k| k - 1).collect();
        let cost = v.windows(2).map(|e| p.d[e[0]][e[1]]).sum();
        cols.push(Col {
            cost,
            visits: v.iter().copied().filter(|k| p.i.contains(k)).collect(),
            nodes: v,
        });
    }
    let mut keys: HashSet<Vec<usize>> = cols.iter().map(|c| c.nodes.clone()).collect();
    let (mut l, mut f, mut cuts) = (f64::NEG_INFINITY, f64::INFINITY, Vec::new());
    let (mut traj, mut calls, mut exact_calls, mut converged) = (Vec::new(), 0, 0, false);
    for k in 1..=max_iter {
        if left() <= 0.0 {
            break;
        }
        let (fk, pi, lam, sigma) = master(p, &cols, &cuts, left().max(1e-3));
        f = fk;
        let w: Option<Vec<f64>> = (!cuts.is_empty()).then(|| {
            let nn = p.x.len();
            let mut w = vec![0.0; nn * nn];
            for ((s, _), sg) in cuts.iter().zip(&sigma) {
                for u in (0..nn).filter(|u| !s.contains(u)) {
                    for &v in s {
                        w[u * nn + v] += sg;
                    }
                }
            }
            w
        });
        let col = |c: &efo_kernels::price::Column| {
            let a: Vec<&Path> = c.arcs.iter().map(|&e| &arcs[e]).collect();
            Col {
                cost: a.iter().map(|a| a.l).sum(),
                visits: a[..a.len() - 1].iter().map(|a| a.j).collect(),
                nodes: std::iter::once(p.o)
                    .chain(a.iter().flat_map(|a| a.nodes[1..].iter().copied()))
                    .collect(),
            }
        };
        let fresh = |r: &efo_kernels::price::Priced, keys: &HashSet<Vec<usize>>| {
            r.cols
                .iter()
                .map(col)
                .filter(|c| !keys.contains(&c.nodes))
                .collect::<Vec<_>>()
        };
        let heur = g.price(&pi, w.as_deref(), Some(labels), left(), 1e-9, 0.0, 1000);
        calls += 1;
        let mut new = fresh(&heur, &keys);
        let mut exact = false;
        if new.is_empty() && left() > 0.0 {
            let r = g.price(
                &pi,
                w.as_deref(),
                None,
                price_time.min(left()),
                1e-9,
                0.0,
                1000,
            );
            (calls, exact_calls, exact) = (calls + 1, exact_calls + 1, r.exact);
            if exact {
                let kappa: f64 = cuts.iter().zip(&sigma).map(|((_, k), s)| k * s).sum();
                l = l.max(p.i.iter().map(|&i| pi[i]).sum::<f64>() + kappa + n * r.best.min(0.0)); // (R2.4)
            }
            new = fresh(&r, &keys);
        }
        let quiet = new.is_empty();
        for c in new.into_iter().take(add) {
            keys.insert(c.nodes.clone());
            cols.push(c);
        }
        let gk = if l.is_finite() {
            (f - l) / (1.0 + f.abs())
        } else {
            f64::INFINITY
        };
        let cut = match &lam {
            Some(lam) if exact && quiet && gk <= eps => {
                separate(p, &cols[..lam.len()], lam, &cuts, 10)
            }
            _ => Vec::new(),
        };
        traj.push(json!({"k": k, "f": f, "L": l.is_finite().then_some(l), "cols": cols.len(), "exact": exact,
            "cuts": cuts.len() + cut.len(), "t": t0.elapsed().as_secs_f64()}));
        let done = exact && quiet && gk <= eps && cut.is_empty();
        cuts.extend(cut);
        if done {
            converged = true;
            break;
        }
    }
    let rest = time - t0.elapsed().as_secs_f64();
    let (u, routes, rp) = if rest > 0.0 {
        restricted(p, &cols, rest)
    } else {
        (None, None, None)
    };
    let l = l.is_finite().then_some(l);
    let status = match gap(u, l) {
        Gap::Closed => "optimal",
        Gap::Crossed => "numerical",
        Gap::Open if u.is_some() => "feasible_limit",
        Gap::Open => "no_incumbent",
    };
    let elapsed = t0.elapsed().as_secs_f64();
    record(
        "R2",
        &p.name,
        Outcome {
            solver_status: status,
            u,
            l,
            replayed: rp.as_ref().map(|r| r["ok"] == true),
            objective: None,
            bound_source: "r24_exact_pricing",
            message: if converged {
                "converged".into()
            } else {
                "limit".into()
            },
            elapsed,
            detail: json!({"formulation": FORMULATION, "time_limit": time, "milp_time": milp_time, "seeds": init.len(),
            "converged": converged, "lp": f.is_finite().then_some(f), "iterations": traj.len(), "pricing": calls,
            "exact_pricing": exact_calls, "columns": cols.len(),
            "cuts": cuts.iter().map(|(s, k)| json!({"S": s.iter().map(|i| i + 1).collect::<Vec<_>>(), "kappa": k})).collect::<Vec<_>>(),
            "routes": routes, "replay": rp, "trajectory": traj}),
        },
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::evrp::enumerate::{enumerate, permutations, route};
    use crate::evrp::fixture;

    #[test]
    fn exact_pricing_equals_brute_force() {
        // ng-sets of 8 hold every customer of a fixture, so ng-routes are elementary routes and
        // cbar* is the least l(route) - pi(route) over capacity-feasible customer sequences.
        for name in ["tiny.evrp", "rand1.evrp", "rand2.evrp"] {
            let p = fixture(name);
            let g = graph(&p, &paths(&p));
            let mut pi = vec![0.0; p.x.len()];
            for (k, &i) in p.i.iter().enumerate() {
                pi[i] = 2.0 * p.d[p.o][i] + 7.0 * k as f64;
            }
            let r = g.price(&pi, None, None, 60.0, 1e-9, 0.0, 1000);
            let mut brute = f64::INFINITY;
            for mask in 1..1usize << p.i.len() {
                let s: Vec<usize> = (0..p.i.len())
                    .filter(|k| mask >> k & 1 == 1)
                    .map(|k| p.i[k])
                    .collect();
                if s.iter().map(|&i| p.b[i]).sum::<f64>() <= p.cap {
                    for q in permutations(&s) {
                        brute = brute.min(route(&p, &q).0 - q.iter().map(|&i| pi[i]).sum::<f64>());
                    }
                }
            }
            assert!(
                r.exact && (r.best - brute).abs() < 1e-6,
                "{name}: {} vs {brute}",
                r.best
            );
        }
    }

    #[test]
    fn more_than_128_customers_is_an_error() {
        assert!(fits(128).is_ok());
        assert!(fits(129).is_err());
    }

    #[test]
    fn r2_bounds_the_fixtures() {
        for name in [
            "tiny.evrp",
            "rand0.evrp",
            "rand1.evrp",
            "rand2.evrp",
            "rand3.evrp",
        ] {
            let p = fixture(name);
            let z = enumerate(&p).0;
            let r = r2(&p, &[], 120.0);
            let (u, l) = (r.u.unwrap(), r.l.unwrap());
            assert!(r.detail["converged"] == true, "{name}");
            assert!(l <= z + 1e-6 && u >= z - 1e-6, "{name}: {l} {z} {u}");
            assert_eq!(r.certified, u - l <= crate::cert::tol(u), "{name}");
        }
    }
}
