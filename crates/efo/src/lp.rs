//! Mixed-integer linear programs on sparse ranged rows, solved by HiGHS.
//!
//! ```text
//! min c'x   s.t.   lo <= A x <= hi,   l <= x <= u,   x_j integer where int_j
//! ```
//!
//! Every formulation writes its rows here once; the barrier method (barrier.rs) reads the same
//! data. A solve reports HiGHS's own termination as a value (Algorithms §6): a bound is HiGHS's
//! MIP dual bound, never the incumbent.

use highs::{HighsModelStatus, HighsSolutionStatus, RowProblem, Sense};

/// One row lo <= sum a_j x_j <= hi; a column may repeat, its coefficients are summed.
#[derive(Clone, Debug)]
pub struct Row {
    pub a: Vec<(usize, f64)>,
    pub lo: f64,
    pub hi: f64,
}

#[derive(Clone, Debug, Default)]
pub struct Lp {
    pub c: Vec<f64>,
    pub l: Vec<f64>,
    pub u: Vec<f64>,
    pub int: Vec<bool>,
    pub rows: Vec<Row>,
}

/// status: optimal, feasible_limit, no_incumbent, infeasible, unbounded or numerical; x and f an
/// incumbent that satisfies the rows within 1e-5; bound HiGHS's dual bound (MIP) or the optimum
/// (LP); y the row duals of an LP, d(f)/d(side).
#[derive(Clone, Debug)]
pub struct Solve {
    pub status: &'static str,
    pub x: Option<Vec<f64>>,
    pub f: Option<f64>,
    pub bound: Option<f64>,
    pub y: Vec<f64>,
    pub nodes: Option<i64>,
}

impl Lp {
    /// A column with cost c on [l, u]; its index.
    pub fn var(&mut self, c: f64, l: f64, u: f64, int: bool) -> usize {
        self.c.push(c);
        self.l.push(l);
        self.u.push(u);
        self.int.push(int);
        self.c.len() - 1
    }

    /// k columns alike; the first index.
    pub fn vars(&mut self, k: usize, c: f64, l: f64, u: f64, int: bool) -> usize {
        let first = self.c.len();
        for _ in 0..k {
            self.var(c, l, u, int);
        }
        first
    }

    pub fn row(&mut self, a: Vec<(usize, f64)>, lo: f64, hi: f64) {
        self.rows.push(Row { a, lo, hi });
    }

    /// a'x >= lo.
    pub fn ge(&mut self, a: Vec<(usize, f64)>, lo: f64) {
        self.row(a, lo, f64::INFINITY);
    }

    /// a'x <= hi.
    pub fn le(&mut self, a: Vec<(usize, f64)>, hi: f64) {
        self.row(a, f64::NEG_INFINITY, hi);
    }

    pub fn eq(&mut self, a: Vec<(usize, f64)>, b: f64) {
        self.row(a, b, b);
    }

    pub fn n(&self) -> usize {
        self.c.len()
    }

    pub fn value(&self, x: &[f64]) -> f64 {
        self.c.iter().zip(x).map(|(c, x)| c * x).sum()
    }

    /// x satisfies rows and bounds within eps (1 + |side|) and is integral where required.
    pub fn feasible(&self, x: &[f64], eps: f64) -> bool {
        let near = |a: f64, b: f64| a <= b + eps * (1.0 + b.abs());
        x.len() == self.n()
            && (0..self.n()).all(|j| {
                x[j].is_finite()
                    && near(self.l[j], x[j])
                    && near(x[j], self.u[j])
                    && (!self.int[j] || (x[j] - x[j].round()).abs() <= eps)
            })
            && self.rows.iter().all(|r| {
                let ax: f64 = r.a.iter().map(|&(j, v)| v * x[j]).sum();
                near(r.lo, ax) && near(ax, r.hi)
            })
    }

    /// HiGHS on the program, single-threaded, within time seconds and relative MIP gap gap.
    pub fn solve(&self, time: f64, gap: f64) -> Solve {
        let fail = |status| Solve {
            status,
            x: None,
            f: None,
            bound: None,
            y: Vec::new(),
            nodes: None,
        };
        if (0..self.n()).any(|j| self.l[j] > self.u[j]) || self.rows.iter().any(|r| r.lo > r.hi) {
            return fail("infeasible");
        }
        let mut p = RowProblem::new();
        let cols: Vec<_> = (0..self.n())
            .map(|j| p.add_column_with_integrality(self.c[j], self.l[j]..=self.u[j], self.int[j]))
            .collect();
        for r in &self.rows {
            let mut a = r.a.clone();
            a.sort_by_key(|e| e.0);
            a.dedup_by(|e, kept| {
                let same = e.0 == kept.0;
                if same {
                    kept.1 += e.1;
                }
                same
            });
            p.add_row(
                r.lo..=r.hi,
                a.into_iter()
                    .filter(|e| e.1 != 0.0)
                    .map(|(j, v)| (cols[j], v)),
            );
        }
        let Ok(mut model) = p.try_optimise(Sense::Minimise) else {
            return fail("numerical");
        };
        model.make_quiet();
        model.set_option("time_limit", time.max(1e-3));
        model.set_option("mip_rel_gap", gap);
        let Ok(s) = model.try_solve() else {
            return fail("numerical");
        };
        let mip = self.int.iter().any(|&b| b);
        let sol = s.get_solution();
        let x = sol.columns().to_vec();
        let has =
            s.primal_solution_status() == HighsSolutionStatus::Feasible && self.feasible(&x, 1e-5);
        let status = match s.status() {
            HighsModelStatus::Optimal if has => "optimal",
            HighsModelStatus::Infeasible => "infeasible",
            HighsModelStatus::Unbounded | HighsModelStatus::UnboundedOrInfeasible => "unbounded",
            HighsModelStatus::ReachedTimeLimit
            | HighsModelStatus::ReachedIterationLimit
            | HighsModelStatus::ReachedSolutionLimit => {
                if has {
                    "feasible_limit"
                } else {
                    "no_incumbent"
                }
            }
            _ => "numerical",
        };
        let bound = match status {
            "optimal" | "feasible_limit" | "no_incumbent" if mip => s
                .double_info_value(c"mip_dual_bound")
                .ok()
                .filter(|b| b.is_finite()),
            "optimal" => Some(s.objective_value()),
            _ => None,
        };
        Solve {
            status,
            f: has.then(|| self.value(&x)),
            bound,
            y: if !mip && has {
                sol.dual_rows().to_vec()
            } else {
                Vec::new()
            },
            nodes: mip
                .then(|| s.int_info_value(c"mip_node_count").ok())
                .flatten(),
            x: has.then_some(x),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn integer_bound_and_infeasibility() {
        let mut p = Lp::default();
        let x = p.var(1.0, 0.0, 3.0, true);
        p.ge(vec![(x, 1.0)], 1.5);
        let s = p.solve(10.0, 0.0);
        assert_eq!((s.status, s.f, s.bound), ("optimal", Some(2.0), Some(2.0)));
        p.le(vec![(x, 1.0)], 1.0);
        assert_eq!(p.solve(10.0, 0.0).status, "infeasible");
    }

    #[test]
    fn repeated_terms_and_duals() {
        // min 7x s.t. 2x - x = 3, and min x s.t. x >= 2: duals 7 and 1 (d f / d side).
        let mut p = Lp::default();
        let x = p.var(7.0, f64::NEG_INFINITY, f64::INFINITY, false);
        p.eq(vec![(x, 2.0), (x, -1.0)], 3.0);
        let s = p.solve(10.0, 0.0);
        assert_eq!(s.f, Some(21.0));
        assert!((s.y[0] - 7.0).abs() < 1e-9);
        let mut q = Lp::default();
        let x = q.var(1.0, 0.0, f64::INFINITY, false);
        q.ge(vec![(x, 1.0)], 2.0);
        assert!((q.solve(10.0, 0.0).y[0] - 1.0).abs() < 1e-9);
    }
}
