//! Outer approximation for convex MINLPs (Algorithms §5; Duran and Grossmann 1986).
//!
//! ```text
//! min c'x   s.t.   the rows and bounds of an Lp,   x_j integer where int_j,
//!                  g_k(x) <= 0   (convex, each on a few columns)
//! ```
//!
//! The master is the MILP with every g_k replaced by the tangent cuts collected so far,
//! g_k(x^) + grad g_k(x^)'(x - x^) <= 0, valid everywhere because g_k is convex; HiGHS's dual
//! bound of the master is therefore a lower bound L. Each master solution's integers are fixed
//! and the convex subproblem solved; a solution the independent replay accepts gives an upper
//! bound U. Cuts are added at the master point and at the subproblem point. The loop stops when
//! U and L close (cert.rs), with `numerical` when they cross (a wrong cut, bound or replay, never
//! an optimum), with `stall` when the master repeats an assignment and violates no cut, or at a
//! limit. One deadline covers the run; each master gets at most the time left.

use crate::cert::{Gap, gap};
use crate::lp::Lp;
use serde::Serialize;
use std::time::Instant;

/// A convex function of the columns idx: its value and gradient at z = x[idx].
pub trait Cut {
    fn idx(&self) -> &[usize];
    fn f(&self, z: &[f64]) -> f64;
    fn grad(&self, z: &[f64]) -> Vec<f64>;
}

#[derive(Clone, Debug, Serialize)]
pub struct Iteration {
    pub k: usize,
    #[serde(rename = "L")]
    pub l: f64,
    #[serde(rename = "U")]
    pub u: Option<f64>,
    pub cuts: usize,
    pub violation: f64,
    pub sub: &'static str,
}

pub struct Oa {
    pub status: &'static str,
    pub u: Option<f64>,
    pub l: Option<f64>,
    pub x: Option<Vec<f64>>,
    pub iterations: Vec<Iteration>,
    pub cuts: usize,
}

/// Tangent row of g at x: grad'(x[idx]) <= grad'z - g(z).
fn tangent(g: &dyn Cut, x: &[f64]) -> (Vec<(usize, f64)>, f64) {
    let z: Vec<f64> = g.idx().iter().map(|&j| x[j]).collect();
    let d = g.grad(&z);
    let hi = d.iter().zip(&z).map(|(a, b)| a * b).sum::<f64>() - g.f(&z);
    (g.idx().iter().copied().zip(d).collect(), hi)
}

/// Outer approximation of (p, g).
///
/// INPUT   points ...... vectors at which cuts are added before the first master
///         sub ......... master point -> (status, x): the convex problem at its integers
///         replay ...... x -> Some(U) if the independent replay accepts x at cost U
///         time ........ seconds for the run; master_time caps each master
pub fn oa(
    p: &Lp,
    g: &[Box<dyn Cut>],
    points: &[Vec<f64>],
    mut sub: impl FnMut(&[f64]) -> (&'static str, Option<Vec<f64>>),
    mut replay: impl FnMut(&[f64]) -> Option<f64>,
    max_iter: usize,
    time: f64,
    master_time: f64,
) -> Oa {
    let t0 = Instant::now();
    let tol = 1e-7;
    let mut m = p.clone();
    for x in points {
        for gk in g {
            let (a, hi) = tangent(gk.as_ref(), x);
            m.le(a, hi);
        }
    }
    let int: Vec<usize> = (0..p.n()).filter(|&j| p.int[j]).collect();
    let (mut u, mut best, mut l) = (None::<f64>, None, f64::NEG_INFINITY);
    let (mut its, mut seen) = (Vec::new(), std::collections::HashSet::new());
    let mut status = "feasible_limit";
    for k in 1..=max_iter {
        let left = time - t0.elapsed().as_secs_f64();
        if left <= 0.0 {
            break;
        }
        let s = m.solve(master_time.min(left), crate::cert::EPS / 10.0);
        let Some(x) = s.x else {
            if s.status == "infeasible" && u.is_none() {
                status = "infeasible";
            }
            break;
        };
        l = l.max(s.bound.unwrap_or(f64::NEG_INFINITY));
        let at =
            |gk: &dyn Cut, x: &[f64]| gk.f(&gk.idx().iter().map(|&j| x[j]).collect::<Vec<_>>());
        let violation = g.iter().map(|gk| at(gk.as_ref(), &x)).fold(0.0, f64::max);
        let mut new: Vec<_> = g
            .iter()
            .filter(|gk| at(gk.as_ref(), &x) > tol)
            .map(|gk| tangent(gk.as_ref(), &x))
            .collect();
        let key: Vec<i64> = int.iter().map(|&j| x[j].round() as i64).collect();
        let (st, w) = sub(&x);
        if let Some(w) = w {
            if let Some(uw) = replay(&w)
                && u.is_none_or(|u| uw < u)
            {
                u = Some(uw);
                best = Some(w.clone());
            }
            new.extend(g.iter().map(|gk| tangent(gk.as_ref(), &w)));
        }
        its.push(Iteration {
            k,
            l,
            u,
            cuts: m.rows.len() - p.rows.len(),
            violation,
            sub: st,
        });
        match gap(u, Some(l)) {
            Gap::Crossed => {
                status = "numerical";
                break;
            }
            Gap::Closed => {
                status = "optimal";
                break;
            }
            Gap::Open => {}
        }
        if !seen.insert(key) && violation <= tol {
            status = "stall";
            break;
        }
        for (a, hi) in new {
            m.le(a, hi);
        }
    }
    if u.is_none() && status == "feasible_limit" {
        status = "no_incumbent";
    }
    Oa {
        status,
        u,
        l: l.is_finite().then_some(l),
        x: best,
        cuts: m.rows.len() - p.rows.len(),
        iterations: its,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// (x0 - 2.4)^2 - x1 <= 0 on columns 0, 1.
    struct Bowl;

    impl Cut for Bowl {
        fn idx(&self) -> &[usize] {
            &[0, 1]
        }
        fn f(&self, z: &[f64]) -> f64 {
            (z[0] - 2.4).powi(2) - z[1]
        }
        fn grad(&self, z: &[f64]) -> Vec<f64> {
            vec![2.0 * (z[0] - 2.4), -1.0]
        }
    }

    fn bowl() -> Lp {
        let mut p = Lp::default();
        p.var(0.0, 0.0, 5.0, true);
        p.var(1.0, 0.0, 100.0, false);
        p
    }

    fn sub(x: &[f64]) -> (&'static str, Option<Vec<f64>>) {
        let r = x[0].round();
        ("optimal", Some(vec![r, (r - 2.4).powi(2)]))
    }

    #[test]
    fn integer_minimum_of_a_bowl() {
        // min x1 s.t. (x0 - 2.4)^2 <= x1, x0 integer in [0, 5]: x0 = 2, x1 = 0.16.
        let r = oa(
            &bowl(),
            &[Box::new(Bowl)],
            &[],
            sub,
            |w| Some(w[1]),
            50,
            60.0,
            60.0,
        );
        assert_eq!(r.status, "optimal");
        assert!((r.u.unwrap() - 0.16).abs() < 1e-6 && r.l.unwrap() <= r.u.unwrap() + 1e-6);
    }

    #[test]
    fn a_crossed_bound_is_not_optimal() {
        // A replay that under-reports U = -1 < z* = 0.16 <= L must end as numerical.
        let r = oa(
            &bowl(),
            &[Box::new(Bowl)],
            &[],
            sub,
            |_| Some(-1.0),
            50,
            60.0,
            60.0,
        );
        assert_eq!(r.status, "numerical");
    }
}
