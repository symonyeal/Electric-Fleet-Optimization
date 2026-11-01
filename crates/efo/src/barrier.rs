//! Convex subproblems by the primal-dual barrier method (Vanderbei Ch. 25; Algorithms §4).
//!
//! ```text
//! min c'x   s.t.   lo <= A x <= hi,   l <= x <= u,   h(x) <= 0   (h convex)
//! ```
//!
//! An Lp whose integer columns the caller has fixed (l_j = u_j), with convex rows h. Fixed
//! columns are eliminated and the rest shifted to 0 <= x' <= u - l; a row left without free
//! columns is checked as a constant and dropped; each finite side of a ranged row gets a slack
//! s in [0, side - min over the box of its row], finite whenever the box makes it so, and none
//! when that bound is 0 (the side then holds with equality). The kernel (efo_kernels::ipm) then
//! sees A x' = b.

use crate::lp::Lp;
use efo_kernels::ipm::{self, Convex, Csc, Opts, Status, Trip};

/// Convex rows h(x) <= 0 on the full vector x: values, Jacobian and the Hessian of sum lam_k h_k
/// (both triangles), with columns indexing x.
pub trait Rows {
    fn h(&self, x: &[f64]) -> Vec<f64>;
    fn jac(&self, x: &[f64]) -> Trip;
    fn hess(&self, x: &[f64], lam: &[f64]) -> Trip;
}

/// The rows h restricted to the free columns J of a box with lower bound l.
struct Free<'a> {
    h: &'a dyn Rows,
    l: &'a [f64],
    at: Vec<Option<usize>>,
    cols: &'a [usize],
}

impl Free<'_> {
    fn full(&self, x: &[f64]) -> Vec<f64> {
        let mut v = self.l.to_vec();
        for (k, &j) in self.cols.iter().enumerate() {
            v[j] += x[k];
        }
        v
    }

    /// t with its columns mapped to free positions; entries on fixed columns dropped.
    fn restrict(&self, t: Trip, rows_too: bool) -> Trip {
        let mut out = Trip::default();
        for e in 0..t.v.len() {
            let r = if rows_too {
                self.at[t.r[e]]
            } else {
                Some(t.r[e])
            };
            if let (Some(r), Some(c)) = (r, self.at[t.c[e]]) {
                out.r.push(r);
                out.c.push(c);
                out.v.push(t.v[e]);
            }
        }
        out
    }
}

impl Convex for Free<'_> {
    fn h(&mut self, x: &[f64]) -> Vec<f64> {
        self.h.h(&self.full(x))
    }

    fn jac(&mut self, x: &[f64]) -> Trip {
        self.restrict(self.h.jac(&self.full(x)), false)
    }

    fn hess(&mut self, x: &[f64], lam: &[f64]) -> Trip {
        self.restrict(self.h.hess(&self.full(x), lam), true)
    }
}

/// status (optimal, limit, numerical, infeasible) and, unless infeasible, the last iterate x
/// with its objective f = c'x.
pub struct Barrier {
    pub status: &'static str,
    pub x: Option<Vec<f64>>,
    pub f: Option<f64>,
}

/// The barrier method on p with convex rows h, within time seconds.
pub fn solve(p: &Lp, h: Option<&dyn Rows>, time: f64) -> Barrier {
    let infeasible = Barrier {
        status: "infeasible",
        x: None,
        f: None,
    };
    let n = p.n();
    if (0..n).any(|j| p.l[j] > p.u[j] || !p.l[j].is_finite()) {
        return infeasible;
    }
    let cols: Vec<usize> = (0..n).filter(|&j| p.l[j] < p.u[j]).collect();
    let mut at = vec![None; n];
    for (k, &j) in cols.iter().enumerate() {
        at[j] = Some(k);
    }
    let mut c: Vec<f64> = cols.iter().map(|&j| p.c[j]).collect();
    let mut u: Vec<f64> = cols.iter().map(|&j| p.u[j] - p.l[j]).collect();
    let f0 = p.value(&p.l);
    let mut trip: Vec<(usize, usize, f64)> = Vec::new();
    let mut b = Vec::new();
    for r in &p.rows {
        let mut a: Vec<(usize, f64)> = Vec::new();
        let mut al = 0.0;
        for &(j, v) in &r.a {
            al += v * p.l[j];
            if let Some(k) = at[j] {
                a.push((k, v));
            }
        }
        a.retain(|e| e.1 != 0.0);
        if a.is_empty() {
            let t = 1e-9 * (1.0 + al.abs());
            if al < r.lo - t || al > r.hi + t {
                return infeasible;
            }
            continue;
        }
        if r.lo == r.hi {
            let i = b.len();
            trip.extend(a.iter().map(|&(k, v)| (i, k, v)));
            b.push(r.lo - al);
            continue;
        }
        for (side, sign) in [(r.hi, 1.0), (r.lo, -1.0)] {
            if !side.is_finite() {
                continue;
            }
            // sign a'x' + s = sign (side - a'l),  0 <= s <= rhs - min over the box of sign a'x'.
            let rhs = sign * (side - al);
            let least: f64 = a
                .iter()
                .map(|&(k, v)| if sign * v < 0.0 { sign * v * u[k] } else { 0.0 })
                .sum();
            let smax = rhs - least;
            if smax < -1e-9 * (1.0 + rhs.abs()) {
                return infeasible;
            }
            let i = b.len();
            trip.extend(a.iter().map(|&(k, v)| (i, k, sign * v)));
            b.push(rhs);
            if smax > 0.0 {
                trip.push((i, c.len(), 1.0));
                c.push(0.0);
                u.push(smax);
            } // else the side holds only with equality: a slack in [0, 0] has no interior
        }
    }
    let a = csc(b.len(), c.len(), trip);
    let mut free = h.map(|h| Free {
        h,
        l: &p.l,
        at: at.clone(),
        cols: &cols,
    });
    let out = ipm::ipm(
        &a,
        &b,
        &c,
        &u,
        f0,
        free.as_mut().map(|f| f as &mut dyn Convex),
        Opts {
            time_limit: time,
            ..Opts::default()
        },
    );
    let mut x = p.l.clone();
    for (k, &j) in cols.iter().enumerate() {
        x[j] += out.x[k];
    }
    Barrier {
        status: match out.status {
            Status::Optimal => "optimal",
            Status::Limit => "limit",
            Status::Numerical => "numerical",
        },
        f: Some(p.value(&x)),
        x: Some(x),
    }
}

/// Compressed columns of an m x n matrix from triplets; duplicates are summed.
fn csc(m: usize, n: usize, mut t: Vec<(usize, usize, f64)>) -> Csc {
    t.sort_by_key(|&(r, c, _)| (c, r));
    let mut a = Csc {
        m,
        n,
        p: vec![0; n + 1],
        ..Csc::default()
    };
    let mut last = None;
    for (r, c, v) in t {
        if last == Some((r, c)) {
            *a.v.last_mut().unwrap() += v;
        } else {
            a.i.push(r);
            a.v.push(v);
            a.p[c + 1] += 1;
            last = Some((r, c));
        }
    }
    for k in 0..n {
        a.p[k + 1] += a.p[k];
    }
    a
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_side_tight_on_the_box_is_an_equality() {
        // min -x - y s.t. x + y <= 1, x <= 0 on 0 <= x, y <= 1: the second row's slack would lie
        // in [0, 0], which has no interior; on Route 100 it made every subproblem numerical.
        let mut p = Lp::default();
        let (x, y) = (p.var(-1.0, 0.0, 1.0, false), p.var(-1.0, 0.0, 1.0, false));
        p.le(vec![(x, 1.0), (y, 1.0)], 1.0);
        p.le(vec![(x, 1.0)], 0.0);
        let b = solve(&p, None, 10.0);
        assert_eq!(b.status, "optimal");
        assert!((b.f.unwrap() + 1.0).abs() < 1e-7 && b.x.unwrap()[x].abs() < 1e-7);
    }
}
