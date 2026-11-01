//! Least reduced-cost ng-routes by labeling on the station-path multigraph (Routing §3).
//!
//! Legend
//!   o ........ the depot;  I .. customers, at positions 0..n of the ng bitmasks (n <= 128)
//!   arc ...... a station path p from i to j: length l, first-leg energy a, last-leg energy w;
//!              direct when it visits no station
//!   pi_j ..... dual of customer j;  W_ij .. arc dual of (R2.4), zero when absent
//!   label .... (cbar, q, y, M) at a node: reduced cost, load, charge on leaving, ng-memory
//!   f(j, r) .. a lower bound on the reduced cost of any completion from j to o with load at most
//!              r, ignoring the battery and elementarity (a backward DP over loads, exact on the
//!              relaxation); defined when demands and C are integral and every b_j >= 1
//!
//! Extending a label at i along p in P_ij needs y >= a and, at a customer j, j not in M and
//! q + b_j <= C; then y' = y - a (direct) or Q - w, cbar' = cbar + l - pi_j - W_ij, q' = q + b_j,
//! M' = (M & N_j) | {j}. L1 dominates L2 at the same node if cbar1 <= cbar2, q1 <= q2, y1 >= y2
//! and M1 is within M2. Labels are processed in order of load, which grows along every arc.
//! A label with cbar + f(j, C - q) > ub cannot complete below ub and is not kept: the least
//! reduced cost cbar* is exact whenever it is below ub, and every route below ub is reachable.

use std::cmp::{Ordering, Reverse};
use std::collections::BinaryHeap;
use std::time::Instant;

#[derive(Clone, Copy, Debug)]
pub struct Arc {
    pub i: usize,
    pub j: usize,
    pub l: f64,
    pub a: f64,
    pub w: f64,
    pub direct: bool,
}

/// The static part of the pricing problem: graph, demands, capacities, ng-sets.
pub struct Graph {
    pub nodes: usize,
    pub o: usize,
    pub pos: Vec<Option<usize>>,
    pub b: Vec<f64>,
    pub c: f64,
    pub q: f64,
    pub arcs: Vec<Arc>,
    pub ng: Vec<u128>,
    out: Vec<Vec<usize>>,
    lmin: Vec<f64>,
    unit: Option<(f64, Vec<usize>, usize)>,
}

#[derive(Clone, Copy)]
struct Label {
    cb: f64,
    q: f64,
    y: f64,
    m: u128,
    parent: u32,
    arc: u32,
}

const ROOT: u32 = u32::MAX;

/// A column: reduced cost and the arcs of its route in order.
#[derive(Clone, Debug)]
pub struct Column {
    pub rc: f64,
    pub arcs: Vec<usize>,
}

pub struct Priced {
    pub best: f64,
    pub exact: bool,
    pub cols: Vec<Column>,
}

/// (value, label, arc), ordered by value, then label and arc: the key of both heaps below.
#[derive(Clone, Copy, PartialEq)]
struct Key(f64, u32, u32);

impl Eq for Key {}
impl PartialOrd for Key {
    fn partial_cmp(&self, o: &Self) -> Option<Ordering> {
        Some(self.cmp(o))
    }
}
impl Ord for Key {
    fn cmp(&self, o: &Self) -> Ordering {
        self.0
            .total_cmp(&o.0)
            .then((self.1, self.2).cmp(&(o.1, o.2)))
    }
}

impl Graph {
    /// pos[k] is customer k's position in the ng bitmasks; ng[k] is N_k (customers only).
    pub fn new(
        nodes: usize,
        o: usize,
        pos: Vec<Option<usize>>,
        b: Vec<f64>,
        c: f64,
        q: f64,
        arcs: Vec<Arc>,
        ng: Vec<u128>,
    ) -> Graph {
        let mut out = vec![Vec::new(); nodes];
        let mut lmin = vec![f64::INFINITY; nodes * nodes];
        for (k, e) in arcs.iter().enumerate() {
            out[e.i].push(k);
            lmin[e.i * nodes + e.j] = lmin[e.i * nodes + e.j].min(e.l);
        }
        let cust: Vec<usize> = (0..nodes).filter(|&k| pos[k].is_some()).collect();
        let integral = |x: f64| (x - x.round()).abs() <= 1e-9;
        let unit =
            (cust.iter().all(|&k| b[k] >= 1.0 && integral(b[k])) && integral(c)).then(|| {
                let g = cust
                    .iter()
                    .fold(c.round() as u64, |g, &k| gcd(g, b[k].round() as u64))
                    .max(1) as f64;
                let units = (0..nodes)
                    .map(|k| {
                        if pos[k].is_some() {
                            (b[k] / g).round() as usize
                        } else {
                            0
                        }
                    })
                    .collect();
                (g, units, (c / g).round() as usize)
            });
        Graph {
            nodes,
            o,
            pos,
            b,
            c,
            q,
            arcs,
            ng,
            out,
            lmin,
            unit,
        }
    }

    /// f(j, r) for r = 0..R in units, as a nodes x (R + 1) table; None when undefined.
    fn completion(&self, pi: &[f64], wd: Option<&[f64]>) -> Option<(f64, usize, Vec<f64>)> {
        let (g, units, rmax) = self.unit.as_ref()?;
        let nn = self.nodes;
        let cust: Vec<usize> = (0..nn).filter(|&k| self.pos[k].is_some()).collect();
        let mut f = vec![f64::INFINITY; nn * (rmax + 1)];
        for r in 0..=*rmax {
            for &j in &cust {
                let mut best = self.lmin[j * nn + self.o];
                for &k in &cust {
                    let l = self.lmin[j * nn + k];
                    if k != j && units[k] <= r && l.is_finite() {
                        let e = l - pi[k] - wd.map_or(0.0, |w| w[j * nn + k])
                            + f[k * (rmax + 1) + r - units[k]];
                        best = best.min(e);
                    }
                }
                f[j * (rmax + 1) + r] = best;
            }
        }
        Some((*g, *rmax, f))
    }

    /// Price at duals pi (per node) and arc duals W (row-major nodes x nodes).
    ///
    /// INPUT   cap ........ None for exact pricing; Some(k) keeps the k best labels per node
    ///         ub ......... completions are kept and cbar* is exact below ub
    ///         ncols ...... the most columns returned, least reduced cost first
    /// OUTPUT  best (cbar*, exact if exact and best < ub), exact, columns with rc < -tol
    pub fn price(
        &self,
        pi: &[f64],
        wd: Option<&[f64]>,
        cap: Option<usize>,
        time_limit: f64,
        tol: f64,
        ub: f64,
        ncols: usize,
    ) -> Priced {
        let t0 = Instant::now();
        let fc = self.completion(pi, wd);
        let nn = self.nodes;
        let mut lab = vec![Label {
            cb: 0.0,
            q: 0.0,
            y: self.q,
            m: 0,
            parent: ROOT,
            arc: ROOT,
        }];
        let mut node = vec![self.o];
        let mut alive = vec![true];
        let mut at: Vec<Vec<u32>> = vec![Vec::new(); nn];
        let mut heap = BinaryHeap::new();
        heap.push(Reverse(Key(0.0, 0, 0))); // pending labels, least load first
        let mut best = f64::INFINITY;
        let mut done = BinaryHeap::new(); // completions, the ncols least kept
        let mut exact = cap.is_none();
        let mut pops = 0usize;
        while let Some(Reverse(Key(_, k, _))) = heap.pop() {
            pops += 1;
            if pops.is_multiple_of(256) && t0.elapsed().as_secs_f64() > time_limit {
                exact = false;
                break;
            }
            let k = k as usize;
            if !alive[k] {
                continue;
            }
            let lk = lab[k];
            let i = node[k];
            for &e in &self.out[i] {
                let p = self.arcs[e];
                if lk.y < p.a - tol {
                    continue;
                }
                let j = p.j;
                if j == self.o {
                    if i != self.o {
                        let rc = lk.cb + p.l;
                        best = best.min(rc);
                        if rc < -tol {
                            done.push(Key(rc, k as u32, e as u32));
                            if done.len() > ncols {
                                done.pop();
                            }
                        }
                    }
                    continue;
                }
                let bit = 1u128 << self.pos[j].unwrap();
                if lk.m & bit != 0 || lk.q + self.b[j] > self.c + tol {
                    continue;
                }
                let new = Label {
                    cb: lk.cb + p.l - pi[j] - wd.map_or(0.0, |w| w[i * nn + j]),
                    q: lk.q + self.b[j],
                    y: if p.direct { lk.y - p.a } else { self.q - p.w },
                    m: (lk.m & self.ng[j]) | bit,
                    parent: k as u32,
                    arc: e as u32,
                };
                if let Some((g, rmax, f)) = &fc {
                    let r = (((self.c - new.q) / g + 1e-9).floor() as usize).min(*rmax);
                    if new.cb + f[j * (rmax + 1) + r] > ub + tol {
                        continue;
                    }
                }
                let dominated = at[j].iter().any(|&h| {
                    let h = &lab[h as usize];
                    h.cb <= new.cb + tol
                        && h.q <= new.q + tol
                        && h.y >= new.y - tol
                        && h.m & !new.m == 0
                });
                if dominated {
                    continue;
                }
                at[j].retain(|&h| {
                    let hl = &lab[h as usize];
                    let gone = new.cb <= hl.cb + tol
                        && new.q <= hl.q + tol
                        && new.y >= hl.y - tol
                        && new.m & !hl.m == 0;
                    if gone {
                        alive[h as usize] = false;
                    }
                    !gone
                });
                if let Some(kmax) = cap
                    && at[j].len() >= kmax
                {
                    let (wpos, &worst) = at[j]
                        .iter()
                        .enumerate()
                        .max_by(|a, b| lab[*a.1 as usize].cb.total_cmp(&lab[*b.1 as usize].cb))
                        .unwrap();
                    if lab[worst as usize].cb <= new.cb {
                        continue;
                    }
                    alive[worst as usize] = false;
                    at[j].swap_remove(wpos);
                }
                let id = lab.len() as u32;
                lab.push(new);
                node.push(j);
                alive.push(true);
                at[j].push(id);
                heap.push(Reverse(Key(new.q, id, 0)));
            }
        }
        let cols: Vec<Column> = done
            .into_sorted_vec()
            .into_iter()
            .map(|Key(rc, k, last)| {
                let mut arcs = vec![last as usize];
                let mut h = k;
                while lab[h as usize].parent != ROOT {
                    arcs.push(lab[h as usize].arc as usize);
                    h = lab[h as usize].parent;
                }
                arcs.reverse();
                Column { rc, arcs }
            })
            .collect();
        Priced { best, exact, cols }
    }
}

fn gcd(a: u64, b: u64) -> u64 {
    if b == 0 { a } else { gcd(b, a % b) }
}
