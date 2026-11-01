//! Exhaustive M1 optimum for tiny timetables at one charging site (Validation §2), a test oracle
//! that shares no rows with fleet.rs.
//!
//! Every trip starts and ends at one stop, which is the only site and where the depot is, so no
//! deadhead is driven; the site's plugs and upgrade are given. Every partition of the trips into
//! time-feasible chains is a candidate fleet; for each, the charging plan is a small MILP written
//! here (energy per trip and slot, one plug per charging bus), and the least total over partitions
//! is the optimum. Bell(5) = 52 partitions.

use super::Corridor;
use crate::lp::Lp;
use crate::scenario::{Transit, billed};
use std::collections::BTreeMap;

fn partitions(items: &[usize]) -> Vec<Vec<Vec<usize>>> {
    let Some((&first, rest)) = items.split_first() else {
        return vec![Vec::new()];
    };
    let mut out = Vec::new();
    for part in partitions(rest) {
        let mut alone = vec![vec![first]];
        alone.extend(part.iter().cloned());
        out.push(alone);
        for k in 0..part.len() {
            let mut q = part.clone();
            q[k].insert(0, first);
            out.push(q);
        }
    }
    out
}

/// Least charging, depot-restore and peak cost of fixed chains, or inf if infeasible.
fn charging(
    c: &Corridor,
    v: &Transit,
    site: &str,
    chains: &[Vec<usize>],
    plugs: f64,
    up: f64,
) -> f64 {
    let (b, ch, co, tm) = (&v.battery, &v.charger, &v.cost, &v.time);
    let (rb, top, s0b, h, d) = (
        b.reserve * b.b,
        b.smax * b.b,
        b.s0 * b.b,
        tm.delta / 3600.0,
        &v.sites[site],
    );
    let (rho, w0, w1) = co.tariff();
    let t = &c.trips;
    let mut m = Lp::default();
    let mut slots: BTreeMap<i64, Vec<usize>> = BTreeMap::new();
    for chain in chains {
        let mut prev: Option<(usize, usize)> = None;
        for &j in chain {
            let y = m.var(0.0, rb + b.kappa * t[j].km, top, false);
            let here = prev.map_or(f64::NEG_INFINITY, |(i, _)| t[i].arr);
            let mut row = vec![(y, 1.0)];
            for s in ((t[j].dep - tm.window) / tm.delta).ceil() as i64
                ..(t[j].dep / tm.delta).floor() as i64
            {
                if s as f64 * tm.delta >= here {
                    let p = m.var(rho * co.energy * h / ch.eta, 0.0, ch.p, false);
                    let u = m.var(0.0, 0.0, 1.0, true);
                    m.le(vec![(p, 1.0), (u, -ch.p)], 0.0);
                    slots.entry(s).or_default().extend([p, u]);
                    row.push((p, -h));
                }
            }
            match prev {
                None => m.eq(row, s0b), // y_j = s0 B + h sum p
                Some((i, yi)) => {
                    row.push((yi, -1.0)); // y_j = y_i - E_i + h sum p, arrival above reserve
                    m.eq(row, -b.kappa * t[i].km);
                    m.ge(vec![(yi, 1.0)], rb + b.kappa * t[i].km);
                }
            }
            prev = Some((j, y));
        }
        let (last, yl) = prev.unwrap();
        let end = m.var(0.0, 0.0, top, false);
        let r = m.var(rho * co.depot_energy / ch.eta, 0.0, f64::INFINITY, false);
        m.eq(vec![(end, 1.0), (yl, -1.0)], -b.kappa * t[last].km);
        m.ge(vec![(end, 1.0)], rb);
        m.ge(vec![(r, 1.0), (end, 1.0)], s0b); // r >= s0 B - end, r >= 0
    }
    let peak = m.var(rho * co.peak, d.l, f64::INFINITY, false); // the base load is billed
    for (&s, pu) in &slots {
        let (p, u): (Vec<usize>, Vec<usize>) = (
            pu.iter().step_by(2).copied().collect(),
            pu.iter().skip(1).step_by(2).copied().collect(),
        );
        m.le(u.iter().map(|&k| (k, 1.0)).collect(), plugs);
        m.le(
            p.iter().map(|&k| (k, 1.0 / ch.eta)).collect(),
            d.g0 + up - d.l,
        );
        if billed(s as f64 * tm.delta, w0, w1) {
            m.le(
                [
                    p.iter().map(|&k| (k, 1.0 / ch.eta)).collect(),
                    vec![(peak, -1.0)],
                ]
                .concat(),
                -d.l,
            );
        }
    }
    let s = m.solve(60.0, 0.0);
    if s.status == "optimal" {
        s.f.unwrap()
    } else {
        f64::INFINITY
    }
}

/// (least cost, best chains of trip indices) with site's plugs and upgrade up given.
pub fn enumerate(
    c: &Corridor,
    v: &Transit,
    site: &str,
    plugs: f64,
    up: f64,
) -> (f64, Vec<Vec<usize>>) {
    let (co, d, t) = (&v.cost, &v.sites[site], &c.trips);
    if d.l > d.g0 + up + 1e-9 {
        return (f64::INFINITY, Vec::new()); // the meter's base load cannot be served
    }
    let fixed = co.site + co.tariff().0 * co.basic + co.plug * plugs + co.upgrade * up;
    let mut order: Vec<usize> = (0..t.len()).collect();
    order.sort_by(|a, b| t[*a].dep.total_cmp(&t[*b].dep));
    let mut best = (f64::INFINITY, Vec::new());
    for mut part in partitions(&order) {
        for chain in &mut part {
            chain.sort_by(|a, b| t[*a].dep.total_cmp(&t[*b].dep));
        }
        if part.iter().any(|q| {
            q.windows(2)
                .any(|e| t[e[0]].arr + v.time.layover > t[e[1]].dep)
        }) {
            continue;
        }
        let total = co.f * part.len() as f64 + charging(c, v, site, &part, plugs, up) + fixed;
        if total < best.0 {
            best = (total, part);
        }
    }
    best
}
