//! R3: partial recharging with resistive loss, a convex MINLP (Routing §5), by outer
//! approximation.
//!
//! Arcs are direct (i, -, j) or through one station (i, f, j), sources {0} ∪ I, sinks I ∪ {0'}.
//! With x binary per arc, u load, y charge on arrival and t time of arrival at each customer, and
//! per station arc the energy charged q, dwell tau and grid energy g:
//!
//! ```text
//! min  c_d sum l x + c_e sum g + c_tau sum tau
//! degree rows, the capacity bound and lifted MTZ rows as in R1 (R1.2)-(R1.3);
//! y_i >= sum_{out of i} a x   (a = e_ij direct, e_if via a station)          (R1.4)
//! y_j = y_i - e_ij  on a used direct arc                       (two big-M rows)
//! y_j = y_i + q - e_if - e_fj  on a used station arc,  y_i - e_if x + q <= Q   (R3.1)
//! 0 <= q <= Q x,  q <= P tau,  tau_min x <= tau <= T x                        (R3.2)
//! g >= q/eta + alpha q^2 / tau   (closed perspective; convex)                 (R3.3)
//! t_j >= t_i + sigma + travel (+ tau) - M (1 - x),  every route back by T.
//! ```
//!
//! R1 needs only the upper side of the charge rows since it always charges to full; with partial
//! charges y must be the true charge. At most one station lies between consecutive customers, a
//! restriction: R3's optimum is an upper bound on the unrestricted model. The least dwell tau_min
//! keeps (R3.3) smooth for the barrier method; the tangent cuts (R3.4) at power r = q/tau,
//! (1/eta + 2 alpha r) q - alpha r^2 tau - g <= 0, hold down to tau = 0.

use super::Instance;
use super::replay::replay_charge;
use crate::barrier::{self, Rows};
use crate::cert::{Outcome, Record, record};
use crate::lp::Lp;
use crate::oa::{Cut, oa};
use crate::scenario::Recharge;
use efo_kernels::ipm::Trip;
use serde_json::json;
use std::collections::BTreeMap;
use std::time::Instant;

pub const FORMULATION: &str = "R3/1";

/// The R3 program: arcs (i, station, j), the station arcs s, and the first columns of u, y, t,
/// q, tau, g (x is 0..arcs).
struct Model {
    lp: Lp,
    arcs: Vec<(usize, Option<usize>, usize)>,
    s: Vec<usize>,
    q: usize,
    tau: usize,
    g: usize,
}

fn rows(p: &Instance, sc: &Recharge) -> Model {
    let (o, n, h, big_q) = (p.o, p.i.len(), p.h, p.q);
    let (v, sig, t_max, tmin, pw) = (
        sc.time.speed,
        sc.time.service,
        sc.time.t,
        sc.time.tau_min,
        sc.charger.p,
    );
    let reach = |a: usize, b: usize| h * p.d[a][b] <= big_q + 1e-9;
    let mut arcs = Vec::new();
    for i in std::iter::once(o).chain(p.i.iter().copied()) {
        for j in p.i.iter().copied().chain(std::iter::once(o)) {
            if i == j {
                continue;
            }
            if reach(i, j) {
                arcs.push((i, None, j));
            }
            arcs.extend(
                p.f.iter()
                    .filter(|&&f| reach(i, f) && reach(f, j))
                    .map(|&f| (i, Some(f), j)),
            );
        }
    }
    let s: Vec<usize> = (0..arcs.len()).filter(|&k| arcs[k].1.is_some()).collect();
    let at: BTreeMap<usize, usize> = s.iter().enumerate().map(|(k, &a)| (a, k)).collect();
    let ci: BTreeMap<usize, usize> = p.i.iter().enumerate().map(|(k, &i)| (i, k)).collect();
    let length = |a: &(usize, Option<usize>, usize)| match a.1 {
        None => p.d[a.0][a.2],
        Some(f) => p.d[a.0][f] + p.d[f][a.2],
    };
    let mut m = Lp::default();
    for a in &arcs {
        m.var(sc.cost.distance * length(a), 0.0, 1.0, true);
    }
    let u = m.n();
    for &i in &p.i {
        m.var(0.0, p.b[i], p.cap, false);
    }
    let y = m.vars(n, 0.0, 0.0, big_q, false);
    let tt = m.vars(n, 0.0, 0.0, t_max, false);
    let q = m.vars(s.len(), 0.0, 0.0, big_q, false);
    let tau = m.vars(s.len(), sc.cost.dwell, 0.0, t_max, false);
    let gmax = big_q / sc.charger.eta + sc.charger.alpha * big_q * big_q / tmin; // most a visit draws
    let g = m.vars(s.len(), sc.cost.energy, 0.0, gmax, false);
    let (mut out, mut inn, mut pair) = (
        BTreeMap::<usize, Vec<usize>>::new(),
        BTreeMap::<usize, Vec<usize>>::new(),
        BTreeMap::<(usize, usize), Vec<usize>>::new(),
    );
    for (k, &(i, _, j)) in arcs.iter().enumerate() {
        out.entry(i).or_default().push(k);
        inn.entry(j).or_default().push(k);
        pair.entry((i, j)).or_default().push(k);
    }
    let ones = |ks: Option<&Vec<usize>>| {
        ks.into_iter()
            .flatten()
            .map(|&k| (k, 1.0))
            .collect::<Vec<_>>()
    };
    for &i in &p.i {
        m.eq(ones(out.get(&i)), 1.0);
        m.eq(ones(inn.get(&i)), 1.0);
    }
    m.ge(
        ones(out.get(&o)),
        (p.i.iter().map(|&i| p.b[i]).sum::<f64>() / p.cap - 1e-9).ceil(),
    );
    for &i in &p.i {
        for &j in &p.i {
            if i != j {
                let mut a = vec![(u + ci[&j], 1.0), (u + ci[&i], -1.0)];
                a.extend(
                    pair.get(&(i, j))
                        .into_iter()
                        .flatten()
                        .map(|&k| (k, -p.cap)),
                );
                a.extend(
                    pair.get(&(j, i))
                        .into_iter()
                        .flatten()
                        .map(|&k| (k, -(p.cap - p.b[i] - p.b[j]))),
                );
                m.ge(a, p.b[j] - p.cap);
            }
        }
    }
    let first = |a: &(usize, Option<usize>, usize)| h * p.d[a.0][a.1.unwrap_or(a.2)];
    for &i in &p.i {
        let mut a = vec![(y + ci[&i], 1.0)]; // (R1.4)
        a.extend(
            out.get(&i)
                .into_iter()
                .flatten()
                .map(|&k| (k, -first(&arcs[k]))),
        );
        m.ge(a, 0.0);
    }
    for (k, &(i, f, j)) in arcs.iter().enumerate() {
        let tr = length(&arcs[k]) / v;
        match f {
            None => {
                let e = h * p.d[i][j];
                if i != o && j != o {
                    m.le(
                        vec![(y + ci[&j], 1.0), (y + ci[&i], -1.0), (k, e + big_q)],
                        big_q,
                    );
                    m.ge(
                        vec![(y + ci[&j], 1.0), (y + ci[&i], -1.0), (k, e - big_q)],
                        -big_q,
                    );
                } else if i == o {
                    m.le(vec![(y + ci[&j], 1.0), (k, e)], big_q);
                    m.ge(vec![(y + ci[&j], 1.0), (k, -(big_q - e))], 0.0);
                }
            }
            Some(f) => {
                let (sk, e1, e2) = (at[&k], h * p.d[i][f], h * p.d[f][j]);
                let yi: Vec<(usize, f64)> = if i != o {
                    vec![(y + ci[&i], -1.0)]
                } else {
                    Vec::new()
                };
                let qi = if i != o { 0.0 } else { big_q }; // the depot sends Q
                let neg = |v: &[(usize, f64)]| v.iter().map(|&(c, a)| (c, -a)).collect::<Vec<_>>();
                if j != o {
                    // (R3.1) and its lower side
                    let mut a = vec![(y + ci[&j], 1.0), (q + sk, -1.0), (k, e1 + e2 + big_q)];
                    a.extend(&yi);
                    m.le(a, big_q + qi);
                    let mut a = vec![(y + ci[&j], 1.0), (q + sk, -1.0), (k, e1 + e2 - big_q - qi)];
                    a.extend(&yi);
                    m.ge(a, -big_q);
                } else {
                    let mut a = vec![(q + sk, 1.0), (k, -(e1 + e2 + big_q))];
                    a.extend(neg(&yi));
                    m.ge(a, -big_q - qi);
                }
                let mut a = vec![(q + sk, 1.0), (k, -e1)];
                a.extend(neg(&yi));
                m.le(a, big_q - qi);
                m.le(vec![(q + sk, 1.0), (k, -big_q)], 0.0); // (R3.2)
                m.le(vec![(q + sk, 1.0), (tau + sk, -pw)], 0.0);
                m.le(vec![(tau + sk, 1.0), (k, -t_max)], 0.0);
                m.ge(vec![(tau + sk, 1.0), (k, -tmin)], 0.0);
            }
        }
        let dw: Vec<usize> = f.map(|_| tau + at[&k]).into_iter().collect();
        let big = 2.0 * t_max + sig + tr;
        if i != o && j != o {
            let mut a = vec![(tt + ci[&j], 1.0), (tt + ci[&i], -1.0), (k, -big)];
            a.extend(dw.iter().map(|&c| (c, -1.0)));
            m.ge(a, sig + tr - big);
        } else if j != o {
            let mut a = vec![(tt + ci[&j], 1.0), (k, -big)];
            a.extend(dw.iter().map(|&c| (c, -1.0)));
            m.ge(a, tr - big);
        } else if i != o {
            let mut a = vec![(tt + ci[&i], 1.0), (k, big)];
            a.extend(dw.iter().map(|&c| (c, 1.0)));
            m.le(a, t_max + big - sig - tr);
        }
    }
    Model {
        lp: m,
        arcs,
        s,
        q,
        tau,
        g,
    }
}

/// (R3.3) on (q, tau, g) of one station arc, with its closure at tau = 0 (then q = 0).
struct Loss {
    idx: [usize; 3],
    eta: f64,
    alpha: f64,
}

impl Cut for Loss {
    fn idx(&self) -> &[usize] {
        &self.idx
    }

    fn f(&self, z: &[f64]) -> f64 {
        z[0] / self.eta
            + if z[1] > 1e-12 {
                self.alpha * z[0] * z[0] / z[1]
            } else {
                0.0
            }
            - z[2]
    }

    fn grad(&self, z: &[f64]) -> Vec<f64> {
        let r = if z[1] > 1e-12 { z[0] / z[1] } else { 0.0 }; // (R3.4) at power r
        vec![
            1.0 / self.eta + 2.0 * self.alpha * r,
            -self.alpha * r * r,
            -1.0,
        ]
    }
}

/// (R3.3) on the used station arcs, for the barrier method.
struct Losses {
    on: Vec<[usize; 3]>,
    eta: f64,
    alpha: f64,
}

impl Rows for Losses {
    fn h(&self, x: &[f64]) -> Vec<f64> {
        self.on
            .iter()
            .map(|&[q, t, g]| x[q] / self.eta + self.alpha * x[q] * x[q] / x[t] - x[g])
            .collect()
    }

    fn jac(&self, x: &[f64]) -> Trip {
        let mut j = Trip::default();
        for (k, &[q, t, g]) in self.on.iter().enumerate() {
            let r = x[q] / x[t];
            j.r.extend([k, k, k]);
            j.c.extend([q, t, g]);
            j.v.extend([
                1.0 / self.eta + 2.0 * self.alpha * r,
                -self.alpha * r * r,
                -1.0,
            ]);
        }
        j
    }

    /// alpha q^2 / tau: [[2/tau, -2q/tau^2], [-2q/tau^2, 2q^2/tau^3]] times alpha lam.
    fn hess(&self, x: &[f64], lam: &[f64]) -> Trip {
        let mut hh = Trip::default();
        for (k, &[q, t, _]) in self.on.iter().enumerate() {
            let (qv, tv, a) = (x[q], x[t], 2.0 * self.alpha * lam[k]);
            hh.r.extend([q, q, t, t]);
            hh.c.extend([q, t, q, t]);
            hh.v.extend([
                a / tv,
                -a * qv / (tv * tv),
                -a * qv / (tv * tv),
                a * qv * qv / (tv * tv * tv),
            ]);
        }
        hh
    }
}

type Charges = BTreeMap<(usize, usize), (f64, f64)>;

/// Routes (1-based, stations included) and charges (route, position) -> (q, tau) of x.
fn routes(p: &Instance, m: &Model, x: &[f64]) -> (Vec<Vec<usize>>, Charges) {
    let at: BTreeMap<usize, usize> = m.s.iter().enumerate().map(|(k, &a)| (a, k)).collect();
    let used = |k: usize| x[k] > 0.5;
    let succ: BTreeMap<usize, usize> = (0..m.arcs.len())
        .filter(|&k| used(k) && m.arcs[k].0 != p.o)
        .map(|k| (m.arcs[k].0, k))
        .collect();
    let (mut out, mut charges) = (Vec::new(), Charges::new());
    for k0 in (0..m.arcs.len()).filter(|&k| used(k) && m.arcs[k].0 == p.o) {
        let (mut r, mut k) = (vec![p.o], k0);
        for _ in 0..m.arcs.len() {
            let (_, f, j) = m.arcs[k];
            if let Some(f) = f {
                charges.insert((out.len(), r.len()), (x[m.q + at[&k]], x[m.tau + at[&k]]));
                r.push(f);
            }
            r.push(j);
            match succ.get(&j) {
                Some(&next) if j != p.o => k = next,
                _ => break,
            }
        }
        out.push(r.iter().map(|v| v + 1).collect());
    }
    (out, charges)
}

/// R3 by outer approximation within time seconds; U is the cost of the routes replayed with
/// their partial charges, L the master's dual bound.
pub fn r3(p: &Instance, sc: &Recharge, max_iter: usize, time: f64) -> Record {
    let t0 = Instant::now();
    let m = rows(p, sc);
    let (eta, alpha, pw) = (sc.charger.eta, sc.charger.alpha, sc.charger.p);
    let cuts: Vec<Box<dyn Cut>> = (0..m.s.len())
        .map(|k| {
            Box::new(Loss {
                idx: [m.q + k, m.tau + k, m.g + k],
                eta,
                alpha,
            }) as Box<dyn Cut>
        })
        .collect();
    let points: Vec<Vec<f64>> = [0.0, pw / 2.0, pw]
        .iter()
        .map(|&rate| {
            let mut z = vec![0.0; m.lp.n()];
            for k in 0..m.s.len() {
                (z[m.tau + k], z[m.q + k]) = (1.0, rate);
            }
            z
        })
        .collect();
    let sub = |x: &[f64]| {
        let mut f = m.lp.clone();
        let mut on = Vec::new();
        for k in 0..m.arcs.len() {
            let v = x[k].round();
            (f.l[k], f.u[k]) = (v, v);
        }
        for (k, &a) in m.s.iter().enumerate() {
            if x[a].round() == 0.0 {
                for c in [m.q + k, m.tau + k, m.g + k] {
                    f.u[c] = 0.0;
                }
            } else {
                on.push([m.q + k, m.tau + k, m.g + k]);
            }
        }
        let h = Losses { on, eta, alpha };
        let b = barrier::solve(
            &f,
            (!h.on.is_empty()).then_some(&h as &dyn Rows),
            f64::INFINITY,
        );
        (b.status, b.x.filter(|_| b.status == "optimal"))
    };
    let replay = |w: &[f64]| {
        let (r, c) = routes(p, &m, w);
        let rp = replay_charge(p, sc, &r, &c);
        rp.ok.then_some(rp.cost)
    };
    let r = oa(&m.lp, &cuts, &points, sub, replay, max_iter, time, 600.0);
    let (rt, ch) = r.x.as_ref().map(|x| routes(p, &m, x)).unzip();
    let length = rt
        .as_ref()
        .zip(ch.as_ref())
        .map(|(r, c)| replay_charge(p, sc, r, c).length);
    record(
        "R3",
        &p.name,
        Outcome {
            solver_status: r.status,
            u: r.u,
            l: r.l,
            replayed: None,
            objective: None,
            bound_source: "oa_master_dual",
            message: format!("outer approximation, {} iterations", r.iterations.len()),
            elapsed: t0.elapsed().as_secs_f64(),
            detail: json!({"formulation": FORMULATION, "time_limit": time, "max_iter": max_iter, "alpha": alpha, "arcs": m.arcs.len(),
            "cuts": r.cuts, "iterations": r.iterations, "routes": rt, "length": length,
            "charges": ch.map(|c| c.iter().map(|(k, v)| (format!("{}:{}", k.0, k.1), *v)).collect::<BTreeMap<_, _>>())}),
        },
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::evrp::{fixture, r1::r1};
    use crate::scenario::{data, recharge};

    /// Charging costs nothing and takes almost no time: R3 is R1 restricted to one station
    /// between customers.
    fn free() -> Recharge {
        let mut s = recharge(&data("r3.toml")).unwrap();
        (s.charger.alpha, s.charger.p) = (0.0, 1e4);
        (s.cost.energy, s.cost.dwell) = (0.0, 0.0);
        (s.time.t, s.time.tau_min, s.time.service) = (100.0, 1e-3, 0.0);
        s
    }

    #[test]
    fn free_charging_is_r1_with_one_station() {
        for name in ["tiny.evrp", "rand1.evrp"] {
            let p = fixture(name);
            let (a, b) = (r3(&p, &free(), 40, 120.0), r1(&p, 60.0, 1e-7));
            assert!(
                a.certified && b.certified,
                "{name}: {} {}",
                a.status,
                b.status
            );
            assert!(a.u.unwrap() >= b.u.unwrap() - 1e-6);
            let f: Vec<usize> = p.f.iter().map(|k| k + 1).collect();
            let routes: Vec<Vec<usize>> =
                serde_json::from_value(b.detail["routes"].clone()).unwrap();
            if routes.iter().all(|r| {
                r.windows(2)
                    .all(|e| !(f.contains(&e[0]) && f.contains(&e[1])))
            }) {
                assert!((a.u.unwrap() - b.u.unwrap()).abs() < 1e-5, "{name}");
            }
        }
    }

    #[test]
    fn the_declared_scenario_replays() {
        let p = fixture("tiny.evrp");
        let r = r3(&p, &recharge(&data("r3.toml")).unwrap(), 40, 120.0);
        assert!(r.certified, "{}", r.status);
        assert!(r.detail["length"].as_f64().unwrap() <= r.u.unwrap());
    }
}
