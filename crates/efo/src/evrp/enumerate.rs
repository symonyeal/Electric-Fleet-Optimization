//! Exhaustive EVRP optimum for tiny instances (Validation §2), a test oracle written from the
//! rules of Routing §1 alone; it shares no code with the formulations.
//!
//! For a fixed customer order a label search carries (length, charge) through the order; between
//! consecutive stops it goes direct or through any walk of stations, found by Dijkstra over legs
//! the battery allows. A subset's cost is the least over its orders; the optimum is the least
//! partition of the customers into subsets. O(n! 3^n): n <= 7.

use super::Instance;

const TOL: f64 = 1e-9;

/// (added length, charge on arrival at t, stations between) for each way from s with charge y.
fn reach(p: &Instance, s: usize, y: f64, t: usize) -> Vec<(f64, f64, Vec<usize>)> {
    let e = |a: usize, b: usize| p.h * p.d[a][b];
    let mut out = Vec::new();
    if e(s, t) <= y + TOL {
        out.push((p.d[s][t], y - e(s, t), Vec::new()));
    }
    let m = p.f.len();
    let mut dist: Vec<f64> =
        p.f.iter()
            .map(|&f| {
                if e(s, f) <= y + TOL {
                    p.d[s][f]
                } else {
                    f64::INFINITY
                }
            })
            .collect();
    let mut prev = vec![None; m];
    let mut done = vec![false; m];
    while let Some(a) = (0..m)
        .filter(|&k| !done[k] && dist[k].is_finite())
        .min_by(|&x, &z| dist[x].total_cmp(&dist[z]))
    {
        done[a] = true;
        for g in 0..m {
            let dg = dist[a] + p.d[p.f[a]][p.f[g]];
            if !done[g] && e(p.f[a], p.f[g]) <= p.q + TOL && dg < dist[g] {
                dist[g] = dg;
                prev[g] = Some(a);
            }
        }
    }
    for g in 0..m {
        if dist[g].is_finite() && e(p.f[g], t) <= p.q + TOL {
            let mut walk = vec![g];
            while let Some(a) = prev[*walk.last().unwrap()] {
                walk.push(a);
            }
            out.push((
                dist[g] + p.d[p.f[g]][t],
                p.q - e(p.f[g], t),
                walk.iter().rev().map(|&k| p.f[k]).collect(),
            ));
        }
    }
    out
}

/// Least length of o -> seq -> o and its nodes, or (inf, []) when no charging plan serves it.
pub fn route(p: &Instance, seq: &[usize]) -> (f64, Vec<usize>) {
    let mut labels = vec![(0.0, p.q, vec![p.o])];
    for &t in seq.iter().chain(std::iter::once(&p.o)) {
        let mut new = Vec::new();
        for (l, y, v) in &labels {
            for (dl, y2, mid) in reach(p, *v.last().unwrap(), *y, t) {
                let mut w = v.clone();
                w.extend(mid);
                w.push(t);
                new.push((l + dl, y2, w));
            }
        }
        new.sort_by(|a, b| a.0.total_cmp(&b.0).then(a.1.total_cmp(&b.1)));
        labels.clear();
        let mut best = f64::NEG_INFINITY;
        for lab in new {
            if lab.1 > best + TOL {
                best = lab.1;
                labels.push(lab); // Pareto: shorter, or more charge
            }
        }
    }
    labels
        .into_iter()
        .next()
        .map_or((f64::INFINITY, Vec::new()), |l| (l.0, l.2))
}

pub fn permutations(s: &[usize]) -> Vec<Vec<usize>> {
    if s.len() <= 1 {
        return vec![s.to_vec()];
    }
    let mut out = Vec::new();
    for k in 0..s.len() {
        let mut rest = s.to_vec();
        let first = rest.remove(k);
        for mut q in permutations(&rest) {
            q.insert(0, first);
            out.push(q);
        }
    }
    out
}

/// (z*, routes as 1-based identifiers); (inf, []) if no feasible solution exists.
pub fn enumerate(p: &Instance) -> (f64, Vec<Vec<usize>>) {
    let n = p.i.len();
    let full = (1usize << n) - 1;
    let mut cost = vec![(f64::INFINITY, Vec::new()); full + 1];
    cost[0].0 = 0.0;
    for mask in 1..=full {
        let s: Vec<usize> = (0..n)
            .filter(|k| mask >> k & 1 == 1)
            .map(|k| p.i[k])
            .collect();
        if s.iter().map(|&i| p.b[i]).sum::<f64>() <= p.cap + TOL {
            cost[mask] = permutations(&s)
                .iter()
                .map(|q| route(p, q))
                .min_by(|a, b| a.0.total_cmp(&b.0))
                .unwrap();
        }
    }
    let mut f: Vec<(f64, Vec<usize>)> = vec![(f64::INFINITY, Vec::new()); full + 1];
    f[0].0 = 0.0;
    for mask in 1..=full {
        let low = mask & mask.wrapping_neg();
        let mut s = mask;
        while s > 0 {
            if s & low != 0 && cost[s].0 + f[mask ^ s].0 < f[mask].0 {
                let mut parts = vec![s];
                parts.extend(&f[mask ^ s].1);
                f[mask] = (cost[s].0 + f[mask ^ s].0, parts);
            }
            s = (s - 1) & mask;
        }
    }
    let (z, parts) = &f[full];
    if !z.is_finite() {
        return (f64::INFINITY, Vec::new());
    }
    (
        *z,
        parts
            .iter()
            .map(|&s| cost[s].1.iter().map(|k| k + 1).collect())
            .collect(),
    )
}
