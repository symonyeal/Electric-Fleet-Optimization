//! M1, joint scheduling and charging in connection form (Models §3), and M2, its convex MINLP
//! with charging loss and taper (Models §5), by outer approximation.
//!
//! Trips j = 1..n with published times; x_ij = 1 when trip j is the next trip after i on a bus,
//! x_0j a pull-out from the depot, x_i0 a pull-in. Energy (kWh): a_j on arrival at j's first
//! stop, y_j on departing it, E_j the trip, e_ij the deadhead. A bus may charge at j's first stop,
//! when it is a charging site s(j), in the window of slots t before dep_j, with battery-side
//! power p_jt on a plug u_jt; the slot must lie wholly after the predecessor's arrival.
//!
//! ```text
//! min  F sum x_0j + c_dh (deadhead km) + sum_s ((f + rho c_b) o_s + a n_s + b h_s + rho pi D_s)
//!      + rho c_e (Delta/eta) sum p_jt + rho (c_dep/eta) sum_i r_i
//! sum_i x_ij + x_0j = 1,  sum_j x_ij + x_i0 = 1                            (2), (3)
//! a_j = y_i - E_i - e_ij  if x_ij = 1;   a_j = s0 B - e_0j  if x_0j = 1     (7), two-sided big-M
//! y_j = a_j + Delta sum_t p_jt,   rB <= a_j,   rB + E_j <= y_j <= smax B    (7), (8)
//! p_jt <= P u_jt,   u_jt <= x_0j + sum_{i present at t} x_ij                (4)
//! sum_j u_jt <= n_s <= nbar o_s,   h_s <= hbar o_s                          (5)
//! L_s o_s + sum_j p_jt / eta <= G0_s + h_s,   D_s >= L_s o_s + sum_j p_jt / eta    (6)
//!   (D_s over the slots of the billing window only, Data §3; once per site without charging)
//! y_i - E_i - e_i0 >= rB  if x_i0 = 1;   r_i >= s0 B - (y_i - E_i - e_i0)  if x_i0 = 1,  r_i >= 0
//! ```
//!
//! with rho = 1 + rider and c_b the basic charge per metered site. r_i is the energy the depot
//! restores overnight to bring bus i back to s0 B, priced at the depot rate; the recovery itself
//! is not modeled, so no schedule is claimed to repeat day after day (Models §4). The whole trip's
//! energy is taken at its start, which enforces the reserve conservatively (Models §1).
//!
//! M2 replaces p/eta by grid power g_jt in [0, gbar u_jt] in the grid, peak and energy terms,
//! adds the taper (11) p_jt <= P (1 - e_j,t+1 / B), e_j,t+1 = a_j + Delta sum_{t' <= t} p_jt', and
//! the convex loss (10) g_jt >= p_jt/eta + alpha p_jt^2, which outer approximation treats.

use super::replay::{Infra, Plan, replay_energy};
use super::{Corridor, Instance, compile};
use crate::barrier::{self, Rows};
use crate::cert::{Outcome, Record, record};
use crate::lp::Lp;
use crate::oa::{Cut, oa};
use crate::scenario::{Transit, billed};
use efo_kernels::ipm::Trip;
use serde_json::json;
use std::collections::BTreeMap;
use std::time::Instant;

pub const M1: &str = "M1/2";
pub const M2: &str = "M2/2";

/// The program and the first column of each block; slots k = (j, t), sites in scenario order.
pub struct Model<'a> {
    pub m: Instance<'a>,
    pub lp: Lp,
    pub slots: Vec<(usize, i64)>,
    pub sites: Vec<String>,
    pub x0: usize,
    pub x1: usize,
    pub xc: usize,
    pub r: usize,
    pub p: usize,
    pub u: usize,
    pub g: Option<usize>,
    pub o: usize,
    pub nn: usize,
    pub hh: usize,
}

/// M1 (loss false) or the linear rows of M2 (loss true); fixed sets the plugs and upgrade of
/// sites that must open.
pub fn rows<'a>(c: &'a Corridor, v: &'a Transit, fixed: &Infra, loss: bool) -> Model<'a> {
    let m = compile(c, v);
    let n = c.trips.len();
    let (co, ch) = (&v.cost, &v.charger);
    let (rho, w0, w1) = co.tariff();
    let (eta, pm, dt, h) = (ch.eta, ch.p, v.time.delta, v.time.delta / 3600.0);
    let gbar = pm / eta + ch.alpha * pm * pm;
    let slots: Vec<(usize, i64)> = m
        .win
        .iter()
        .flat_map(|(&j, w)| w.iter().map(move |&t| (j, t)))
        .collect();
    let sites: Vec<String> = v.sites.keys().cloned().collect();
    let ns = slots.len();
    let mut lp = Lp::default();
    let x0 = lp.n();
    for j in 0..n {
        lp.var(co.f + co.deadhead * m.km0[j], 0.0, 1.0, true);
    }
    let x1 = lp.n();
    for i in 0..n {
        lp.var(co.deadhead * m.km1[i], 0.0, 1.0, true);
    }
    let xc = lp.n();
    for k in 0..m.arcs.len() {
        lp.var(co.deadhead * m.km[k], 0.0, 1.0, true);
    }
    let a = lp.vars(n, 0.0, m.rb, m.top, false);
    let y = lp.n();
    for j in 0..n {
        lp.var(0.0, m.rb + m.e[j], m.top, false);
    }
    let r = lp.vars(n, rho * co.depot_energy / eta, 0.0, m.s0b - m.rb, false);
    let p = lp.vars(
        ns,
        if loss { 0.0 } else { rho * co.energy * h / eta },
        0.0,
        pm,
        false,
    );
    let u = lp.vars(ns, 0.0, 0.0, 1.0, true);
    let g = loss.then(|| lp.vars(ns, rho * co.energy * h, 0.0, gbar, false));
    let (o, nn, hh, dd) = (
        lp.n(),
        lp.n() + sites.len(),
        lp.n() + 2 * sites.len(),
        lp.n() + 3 * sites.len(),
    );
    for s in &sites {
        let lo = if fixed.contains_key(s) { 1.0 } else { 0.0 };
        lp.var(co.site + rho * co.basic, lo, 1.0, true);
    }
    for s in &sites {
        let (lo, hi) = fixed.get(s).map_or((0.0, v.sites[s].nbar), |f| (f.0, f.0));
        lp.var(co.plug, lo, hi, true);
    }
    for s in &sites {
        let (lo, hi) = fixed.get(s).map_or((0.0, v.sites[s].hbar), |f| (f.1, f.1));
        lp.var(co.upgrade, lo, hi, false);
    }
    lp.vars(sites.len(), rho * co.peak, 0.0, f64::INFINITY, false);
    let (mut into, mut outof) = (vec![Vec::new(); n], vec![Vec::new(); n]);
    for (k, &(i, j, _)) in m.arcs.iter().enumerate() {
        into[j].push((xc + k, 1.0));
        outof[i].push((xc + k, 1.0));
    }
    for j in 0..n {
        lp.eq([vec![(x0 + j, 1.0)], into[j].clone()].concat(), 1.0); // (2), (3)
        lp.eq([vec![(x1 + j, 1.0)], outof[j].clone()].concat(), 1.0);
    }
    let kappa = v.battery.kappa;
    for (k, &(i, j, _)) in m.arcs.iter().enumerate() {
        let (e, big) = (kappa * m.km[k], m.top + kappa * m.km[k]); // (7), connections
        lp.le(
            vec![(a + j, 1.0), (y + i, -1.0), (xc + k, big)],
            big - m.e[i] - e,
        );
        lp.ge(
            vec![(a + j, 1.0), (y + i, -1.0), (xc + k, -big)],
            -big - m.e[i] - e,
        );
    }
    for j in 0..n {
        let (e, big) = (kappa * m.km0[j], m.top + kappa * m.km0[j]); // (7), pull-outs
        lp.le(vec![(a + j, 1.0), (x0 + j, big)], big + m.s0b - e);
        lp.ge(vec![(a + j, 1.0), (x0 + j, -big)], -big + m.s0b - e);
    }
    for i in 0..n {
        let (e, big) = (kappa * m.km1[i], m.top + kappa * m.km1[i]); // pull-ins
        lp.ge(vec![(y + i, 1.0), (x1 + i, -big)], m.e[i] + e + m.rb - big);
        let br = m.s0b + e; // r_i + y_i >= s0B + E_i + e_i0
        lp.ge(
            vec![(r + i, 1.0), (y + i, 1.0), (x1 + i, -br)],
            m.s0b + m.e[i] + e - br,
        );
        lp.le(vec![(r + i, 1.0), (x1 + i, -(m.s0b - m.rb))], 0.0);
    }
    let at: BTreeMap<(usize, i64), usize> =
        slots.iter().enumerate().map(|(k, &jt)| (jt, k)).collect();
    for j in 0..n {
        let mut row = vec![(y + j, 1.0), (a + j, -1.0)]; // y_j = a_j + h sum p
        row.extend(
            m.win
                .get(&j)
                .into_iter()
                .flatten()
                .map(|&t| (p + at[&(j, t)], -h)),
        );
        lp.eq(row, 0.0);
    }
    let mut present: BTreeMap<usize, Vec<(f64, usize)>> = BTreeMap::new();
    for (k, &(i, j, tau)) in m.arcs.iter().enumerate() {
        present
            .entry(j)
            .or_default()
            .push((c.trips[i].arr + tau, xc + k));
    }
    let mut by: BTreeMap<(usize, i64), Vec<usize>> = BTreeMap::new();
    for (k, &(j, t)) in slots.iter().enumerate() {
        lp.le(vec![(p + k, 1.0), (u + k, -pm)], 0.0); // (4)
        let mut row = vec![(u + k, 1.0), (x0 + j, -1.0)];
        row.extend(
            present
                .get(&j)
                .into_iter()
                .flatten()
                .filter(|e| e.0 <= t as f64 * dt + 1e-9)
                .map(|e| (e.1, -1.0)),
        );
        lp.le(row, 0.0);
        let s = sites
            .iter()
            .position(|s| *s == m.site[&c.trips[j].first])
            .unwrap();
        by.entry((s, t)).or_default().push(k);
    }
    for (&(q, t), ks) in &by {
        let d = &v.sites[&sites[q]]; // (5), (6) per slot
        let mut row: Vec<(usize, f64)> = ks.iter().map(|&k| (u + k, 1.0)).collect();
        row.push((nn + q, -1.0));
        lp.le(row, 0.0);
        let mut load: Vec<(usize, f64)> = ks
            .iter()
            .map(|&k| g.map_or((p + k, 1.0 / eta), |g| (g + k, 1.0)))
            .collect();
        if d.l != 0.0 {
            load.push((o + q, d.l));
        }
        lp.le([load.clone(), vec![(hh + q, -1.0)]].concat(), d.g0);
        if billed(t as f64 * dt, w0, w1) {
            lp.le([load, vec![(dd + q, -1.0)]].concat(), 0.0);
        }
    }
    for (q, s) in sites.iter().enumerate() {
        let d = &v.sites[s];
        lp.le(vec![(nn + q, 1.0), (o + q, -d.nbar)], 0.0);
        lp.le(vec![(hh + q, 1.0), (o + q, -d.hbar)], 0.0);
        if d.l != 0.0 {
            lp.le(vec![(o + q, d.l), (hh + q, -1.0)], d.g0); // (6) per site
            lp.le(vec![(o + q, d.l), (dd + q, -1.0)], 0.0);
        }
    }
    if let Some(g) = g {
        let bb = v.battery.b;
        for (k, &(j, t)) in slots.iter().enumerate() {
            lp.le(vec![(g + k, 1.0), (u + k, -gbar)], 0.0); // (10) bound, (11)
            let mut row = vec![(p + k, 1.0), (a + j, pm / bb)];
            row.extend(
                m.win[&j]
                    .iter()
                    .filter(|&&s| s <= t)
                    .map(|&s| (p + at[&(j, s)], pm * h / bb)),
            );
            lp.le(row, pm);
        }
    }
    Model {
        m,
        lp,
        slots,
        sites,
        x0,
        x1,
        xc,
        r,
        p,
        u,
        g,
        o,
        nn,
        hh,
    }
}

/// Duties (trip ids), charging plan and opened sites of a solution x.
pub fn solution(md: &Model, x: &[f64]) -> (Vec<Vec<String>>, Plan, Infra) {
    let t = &md.m.c.trips;
    let succ: BTreeMap<usize, usize> =
        md.m.arcs
            .iter()
            .enumerate()
            .filter(|(k, _)| x[md.xc + k] > 0.5)
            .map(|(_, &(i, j, _))| (i, j))
            .collect();
    let duties = (0..t.len())
        .filter(|&j| x[md.x0 + j] > 0.5)
        .map(|j| {
            std::iter::successors(Some(j), |k| succ.get(k).copied())
                .take(t.len())
                .map(|k| t[k].id.clone())
                .collect()
        })
        .collect();
    let mut plan = Plan::new();
    for (k, &(j, s)) in md.slots.iter().enumerate() {
        if x[md.p + k] > 1e-9 {
            plan.entry(t[j].id.clone())
                .or_default()
                .insert(s, x[md.p + k]);
        }
    }
    let infra = md
        .sites
        .iter()
        .enumerate()
        .filter(|(q, _)| x[md.o + q] > 0.5)
        .map(|(q, s)| (s.clone(), (x[md.nn + q].round(), x[md.hh + q])))
        .collect();
    (duties, plan, infra)
}

fn schedule(md: &Model, x: &[f64], loss: bool) -> (serde_json::Value, Option<f64>, bool) {
    let (duties, plan, infra) = solution(md, x);
    let rp = replay_energy(md.m.c, md.m.v, &duties, &plan, &infra, loss);
    let detail = json!({"fleet": duties.len(), "duties": duties, "plan": plan, "infra": infra,
        "replay": {"ok": rp.ok, "defects": rp.defects, "cost": rp.cost, "parts": rp.parts}});
    (detail, rp.ok.then_some(rp.cost), rp.ok)
}

/// The cover start of M1 (Models §4): (the cover's value, a point of md.lp or None).
///
/// The degree rows (2), (3) with the pull-out, pull-in and connection costs alone are the
/// assignment problem of M0 with costs, totally unimodular: an integral optimum is a least-cost
/// cover of the trips by duties on the compatibility DAG, and its value bounds M1 below, since
/// every other term of M1 is nonnegative. With all x fixed at that cover, the rest of md.lp is
/// the charging plan of those duties; its optimum, when one exists, is a point of M1.
pub fn cover(md: &Model, time: f64) -> (Option<f64>, Option<Vec<f64>>) {
    let t0 = Instant::now();
    let (n, k) = (md.m.c.trips.len(), md.xc + md.m.arcs.len());
    let lp = &md.lp;
    let core = Lp {
        c: lp.c[..k].to_vec(),
        l: lp.l[..k].to_vec(),
        u: lp.u[..k].to_vec(),
        int: lp.int[..k].to_vec(),
        rows: lp.rows[..2 * n].to_vec(), // rows() writes the degree rows first
    };
    let s = core.solve(time, 0.0);
    let Some(x) = s.x.filter(|_| s.status == "optimal") else {
        return (None, None);
    };
    let mut fixed = lp.clone();
    for j in 0..k {
        (fixed.l[j], fixed.u[j]) = (x[j].round(), x[j].round());
    }
    let left = (time - t0.elapsed().as_secs_f64()).max(0.0);
    (s.f, fixed.solve(left, 0.0).x)
}

/// M1 by HiGHS within time seconds at relative gap gap, from the cover start when start; U is
/// the replayed cost of the schedule, which must agree with the model's objective.
pub fn m1(
    c: &Corridor,
    v: &Transit,
    name: &str,
    fixed: &Infra,
    time: f64,
    gap: f64,
    start: bool,
) -> Record {
    let t0 = Instant::now();
    let md = rows(c, v, fixed, false);
    let (mut first, mut left, mut x0) = (json!(null), time, None);
    if start {
        let (cv, x) = cover(&md, time);
        first = json!({"cover": cv, "found": x.is_some(), "seconds": t0.elapsed().as_secs_f64()});
        (left, x0) = ((time - t0.elapsed().as_secs_f64()).max(1e-3), x);
    }
    let s = md.lp.solve_from(left, gap, x0.as_deref());
    let (sched, u, ok) = s.x.as_ref().map_or((json!(null), None, None), |x| {
        let (d, u, ok) = schedule(&md, x, false);
        (d, u, Some(ok))
    });
    record(
        "M1",
        name,
        Outcome {
            solver_status: s.status,
            u,
            l: s.bound,
            replayed: ok,
            objective: s.f,
            bound_source: "highs_dual",
            message: format!("HiGHS {}", s.status),
            elapsed: t0.elapsed().as_secs_f64(),
            detail: json!({"formulation": M1, "time_limit": time, "mip_rel_gap": gap, "trips": c.trips.len(),
            "variables": md.lp.n(), "rows": md.lp.rows.len(), "nodes": s.nodes, "schedule": sched,
            "start": first}),
        },
    )
}

/// (10) for one slot on (p, g): p/eta + alpha p^2 - g <= 0.
struct Loss {
    idx: [usize; 2],
    eta: f64,
    alpha: f64,
}

impl Cut for Loss {
    fn idx(&self) -> &[usize] {
        &self.idx
    }

    fn f(&self, z: &[f64]) -> f64 {
        z[0] / self.eta + self.alpha * z[0] * z[0] - z[1]
    }

    fn grad(&self, z: &[f64]) -> Vec<f64> {
        vec![1.0 / self.eta + 2.0 * self.alpha * z[0], -1.0]
    }
}

struct Losses(Vec<Loss>);

impl Rows for Losses {
    fn h(&self, x: &[f64]) -> Vec<f64> {
        self.0
            .iter()
            .map(|l| l.f(&[x[l.idx[0]], x[l.idx[1]]]))
            .collect()
    }

    fn jac(&self, x: &[f64]) -> Trip {
        let mut j = Trip::default();
        for (k, l) in self.0.iter().enumerate() {
            j.r.extend([k, k]);
            j.c.extend(l.idx);
            j.v.extend(l.grad(&[x[l.idx[0]], x[l.idx[1]]]));
        }
        j
    }

    fn hess(&self, _: &[f64], lam: &[f64]) -> Trip {
        let mut h = Trip::default();
        for (k, l) in self.0.iter().enumerate() {
            h.r.push(l.idx[0]);
            h.c.push(l.idx[0]);
            h.v.push(2.0 * l.alpha * lam[k]);
        }
        h
    }
}

/// M2 at the integers of x by the barrier method: every integer fixed at its rounded value,
/// p = g = 0 where u = 0, and r_i = 0 where trip i is not a pull-in, so no barrier acts on a face
/// without interior (Models §5).
pub fn m2_fixed(md: &Model, x: &[f64]) -> barrier::Barrier {
    let mut f = md.lp.clone();
    for j in 0..f.n() {
        if f.int[j] {
            (f.l[j], f.u[j]) = (x[j].round(), x[j].round());
        }
    }
    let g = md.g.expect("M2 rows");
    let ch = &md.m.v.charger;
    let mut on = Vec::new();
    for k in 0..md.slots.len() {
        if f.l[md.u + k] == 0.0 {
            (f.u[md.p + k], f.u[g + k]) = (0.0, 0.0);
        } else {
            on.push(Loss {
                idx: [md.p + k, g + k],
                eta: ch.eta,
                alpha: ch.alpha,
            });
        }
    }
    for i in 0..md.m.c.trips.len() {
        if f.l[md.x1 + i] == 0.0 {
            f.u[md.r + i] = 0.0;
        }
    }
    let h = Losses(on);
    barrier::solve(
        &f,
        (!h.0.is_empty()).then_some(&h as &dyn Rows),
        f64::INFINITY,
    )
}

/// M2 by outer approximation within time seconds; U is the cost of a schedule replayed with
/// losses and taper, L the master's dual bound.
pub fn m2(
    c: &Corridor,
    v: &Transit,
    name: &str,
    fixed: &Infra,
    max_iter: usize,
    time: f64,
) -> Record {
    let t0 = Instant::now();
    let md = rows(c, v, fixed, true);
    let g = md.g.unwrap();
    let ch = &v.charger;
    let cuts: Vec<Box<dyn Cut>> = (0..md.slots.len())
        .map(|k| {
            Box::new(Loss {
                idx: [md.p + k, g + k],
                eta: ch.eta,
                alpha: ch.alpha,
            }) as Box<dyn Cut>
        })
        .collect();
    let points: Vec<Vec<f64>> = [0.0, ch.p / 2.0, ch.p]
        .iter()
        .map(|&pw| {
            let mut z = vec![0.0; md.lp.n()];
            z[md.p..md.p + md.slots.len()].fill(pw);
            z
        })
        .collect();
    let sub = |x: &[f64]| {
        let b = m2_fixed(&md, x);
        (b.status, b.x.filter(|_| b.status == "optimal"))
    };
    let replay = |w: &[f64]| schedule(&md, w, true).1;
    let r = oa(&md.lp, &cuts, &points, sub, replay, max_iter, time, 600.0);
    let sched = r.x.as_ref().map(|x| schedule(&md, x, true).0);
    record(
        "M2",
        name,
        Outcome {
            solver_status: r.status,
            u: r.u,
            l: r.l,
            replayed: None,
            objective: None,
            bound_source: "oa_master_dual",
            message: format!("outer approximation, {} iterations", r.iterations.len()),
            elapsed: t0.elapsed().as_secs_f64(),
            detail: json!({"formulation": M2, "time_limit": time, "max_iter": max_iter, "alpha": ch.alpha, "trips": c.trips.len(),
            "cuts": r.cuts, "iterations": r.iterations, "schedule": sched}),
        },
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::transit::enumerate::enumerate;
    use crate::transit::fixtures::tiny;

    fn fix() -> Infra {
        [("A".to_owned(), (1.0, 500.0))].into()
    }

    fn close(a: f64, b: f64) -> bool {
        (a - b).abs() <= 1e-6 * b.abs() + 1e-4
    }

    #[test]
    fn m1_equals_enumeration_and_the_baseline() {
        // (enumeration at one plug and 500 kW, free M1) of revision 89e967d, seeds 0..5.
        let want = [
            (1332.8804347826087, 1313.9945652173913),
            (1332.8804347826087, 1313.9945652173915),
            (1685.8695652173913, 1662.5000000000052),
            (2082.608695652174, 2043.4782608695652),
            (1685.8695652173913, 1662.5),
            (1685.8695652173913, 1662.5),
        ];
        for (seed, &(z, free)) in want.iter().enumerate() {
            let (c, v) = tiny(seed);
            let r = m1(&c, &v, "tiny", &fix(), 60.0, 1e-6, false);
            assert!(r.certified && close(r.u.unwrap(), z), "{seed}: {r:?}");
            assert!(close(enumerate(&c, &v, "A", 1.0, 500.0).0, z), "{seed}");
            let r = m1(&c, &v, "tiny", &Infra::new(), 60.0, 1e-6, false);
            assert!(r.certified && close(r.u.unwrap(), free), "{seed}");
        }
    }

    #[test]
    fn the_cover_start_keeps_the_optimum_and_bounds_m1() {
        // From the cover start M1 certifies the enumeration optimum; on the full Route 100 day the
        // cover is 16 duties (M0's least fleet) whose charging plan replays at no less than the
        // cover's value.
        for seed in 0..6 {
            let (c, v) = tiny(seed);
            let r = m1(&c, &v, "tiny", &fix(), 60.0, 1e-6, true);
            let z = enumerate(&c, &v, "A", 1.0, 500.0).0;
            assert!(r.certified && close(r.u.unwrap(), z), "{seed}: {r:?}");
        }
        let (c, v) = crate::transit::fixtures::route100();
        let md = rows(&c, &v, &Infra::new(), false);
        let (cv, x) = cover(&md, 120.0);
        let x = x.unwrap();
        assert!(md.lp.feasible(&x, 1e-5));
        let (d, u, ok) = schedule(&md, &x, false);
        assert!(ok && d["fleet"].as_u64() == Some(16));
        assert!(cv.unwrap() <= u.unwrap() + 1e-6);
    }

    #[test]
    fn base_load_on_the_site_meter() {
        // A site too dear to open stays closed, whatever its base load; an open one bills its
        // load L even when no slot of the billing window can charge (0.5 x 10 = 5).
        for g0 in [50.0, 0.0] {
            let (c, mut v) = tiny(0);
            (
                v.sites.get_mut("A").unwrap().l,
                v.sites.get_mut("A").unwrap().g0,
            ) = (10.0, g0);
            v.cost.site = 1e6;
            let r = m1(&c, &v, "tiny", &Infra::new(), 60.0, 1e-6, false);
            assert!(
                r.detail["schedule"]["infra"]
                    .as_object()
                    .unwrap()
                    .is_empty()
                    && r.u.unwrap() < 1e6
            );
            assert!(r.validation_status == "replayed");
        }
        for seed in 0..3 {
            let (c, mut v) = tiny(seed);
            v.sites.get_mut("A").unwrap().l = 10.0;
            (v.cost.peak_from, v.cost.peak_to) = (Some(0.0), Some(1.0));
            let z = enumerate(&c, &v, "A", 1.0, 500.0).0;
            let r = m1(&c, &v, "tiny", &fix(), 60.0, 1e-6, false);
            assert!(r.certified && close(r.u.unwrap(), z), "{seed}");
            assert!(
                (r.detail["schedule"]["replay"]["parts"]["peak"]
                    .as_f64()
                    .unwrap()
                    - 5.0)
                    .abs()
                    < 1e-9
            );
        }
    }

    #[test]
    fn m2_at_fixed_integers_and_by_outer_approximation() {
        // At fixed integers and alpha = 0 the loss rows are linear, g >= p/eta: the barrier
        // optimum is HiGHS's; with alpha > 0 losses only add cost.
        for seed in 0..4 {
            let (c, mut v) = tiny(seed);
            for alpha in [0.0, v.charger.alpha] {
                v.charger.alpha = alpha;
                let x = rows(&c, &v, &fix(), false).lp.solve(60.0, 1e-6).x.unwrap();
                let (m1, md) = (rows(&c, &v, &fix(), false), rows(&c, &v, &fix(), true));
                let mut w = vec![0.0; md.lp.n()];
                for (from, to, k) in [
                    (m1.x0, md.x0, md.u - md.x0),
                    (m1.u, md.u, md.slots.len()),
                    (m1.o, md.o, 3 * md.sites.len()),
                ] {
                    w[to..to + k].copy_from_slice(&x[from..from + k]);
                }
                let b = m2_fixed(&md, &w);
                let mut lp = md.lp.clone();
                for j in (0..lp.n()).filter(|&j| lp.int[j]) {
                    (lp.l[j], lp.u[j]) = (w[j].round(), w[j].round());
                }
                for k in 0..md.slots.len() {
                    lp.ge(
                        vec![(md.g.unwrap() + k, 1.0), (md.p + k, -1.0 / v.charger.eta)],
                        0.0,
                    );
                }
                let z = lp.solve(60.0, 0.0).f.unwrap();
                let f = b.f.unwrap();
                assert_eq!(b.status, "optimal");
                assert!(
                    if alpha == 0.0 {
                        (f - z).abs() < 1e-6 * z
                    } else {
                        f >= z - 1e-6
                    },
                    "{seed} {alpha}: {f} {z}"
                );
            }
        }
        for (seed, z) in [(0, 1315.131803825102), (1, 1315.1259811643142)] {
            let (c, v) = tiny(seed);
            let r = m2(&c, &v, "tiny", &Infra::new(), 40, 300.0);
            assert!(r.certified && close(r.u.unwrap(), z), "{seed}: {r:?}");
        }
    }
}
