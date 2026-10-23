//! Sparse rows lo <= A v <= hi, accumulated one at a time: the plumbing every formulation shares.
//!
//! Legend
//!   r, c, v .. row, column, value of each entry     lo, hi .. row bounds (±inf when open)

use efo_highs::Csc;

pub const INF: f64 = f64::INFINITY;

#[derive(Clone, Debug, Default)]
pub struct Rows {
    pub r: Vec<usize>,
    pub c: Vec<usize>,
    pub v: Vec<f64>,
    pub lo: Vec<f64>,
    pub hi: Vec<f64>,
}

impl Rows {
    pub fn new() -> Rows {
        Rows::default()
    }

    /// One row sum_k vals_k v_{cols_k} in [lo, hi].
    pub fn add(&mut self, cols: &[usize], vals: &[f64], lo: f64, hi: f64) {
        debug_assert_eq!(cols.len(), vals.len());
        let k = self.lo.len();
        self.r.extend(std::iter::repeat_n(k, cols.len()));
        self.c.extend_from_slice(cols);
        self.v.extend_from_slice(vals);
        self.lo.push(lo);
        self.hi.push(hi);
    }

    pub fn len(&self) -> usize {
        self.lo.len()
    }

    pub fn is_empty(&self) -> bool {
        self.lo.is_empty()
    }

    /// The matrix over n columns, as SciPy builds `csr_array((v, (r, c)))`.
    pub fn a(&self, n: usize) -> Csc {
        Csc::from_triplets(self.lo.len(), n, &self.r, &self.c, &self.v)
    }
}

/// HiGHS termination as the reference names it: a limit without an incumbent is no_incumbent.
pub fn status(st: i32, has_x: bool) -> &'static str {
    let s = match st {
        0 => "optimal",
        1 => "feasible_limit",
        2 => "infeasible",
        3 => "unbounded",
        _ => "numerical",
    };
    if s == "feasible_limit" && !has_x {
        "no_incumbent"
    } else {
        s
    }
}
