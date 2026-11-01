//! Station graph and Pareto station paths (Routing §2).
//!
//! A segment from i to j is p = (i, f_1, ..., f_k, j), k >= 0, f_t stations, with length l,
//! first-leg energy a = e_{i f_1} and last-leg energy w = e_{f_k j} (both e_ij when k = 0). For
//! k >= 1 the vehicle reaches j with Q - w whatever its charge at i, provided that charge is at
//! least a; hence among k >= 1 only the Pareto-minimal (l, a, w) matter, and for fixed first and
//! last stations f, g the interior is a shortest path SP(f, g) of the station graph.

use super::Instance;

const TOL: f64 = 1e-9;

#[derive(Clone, Debug)]
pub struct Path {
    pub i: usize,
    pub j: usize,
    pub l: f64,
    pub a: f64,
    pub w: f64,
    pub nodes: Vec<usize>,
}

impl Path {
    pub fn direct(&self) -> bool {
        self.nodes.len() == 2
    }
}

/// Floyd-Warshall on stations over legs consuming at most Q: lengths S (inf when unreachable)
/// and successors for recovery, both |F| x |F|. O(|F|^3).
fn station_sp(p: &Instance) -> (Vec<Vec<f64>>, Vec<Vec<usize>>) {
    let m = p.f.len();
    let mut s = vec![vec![f64::INFINITY; m]; m];
    let mut next = vec![(0..m).collect::<Vec<_>>(); m];
    for (a, &fa) in p.f.iter().enumerate() {
        for (c, &fc) in p.f.iter().enumerate() {
            if p.h * p.d[fa][fc] <= p.q + TOL {
                s[a][c] = p.d[fa][fc];
            }
        }
        s[a][a] = 0.0;
    }
    for k in 0..m {
        for a in 0..m {
            for c in 0..m {
                if s[a][k] + s[k][c] < s[a][c] {
                    s[a][c] = s[a][k] + s[k][c];
                    next[a][c] = next[a][k];
                }
            }
        }
    }
    (s, next)
}

/// Paths from sources {o} ∪ I to sinks I ∪ {o}, no (o, o): the direct arc when e_ij <= Q, and the
/// Pareto-minimal station paths with a, w <= Q, grouped by (i, j). O(n^2 |F|^2) candidates.
pub fn paths(p: &Instance) -> Vec<Path> {
    let (s, next) = station_sp(p);
    let src = std::iter::once(p.o).chain(p.i.iter().copied());
    let mut out = Vec::new();
    for i in src {
        for j in p.i.iter().copied().chain(std::iter::once(p.o)) {
            if i == j {
                continue;
            }
            let e = p.h * p.d[i][j];
            if e <= p.q + TOL {
                out.push(Path {
                    i,
                    j,
                    l: p.d[i][j],
                    a: e,
                    w: e,
                    nodes: vec![i, j],
                });
            }
            let mut cand = Vec::new();
            for (f, &sf) in p.f.iter().enumerate() {
                for (g, &sg) in p.f.iter().enumerate() {
                    let (a, w) = (p.h * p.d[i][sf], p.h * p.d[sg][j]);
                    let l = p.d[i][sf] + s[f][g] + p.d[sg][j];
                    if l.is_finite() && a <= p.q + TOL && w <= p.q + TOL {
                        cand.push((l, a, w, f, g));
                    }
                }
            }
            cand.sort_by(|x, y| {
                x.0.total_cmp(&y.0)
                    .then(x.1.total_cmp(&y.1))
                    .then(x.2.total_cmp(&y.2))
            });
            let mut kept: Vec<(f64, f64, f64, usize, usize)> = Vec::new();
            for c in cand {
                if !kept
                    .iter()
                    .any(|k| k.0 <= c.0 + TOL && k.1 <= c.1 + TOL && k.2 <= c.2 + TOL)
                {
                    kept.push(c);
                }
            }
            for (l, a, w, f, g) in kept {
                let mut nodes = vec![i, p.f[f]];
                let mut k = f;
                while k != g {
                    k = next[k][g];
                    nodes.push(p.f[k]);
                }
                nodes.push(j);
                out.push(Path {
                    i,
                    j,
                    l,
                    a,
                    w,
                    nodes,
                });
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn path_counts_match_the_baseline() {
        // Counts of revision 89e967d (models/paths.py).
        for (name, n) in [
            ("tiny.evrp", 40),
            ("rand0.evrp", 60),
            ("rand1.evrp", 106),
            ("rand2.evrp", 122),
            ("rand3.evrp", 80),
        ] {
            assert_eq!(paths(&crate::evrp::fixture(name)).len(), n, "{name}");
        }
    }
}
