//! Primal-dual path following (Vanderbei Ch. 17-19, convex Ch. 25; Algorithms §2-§3).
//!
//! ```text
//! min c'x   s.t.   Ax = b,   0 <= x <= U,   h(x) <= 0,     U_j = inf allowed,
//! ```
//!
//! the problem after the caller has eliminated fixed columns and shifted l to 0.
//!
//! Legend
//!   w ........ U - x on finite U (B: the columns with finite U); 1 elsewhere, unused
//!   y, z, v .. multipliers of Ax = b, x >= 0, w >= 0
//!   sl, lam .. slack s = -h(x) >= 0 of the convex rows and its multiplier
//!   rp, ru ... b - Ax, U - x - w;    rd .. c - A'y - z + v + Jh'lam;    rh .. -h(x) - s
//!   g ........ x'z + w'v + s'lam, the complementarity;  mu = sigma g / nb
//!   D ........ X^-1 Z + W^-1 V;   H .. Hh + Jh' (lam/s) Jh
//!
//! Each iteration solves the quasi-definite system (Vanderbei Ch. 19)
//!
//! ```text
//! [ -(H + D + dp I)   A'   ] [dx]   [rho]     rho = rd - X^-1 rxz + W^-1 (rwv - V ru)
//! [  A                dd I ] [dy] = [ rp]
//! ```
//!
//! by one sparse LDL' (ldl.rs). For an LP, H = 0
//! and the normal equations
//!
//! ```text
//! (A (D + dp I)^-1 A' + dd I) dy = rp + A (D + dp I)^-1 rho,    dx = (D + dp I)^-1 (A'dy - rho)
//! ```
//!
//! are positive definite, so their LDL' is stable in any order, while the quasi-definite one loses
//! accuracy as D spreads near the optimum. They are used unless their factor would hold more than
//! NE_FILL times the entries of the quasi-definite one (both counted once, from the symbolic
//! analysis), as dense columns of A make it. The centering parameter sigma is fixed; with convex
//! rows the primal and dual steps are common and backtrack on the residual merit. A direction that
//! is not finite ends the method as `numerical` at the last iterate, which is finite.

use crate::ldl::{Ldl, Lower, factor_nnz};
use std::time::Instant;

/// A sparse m x n matrix by compressed columns.
#[derive(Clone, Debug, Default)]
pub struct Csc {
    pub m: usize,
    pub n: usize,
    pub p: Vec<usize>,
    pub i: Vec<usize>,
    pub v: Vec<f64>,
}

impl Csc {
    /// A x.
    pub fn mul(&self, x: &[f64]) -> Vec<f64> {
        let mut y = vec![0.0; self.m];
        for j in 0..self.n {
            for k in self.p[j]..self.p[j + 1] {
                y[self.i[k]] += self.v[k] * x[j];
            }
        }
        y
    }

    /// A' y.
    pub fn tmul(&self, y: &[f64]) -> Vec<f64> {
        (0..self.n)
            .map(|j| {
                (self.p[j]..self.p[j + 1])
                    .map(|k| self.v[k] * y[self.i[k]])
                    .sum()
            })
            .collect()
    }
}

/// Entries (r, c, v) of a sparse matrix.
#[derive(Clone, Debug, Default)]
pub struct Trip {
    pub r: Vec<usize>,
    pub c: Vec<usize>,
    pub v: Vec<f64>,
}

impl Trip {
    /// (J' y)_c = sum_r J_rc y_r.
    fn tmul(&self, y: &[f64], n: usize) -> Vec<f64> {
        let mut out = vec![0.0; n];
        for k in 0..self.v.len() {
            out[self.c[k]] += self.v[k] * y[self.r[k]];
        }
        out
    }

    /// (J x)_r.
    fn mul(&self, x: &[f64], m: usize) -> Vec<f64> {
        let mut out = vec![0.0; m];
        for k in 0..self.v.len() {
            out[self.r[k]] += self.v[k] * x[self.c[k]];
        }
        out
    }
}

/// Convex rows h(x) <= 0 at the free x: values, Jacobian (one row per constraint), and the
/// Hessian of sum_k lam_k h_k, symmetric with both triangles given.
pub trait Convex {
    fn h(&mut self, x: &[f64]) -> Vec<f64>;
    fn jac(&mut self, x: &[f64]) -> Trip;
    fn hess(&mut self, x: &[f64], lam: &[f64]) -> Trip;
}

/// eps: tolerance of the stopping rule (A2); sigma: centering; eta: fraction to the boundary;
/// kmax: iteration limit; dp, dd: primal and dual regularization; time_limit: seconds.
#[derive(Clone, Copy, Debug)]
pub struct Opts {
    pub eps: f64,
    pub sigma: f64,
    pub eta: f64,
    pub kmax: usize,
    pub dp: f64,
    pub dd: f64,
    pub time_limit: f64,
}

impl Default for Opts {
    fn default() -> Opts {
        Opts {
            eps: 1e-8,
            sigma: 0.1,
            eta: 0.9995,
            kmax: 200,
            dp: 1e-10,
            dd: 1e-10,
            time_limit: f64::INFINITY,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Status {
    Optimal,
    Limit,
    Numerical,
}

/// The last iterate (x, y, lam), its status, the iteration count k, the residuals err (A2), and
/// whether the normal equations were factored.
#[derive(Clone, Debug)]
pub struct Out {
    pub x: Vec<f64>,
    pub y: Vec<f64>,
    pub lam: Vec<f64>,
    pub status: Status,
    pub k: usize,
    pub err: [f64; 3],
    pub normal: bool,
}

fn amax(v: &[f64]) -> f64 {
    v.iter().fold(0.0, |a, x| a.max(x.abs()))
}

fn dot(a: &[f64], b: &[f64]) -> f64 {
    a.iter().zip(b).map(|(x, y)| x * y).sum()
}

/// Largest t <= 1 with v + t dv >= (1 - eta) v, over the entries where on holds.
fn step(v: &[f64], dv: &[f64], on: &[bool], eta: f64) -> f64 {
    let mut t = f64::INFINITY;
    for k in 0..v.len() {
        if on[k] && dv[k] < 0.0 {
            t = t.min(-v[k] / dv[k]);
        }
    }
    (eta * t).min(1.0)
}

struct Point {
    x: Vec<f64>,
    w: Vec<f64>,
    y: Vec<f64>,
    z: Vec<f64>,
    v: Vec<f64>,
    sl: Vec<f64>,
    lam: Vec<f64>,
}

struct Resid {
    rp: Vec<f64>,
    ru: Vec<f64>,
    rd: Vec<f64>,
    rh: Vec<f64>,
    g: f64,
    jf: Trip,
}

impl Resid {
    fn merit(&self) -> f64 {
        amax(&self.rp) + amax(&self.ru) + amax(&self.rd) + amax(&self.rh) + self.g
    }
}

const NE_FILL: usize = 2;

/// The pattern of A A' + I (lower triangle) and, per pair of entries (e1, e2) sharing a column j,
/// the position its product a_e1 a_e2 / H_j adds to; None if A A' alone would hold more than 50
/// times the entries of A, where its factor cannot be small.
struct Normal {
    pattern: Lower,
    pairs: Vec<(usize, usize, usize, usize)>,
}

impl Normal {
    fn new(a: &Csc) -> Option<Normal> {
        let count: usize = (0..a.n)
            .map(|j| {
                let k = a.p[j + 1] - a.p[j];
                k * (k + 1) / 2
            })
            .sum();
        if count > 50 * (a.v.len() + a.m) {
            return None;
        }
        let (mut r, mut c) = ((0..a.m).collect::<Vec<_>>(), (0..a.m).collect::<Vec<_>>());
        for j in 0..a.n {
            for e1 in a.p[j]..a.p[j + 1] {
                for e2 in a.p[j]..=e1 {
                    r.push(a.i[e1].max(a.i[e2]));
                    c.push(a.i[e1].min(a.i[e2]));
                }
            }
        }
        let zero = vec![0.0; r.len()];
        let pattern = Lower::from_triplets(a.m, &r, &c, &zero);
        let at = |row: usize, col: usize| {
            let s = &pattern.i[pattern.p[col]..pattern.p[col + 1]];
            pattern.p[col] + s.binary_search(&row).unwrap()
        };
        let mut pairs = Vec::with_capacity(count);
        for j in 0..a.n {
            for e1 in a.p[j]..a.p[j + 1] {
                for e2 in a.p[j]..=e1 {
                    let (i1, i2) = (a.i[e1].max(a.i[e2]), a.i[e1].min(a.i[e2]));
                    pairs.push((j, e1, e2, at(i1, i2)));
                }
            }
        }
        Some(Normal { pattern, pairs })
    }

    /// A diag(hi) A' + dd I.
    fn matrix(&self, a: &Csc, hi: &[f64], dd: f64) -> Lower {
        let mut k = self.pattern.clone();
        for col in 0..k.n {
            let d = k.p[col] + k.i[k.p[col]..k.p[col + 1]].binary_search(&col).unwrap();
            k.v[d] = dd;
        }
        for &(j, e1, e2, at) in &self.pairs {
            k.v[at] += hi[j] * a.v[e1] * a.v[e2];
        }
        k
    }
}

/// The method of the module legend on (A, b, c, U), with f0 the objective's constant.
pub fn ipm(
    a: &Csc,
    b: &[f64],
    c: &[f64],
    u: &[f64],
    f0: f64,
    mut hc: Option<&mut dyn Convex>,
    o: Opts,
) -> Out {
    let t0 = Instant::now();
    let (m, n) = (a.m, a.n);
    let bf: Vec<bool> = u.iter().map(|x| x.is_finite()).collect();
    let all = vec![true; n];
    let nl = hc.is_some();
    let mut s = Point {
        x: (0..n)
            .map(|j| if bf[j] { u[j] / 2.0 } else { 1.0 })
            .collect(),
        w: vec![1.0; n],
        y: vec![0.0; m],
        z: vec![0.0; n],
        v: vec![0.0; n],
        sl: Vec::new(),
        lam: Vec::new(),
    };
    for j in 0..n {
        if bf[j] {
            s.w[j] = u[j] - s.x[j];
            s.v[j] = 1.0 / s.w[j];
        }
        s.z[j] = 1.0 / s.x[j];
    }
    if let Some(h) = hc.as_deref_mut() {
        s.sl = h.h(&s.x).iter().map(|e| (-e).max(1.0)).collect();
        s.lam = s.sl.iter().map(|e| 1.0 / e).collect();
    }
    let nb = ((n + bf.iter().filter(|&&f| f).count() + s.sl.len()) as f64).max(1.0);
    let bmax = amax(b);
    let cmax = amax(c);
    let mut status = Status::Limit;
    let mut err;
    let mut f: Option<Ldl> = None;
    let signs: Vec<i8> = (0..n + m).map(|k| if k < n { -1 } else { 1 }).collect();
    let ne = if nl {
        None
    } else {
        Normal::new(a).filter(|ne| {
            let (mut r, mut c) = (
                (0..n + m).collect::<Vec<_>>(),
                (0..n + m).collect::<Vec<_>>(),
            );
            for j in 0..n {
                for e in a.p[j]..a.p[j + 1] {
                    r.push(n + a.i[e]);
                    c.push(j);
                }
            }
            let k = Lower::from_triplets(n + m, &r, &c, &vec![1.0; r.len()]);
            factor_nnz(&ne.pattern) <= NE_FILL * factor_nnz(&k)
        })
    };
    let ne_signs = vec![1i8; m];

    let resid = |p: &Point, hc: &mut Option<&mut dyn Convex>| -> Resid {
        let ax = a.mul(&p.x);
        let rp: Vec<f64> = (0..m).map(|r| b[r] - ax[r]).collect();
        let ru: Vec<f64> = (0..n)
            .map(|j| if bf[j] { u[j] - p.x[j] - p.w[j] } else { 0.0 })
            .collect();
        let aty = a.tmul(&p.y);
        let mut rd: Vec<f64> = (0..n).map(|j| c[j] - aty[j] - p.z[j] + p.v[j]).collect();
        let (mut rh, mut jf) = (Vec::new(), Trip::default());
        if let Some(h) = hc.as_deref_mut() {
            jf = h.jac(&p.x);
            for (j, e) in jf.tmul(&p.lam, n).into_iter().enumerate() {
                rd[j] += e;
            }
            rh = h.h(&p.x).iter().zip(&p.sl).map(|(e, s)| -e - s).collect();
        }
        let mut g = dot(&p.x, &p.z) + dot(&p.sl, &p.lam);
        for j in 0..n {
            if bf[j] {
                g += p.w[j] * p.v[j];
            }
        }
        Resid {
            rp,
            ru,
            rd,
            rh,
            g,
            jf,
        }
    };

    let mut k = 0;
    loop {
        let r = resid(&s, &mut hc);
        let pobj = f0 + dot(c, &s.x);
        let mut eu: f64 = 0.0;
        for j in 0..n {
            if bf[j] {
                eu = eu.max(r.ru[j].abs() / (1.0 + u[j]));
            }
        }
        let xsum: f64 = s.x.iter().map(|x| x.abs()).sum();
        err = [
            (amax(&r.rp) / (1.0 + bmax))
                .max(eu)
                .max(amax(&r.rh) / (1.0 + amax(&s.sl))),
            amax(&r.rd) * (1.0 / (1.0 + cmax)).max(xsum / (1.0 + pobj.abs())),
            r.g / (1.0 + pobj.abs()),
        ];
        if err.iter().all(|&e| e <= o.eps) {
            status = Status::Optimal;
            break;
        }
        if !r.g.is_finite() || amax(&s.x).max(amax(&s.y)) > 1e14 {
            status = Status::Numerical;
            break;
        }
        if k == o.kmax || t0.elapsed().as_secs_f64() > o.time_limit {
            break;
        }
        let wi: Vec<f64> = (0..n)
            .map(|j| if bf[j] { 1.0 / s.w[j] } else { 0.0 })
            .collect();
        let dg: Vec<f64> = (0..n).map(|j| s.z[j] / s.x[j] + wi[j] * s.v[j]).collect();

        let hi: Vec<f64> = dg.iter().map(|d| 1.0 / (d + o.dp)).collect();
        // K, lower triangle: -(Hh + Jh'(lam/s)Jh + D + dp I) | A | dd I.
        let (mut tr, mut tc, mut tv) = (Vec::new(), Vec::new(), Vec::new());
        let mut put = |i: usize, j: usize, x: f64| {
            tr.push(i);
            tc.push(j);
            tv.push(x);
        };
        if ne.is_none() {
            for j in 0..n {
                put(j, j, -(dg[j] + o.dp));
                for e in a.p[j]..a.p[j + 1] {
                    put(n + a.i[e], j, a.v[e]);
                }
            }
            for rr in 0..m {
                put(n + rr, n + rr, o.dd);
            }
        }
        let mut rsl = Vec::new();
        if let Some(h) = hc.as_deref_mut() {
            let hh = h.hess(&s.x, &s.lam);
            for e in 0..hh.v.len() {
                if hh.r[e] >= hh.c[e] {
                    put(hh.r[e], hh.c[e], -hh.v[e]);
                }
            }
            let mut rows: Vec<Vec<(usize, f64)>> = vec![Vec::new(); s.sl.len()];
            for e in 0..r.jf.v.len() {
                rows[r.jf.r[e]].push((r.jf.c[e], r.jf.v[e]));
            }
            for (kk, row) in rows.iter().enumerate() {
                let wgt = s.lam[kk] / s.sl[kk];
                for &(ca, va) in row {
                    for &(cb, vb) in row {
                        if ca >= cb {
                            put(ca, cb, -wgt * va * vb);
                        }
                    }
                }
            }
            rsl = (0..s.sl.len())
                .map(|kk| o.sigma * r.g / nb - s.sl[kk] * s.lam[kk])
                .collect();
        }
        let kmat = match &ne {
            Some(ne) => ne.matrix(a, &hi, o.dd),
            None => Lower::from_triplets(n + m, &tr, &tc, &tv),
        };
        let ok = match f.as_mut() {
            Some(f) => f.factor(kmat),
            None => {
                f = match ne {
                    Some(_) => Ldl::new(kmat, ne_signs.clone(), 1e-30, 1e128),
                    None => Ldl::new(kmat, signs.clone(), 1e-13, 1e-8),
                };
                f.is_some()
            }
        };
        if !ok {
            status = Status::Numerical;
            break;
        }
        let fac = f.as_ref().unwrap();

        // The direction for the complementarity targets rxz = mu e - XZe, rwv = mu e - WVe.
        let direction = |rxz: &[f64], rwv: &[f64]| {
            let mut rhs: Vec<f64> = (0..n)
                .map(|j| r.rd[j] - rxz[j] / s.x[j] + wi[j] * (rwv[j] - s.v[j] * r.ru[j]))
                .collect();
            if nl {
                let e: Vec<f64> = (0..s.sl.len())
                    .map(|kk| (rsl[kk] - s.lam[kk] * r.rh[kk]) / s.sl[kk])
                    .collect();
                for (j, x) in r.jf.tmul(&e, n).into_iter().enumerate() {
                    rhs[j] += x;
                }
            }
            let (dx, dy) = if ne.is_some() {
                let ahr = a.mul(&(0..n).map(|j| hi[j] * rhs[j]).collect::<Vec<_>>());
                let dy = fac.solve(&(0..m).map(|i| r.rp[i] + ahr[i]).collect::<Vec<_>>());
                let aty = a.tmul(&dy);
                (
                    (0..n)
                        .map(|j| hi[j] * (aty[j] - rhs[j]))
                        .collect::<Vec<_>>(),
                    dy,
                )
            } else {
                rhs.extend_from_slice(&r.rp);
                let d = fac.solve(&rhs);
                (d[..n].to_vec(), d[n..].to_vec())
            };
            let dz: Vec<f64> = (0..n).map(|j| (rxz[j] - s.z[j] * dx[j]) / s.x[j]).collect();
            let dw: Vec<f64> = (0..n)
                .map(|j| if bf[j] { r.ru[j] - dx[j] } else { 0.0 })
                .collect();
            let dv: Vec<f64> = (0..n).map(|j| wi[j] * (rwv[j] - s.v[j] * dw[j])).collect();
            (dx, dy, dz, dw, dv)
        };
        let mu = o.sigma * r.g / nb;
        let rxz: Vec<f64> = (0..n).map(|j| mu - s.x[j] * s.z[j]).collect();
        let rwv: Vec<f64> = (0..n)
            .map(|j| if bf[j] { mu - s.w[j] * s.v[j] } else { 0.0 })
            .collect();
        let (dx, dy, dz, dw, dv) = direction(&rxz, &rwv);
        let mut tp = step(&s.x, &dx, &all, o.eta).min(step(&s.w, &dw, &bf, o.eta));
        let mut td = step(&s.z, &dz, &all, o.eta).min(step(&s.v, &dv, &bf, o.eta));
        let (mut ds, mut dl) = (Vec::new(), Vec::new());
        if nl {
            let jdx = r.jf.mul(&dx, s.sl.len());
            ds = (0..s.sl.len()).map(|kk| r.rh[kk] - jdx[kk]).collect();
            dl = (0..s.sl.len())
                .map(|kk| (rsl[kk] - s.lam[kk] * ds[kk]) / s.sl[kk])
                .collect();
            let on = vec![true; s.sl.len()];
            tp = tp.min(step(&s.sl, &ds, &on, o.eta));
            td = td.min(step(&s.lam, &dl, &on, o.eta));
        }
        if nl {
            tp = tp.min(td);
            td = tp;
        }
        let at = |tp: f64, td: f64| Point {
            x: (0..n).map(|j| s.x[j] + tp * dx[j]).collect(),
            w: (0..n)
                .map(|j| if bf[j] { s.w[j] + tp * dw[j] } else { 1.0 })
                .collect(),
            y: (0..m).map(|i| s.y[i] + td * dy[i]).collect(),
            z: (0..n).map(|j| s.z[j] + td * dz[j]).collect(),
            v: (0..n)
                .map(|j| if bf[j] { s.v[j] + td * dv[j] } else { 0.0 })
                .collect(),
            sl: (0..ds.len()).map(|kk| s.sl[kk] + tp * ds[kk]).collect(),
            lam: (0..dl.len()).map(|kk| s.lam[kk] + td * dl[kk]).collect(),
        };
        let mut next = at(tp, td);
        if nl {
            // Backtrack on the residual merit.
            let m0 = r.merit();
            while tp > 1e-12 {
                if resid(&next, &mut hc).merit() <= (1.0 - 1e-4 * tp) * m0 {
                    break;
                }
                tp /= 2.0;
                next = at(tp, tp);
            }
        }
        let finite = |v: &[f64]| v.iter().all(|x| x.is_finite());
        if ![
            &next.x, &next.w, &next.y, &next.z, &next.v, &next.sl, &next.lam,
        ]
        .iter()
        .all(|v| finite(v))
        {
            status = Status::Numerical; // the last finite iterate is returned
            break;
        }
        s = next;
        k += 1;
    }
    Out {
        x: s.x,
        y: s.y,
        lam: s.lam,
        status,
        k,
        err,
        normal: ne.is_some(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn csc(m: usize, n: usize, d: &[f64]) -> Csc {
        let (mut p, mut i, mut v) = (vec![0], Vec::new(), Vec::new());
        for j in 0..n {
            for r in 0..m {
                if d[r * n + j] != 0.0 {
                    i.push(r);
                    v.push(d[r * n + j]);
                }
            }
            p.push(i.len());
        }
        Csc { m, n, p, i, v }
    }

    #[test]
    fn small_lp() {
        // min -x1 - 2x2  s.t.  x1 + x2 + s = 4,  x1 <= 3, x2 <= 2:  x* = (2, 2), f* = -6.
        let a = csc(1, 3, &[1.0, 1.0, 1.0]);
        let o = ipm(
            &a,
            &[4.0],
            &[-1.0, -2.0, 0.0],
            &[3.0, 2.0, f64::INFINITY],
            0.0,
            None,
            Opts::default(),
        );
        assert_eq!(o.status, Status::Optimal);
        assert!(o.normal);
        assert!((o.x[0] - 2.0).abs() < 1e-6 && (o.x[1] - 2.0).abs() < 1e-6);
    }

    struct Disc;

    impl Convex for Disc {
        fn h(&mut self, x: &[f64]) -> Vec<f64> {
            vec![x[0] * x[0] + x[1] * x[1] - 1.0]
        }
        fn jac(&mut self, x: &[f64]) -> Trip {
            Trip {
                r: vec![0, 0],
                c: vec![0, 1],
                v: vec![2.0 * x[0], 2.0 * x[1]],
            }
        }
        fn hess(&mut self, _: &[f64], lam: &[f64]) -> Trip {
            Trip {
                r: vec![0, 1],
                c: vec![0, 1],
                v: vec![2.0 * lam[0], 2.0 * lam[0]],
            }
        }
    }

    #[test]
    fn disc() {
        // min -x1 - x2 s.t. x1^2 + x2^2 <= 1, 0 <= x <= 2: f* = -sqrt 2.
        let a = Csc {
            m: 0,
            n: 2,
            p: vec![0; 3],
            ..Default::default()
        };
        let mut h = Disc;
        let o = ipm(
            &a,
            &[],
            &[-1.0, -1.0],
            &[2.0, 2.0],
            0.0,
            Some(&mut h),
            Opts::default(),
        );
        assert_eq!(o.status, Status::Optimal);
        assert!((o.x[0] + o.x[1] - 2f64.sqrt()).abs() < 1e-6);
    }
}
