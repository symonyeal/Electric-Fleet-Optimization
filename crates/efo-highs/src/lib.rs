//! HiGHS 1.12.0 behind the two SciPy entry points the Python reference uses.
//!
//! Legend
//!   A ....... constraint matrix, compressed by column (p: column starts, i: row indices, v: values)
//!   c ....... objective, minimised
//!   l, u .... column bounds          lo, hi .. row bounds, lo <= A v <= hi
//!   integ ... 1 on integer columns   x ....... primal solution
//!   y ....... row duals (HiGHS sign) z ....... column duals
//!   ms ...... HiGHS model status     st ...... SciPy status: 0 optimal, 1 limit, 2 infeasible,
//!                                              3 unbounded, 4 other
//!
//! `milp` and `linprog` reproduce what `scipy.optimize.milp` and `linprog(method="highs-*")` hand
//! to HiGHS: CSC arrays, options and result rules. Full solver parity remains to be measured.

use std::ffi::{CString, c_char, c_void};

type Hi = i32;

unsafe extern "C" {
    fn Highs_create() -> *mut c_void;
    fn Highs_destroy(h: *mut c_void);
    fn Highs_version() -> *const c_char;
    fn Highs_passModel(
        h: *mut c_void,
        n: Hi,
        m: Hi,
        nnz: Hi,
        q_nnz: Hi,
        a_format: Hi,
        q_format: Hi,
        sense: Hi,
        offset: f64,
        c: *const f64,
        l: *const f64,
        u: *const f64,
        lo: *const f64,
        hi: *const f64,
        p: *const Hi,
        i: *const Hi,
        v: *const f64,
        qp: *const Hi,
        qi: *const Hi,
        qv: *const f64,
        integ: *const Hi,
    ) -> Hi;
    fn Highs_setBoolOptionValue(h: *mut c_void, k: *const c_char, v: Hi) -> Hi;
    fn Highs_setIntOptionValue(h: *mut c_void, k: *const c_char, v: Hi) -> Hi;
    fn Highs_setDoubleOptionValue(h: *mut c_void, k: *const c_char, v: f64) -> Hi;
    fn Highs_setStringOptionValue(h: *mut c_void, k: *const c_char, v: *const c_char) -> Hi;
    fn Highs_run(h: *mut c_void) -> Hi;
    fn Highs_getModelStatus(h: *const c_void) -> Hi;
    fn Highs_getSolution(
        h: *const c_void,
        x: *mut f64,
        z: *mut f64,
        r: *mut f64,
        y: *mut f64,
    ) -> Hi;
    fn Highs_getIntInfoValue(h: *const c_void, k: *const c_char, v: *mut Hi) -> Hi;
    fn Highs_getInt64InfoValue(h: *const c_void, k: *const c_char, v: *mut i64) -> Hi;
    fn Highs_getDoubleInfoValue(h: *const c_void, k: *const c_char, v: *mut f64) -> Hi;
}

const OPTIMAL: Hi = 7;
const TIME_LIMIT: Hi = 13;
const ITER_LIMIT: Hi = 14;
const SOL_LIMIT: Hi = 16;

/// The linked HiGHS version, e.g. "1.12.0".
pub fn version() -> String {
    // SAFETY: Highs_version returns a static NUL-terminated string.
    unsafe { std::ffi::CStr::from_ptr(Highs_version()) }
        .to_string_lossy()
        .into_owned()
}

/// A sparse matrix by column, as HiGHS takes it.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Csc {
    pub m: usize,
    pub n: usize,
    pub p: Vec<Hi>,
    pub i: Vec<Hi>,
    pub v: Vec<f64>,
}

impl Csc {
    /// SciPy's `csr_array((v, (r, c)), shape=(m, n))` followed by `tocsc()`: duplicates are summed
    /// after each row is sorted by (column, value), as `csr_sort_indices` does, and kept zeros stay.
    pub fn from_triplets(m: usize, n: usize, r: &[usize], c: &[usize], v: &[f64]) -> Csc {
        let mut rows: Vec<Vec<(usize, f64)>> = vec![Vec::new(); m];
        for k in 0..r.len() {
            rows[r[k]].push((c[k], v[k]));
        }
        let mut cnt = vec![0usize; n];
        for row in rows.iter_mut() {
            row.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.total_cmp(&b.1)));
            let mut out: Vec<(usize, f64)> = Vec::with_capacity(row.len());
            for &(j, x) in row.iter() {
                match out.last_mut() {
                    Some(last) if last.0 == j => last.1 += x,
                    _ => out.push((j, x)),
                }
            }
            for &(j, _) in &out {
                cnt[j] += 1;
            }
            *row = out;
        }
        let mut p = vec![0 as Hi; n + 1];
        for j in 0..n {
            p[j + 1] = p[j] + cnt[j] as Hi;
        }
        let nnz = p[n] as usize;
        let mut i = vec![0 as Hi; nnz];
        let mut vv = vec![0.0; nnz];
        let mut at: Vec<usize> = p[..n].iter().map(|&s| s as usize).collect();
        for (ri, row) in rows.iter().enumerate() {
            for &(j, x) in row {
                i[at[j]] = ri as Hi;
                vv[at[j]] = x;
                at[j] += 1;
            }
        }
        Csc { m, n, p, i, v: vv }
    }

    /// Rows of `a` above rows of `b` (`scipy.sparse.vstack`).
    pub fn vstack(a: &Csc, b: &Csc) -> Csc {
        assert_eq!(a.n, b.n);
        let n = a.n;
        let mut p = vec![0 as Hi; n + 1];
        let mut i = Vec::with_capacity(a.i.len() + b.i.len());
        let mut v = Vec::with_capacity(a.v.len() + b.v.len());
        for j in 0..n {
            for k in a.p[j] as usize..a.p[j + 1] as usize {
                i.push(a.i[k]);
                v.push(a.v[k]);
            }
            for k in b.p[j] as usize..b.p[j + 1] as usize {
                i.push(b.i[k] + a.m as Hi);
                v.push(b.v[k]);
            }
            p[j + 1] = i.len() as Hi;
        }
        Csc {
            m: a.m + b.m,
            n,
            p,
            i,
            v,
        }
    }

    /// A v.
    pub fn mul(&self, x: &[f64]) -> Vec<f64> {
        let mut y = vec![0.0; self.m];
        for j in 0..self.n {
            for k in self.p[j] as usize..self.p[j + 1] as usize {
                y[self.i[k] as usize] += self.v[k] * x[j];
            }
        }
        y
    }
}

/// One HiGHS option, set by name exactly as SciPy sets it.
#[derive(Clone, Debug)]
pub enum Opt {
    B(&'static str, bool),
    I(&'static str, i32),
    F(&'static str, f64),
    S(&'static str, &'static str),
}

/// What SciPy returns from one HiGHS call.
#[derive(Clone, Debug, Default)]
pub struct Res {
    pub st: i32,
    pub ms: i32,
    pub message: String,
    pub x: Option<Vec<f64>>,
    pub fun: Option<f64>,
    pub y: Option<Vec<f64>>,
    pub z: Option<Vec<f64>>,
    pub dual_bound: Option<f64>,
    pub gap: Option<f64>,
    pub nodes: Option<i64>,
}

fn model_status(ms: Hi) -> &'static str {
    match ms {
        0 => "Not Set",
        1 => "Load error",
        2 => "Model error",
        3 => "Presolve error",
        4 => "Solve error",
        5 => "Postsolve error",
        6 => "Empty",
        7 => "Optimal",
        8 => "Infeasible",
        9 => "Primal infeasible or unbounded",
        10 => "Unbounded",
        11 => "Bound on objective reached",
        12 => "Target for objective reached",
        13 => "Time limit reached",
        14 => "Iteration limit reached",
        15 => "Unknown",
        16 => "Solution limit reached",
        17 => "Interrupted by user",
        18 => "Memory limit reached",
        19 => "Interrupted by HiGHS",
        _ => "Unrecognised HiGHS model status",
    }
}

fn solution_status(s: Hi) -> &'static str {
    match s {
        0 => "None",
        1 => "Infeasible",
        2 => "Feasible",
        _ => "Unrecognised solution status",
    }
}

/// `_highs_to_scipy_status_message`.
fn scipy(ms: Hi, msg: &str) -> (i32, String) {
    let (st, head) = match ms {
        7 => (0, "Optimization terminated successfully. "),
        13 => (1, "Time limit reached. "),
        14 => (1, "Iteration limit reached. "),
        8 => (2, "The problem is infeasible. "),
        10 => (3, "The problem is unbounded. "),
        9 => (4, "The problem is unbounded or infeasible. "),
        2 => (2, ""),
        0 | 1 | 3..=6 | 11 | 12 => (4, ""),
        _ => (4, "The HiGHS status code was not recognized. "),
    };
    (st, format!("{head}(HiGHS Status {ms}: {msg})"))
}

struct H(*mut c_void);

impl Drop for H {
    fn drop(&mut self) {
        // SAFETY: created by Highs_create and destroyed once.
        unsafe { Highs_destroy(self.0) }
    }
}

impl H {
    fn opt(&self, o: &Opt) {
        // SAFETY: the handle is live and every string is NUL-terminated for the call.
        unsafe {
            match o {
                Opt::B(k, v) => {
                    let k = CString::new(*k).unwrap();
                    Highs_setBoolOptionValue(self.0, k.as_ptr(), *v as Hi);
                }
                Opt::I(k, v) => {
                    let k = CString::new(*k).unwrap();
                    Highs_setIntOptionValue(self.0, k.as_ptr(), *v);
                }
                Opt::F(k, v) => {
                    let k = CString::new(*k).unwrap();
                    Highs_setDoubleOptionValue(self.0, k.as_ptr(), *v);
                }
                Opt::S(k, v) => {
                    let (k, v) = (CString::new(*k).unwrap(), CString::new(*v).unwrap());
                    Highs_setStringOptionValue(self.0, k.as_ptr(), v.as_ptr());
                }
            }
        }
    }

    fn info_f(&self, k: &str) -> f64 {
        let k = CString::new(k).unwrap();
        let mut v = 0.0;
        // SAFETY: live handle, valid out pointer.
        unsafe { Highs_getDoubleInfoValue(self.0, k.as_ptr(), &mut v) };
        v
    }

    fn info_i(&self, k: &str) -> i64 {
        let k = CString::new(k).unwrap();
        let mut v: Hi = 0;
        // SAFETY: live handle, valid out pointer.
        unsafe { Highs_getIntInfoValue(self.0, k.as_ptr(), &mut v) };
        v as i64
    }

    fn info_l(&self, k: &str) -> i64 {
        let k = CString::new(k).unwrap();
        let mut v: i64 = 0;
        // SAFETY: live handle, valid out pointer.
        unsafe { Highs_getInt64InfoValue(self.0, k.as_ptr(), &mut v) };
        v
    }
}

/// `_highs_wrapper`: min c'v, lo <= A v <= hi, l <= v <= u, integrality `integ` (None for an LP).
pub fn solve(
    c: &[f64],
    a: &Csc,
    lo: &[f64],
    hi: &[f64],
    l: &[f64],
    u: &[f64],
    integ: Option<&[u8]>,
    opts: &[Opt],
) -> Res {
    let (n, m) = (c.len(), lo.len());
    assert!(a.n == n && a.m == m && hi.len() == m && l.len() == n && u.len() == n);
    // The public Csc fields are caller-controlled. Validate before C++ reads any pointer.
    assert!(n <= Hi::MAX as usize && m <= Hi::MAX as usize && a.v.len() <= Hi::MAX as usize);
    assert!(
        a.p.len() == n + 1
            && a.p.first() == Some(&0)
            && a.p.last() == Some(&(a.v.len() as Hi))
            && a.p.windows(2).all(|w| w[0] >= 0 && w[0] <= w[1]),
        "invalid CSC column pointers"
    );
    assert!(
        a.i.len() == a.v.len() && a.i.iter().all(|&i| i >= 0 && (i as usize) < m),
        "invalid CSC row indices"
    );
    assert!(
        integ.is_none_or(|g| g.len() == n && g.iter().all(|&k| k <= 4)),
        "invalid integrality array"
    );
    // SAFETY: Highs_create returns an owned handle, released by H's Drop.
    let h = H(unsafe { Highs_create() });
    assert!(!h.0.is_null(), "HiGHS allocation failed");
    h.opt(&Opt::B("output_flag", false));
    h.opt(&Opt::B("log_to_console", false));
    for o in opts {
        h.opt(o);
    }
    let mip = integ.is_some_and(|g| g.iter().any(|&k| k != 0));
    let ig: Option<Vec<Hi>> = integ.map(|g| g.iter().map(|&k| k as Hi).collect());
    // SAFETY: every array outlives the call and has the length HiGHS reads.
    let st = unsafe {
        Highs_passModel(
            h.0,
            n as Hi,
            m as Hi,
            a.v.len() as Hi,
            0,
            1,
            0,
            1,
            0.0,
            c.as_ptr(),
            l.as_ptr(),
            u.as_ptr(),
            lo.as_ptr(),
            hi.as_ptr(),
            a.p.as_ptr(),
            a.i.as_ptr(),
            a.v.as_ptr(),
            std::ptr::null(),
            std::ptr::null(),
            std::ptr::null(),
            ig.as_ref().map_or(std::ptr::null(), |g| g.as_ptr()),
        )
    };
    let mut r = Res::default();
    if st == -1 {
        r.ms = 2;
        (r.st, r.message) = scipy(2, model_status(2));
        return r;
    }
    // SAFETY: live handle.
    let run = unsafe { Highs_run(h.0) };
    // SAFETY: live handle.
    let ms = unsafe { Highs_getModelStatus(h.0) };
    r.ms = ms;
    if run == -1 {
        (r.st, r.message) = scipy(ms, model_status(ms));
        return r;
    }
    let obj = h.info_f("objective_function_value");
    let limit = matches!(ms, TIME_LIMIT | ITER_LIMIT | SOL_LIMIT);
    let fail = if mip {
        !(ms == OPTIMAL || limit) || (limit && obj == f64::INFINITY)
    } else {
        ms != OPTIMAL
    };
    if fail {
        let ps = h.info_i("primal_solution_status") as Hi;
        let msg = format!(
            "model_status is {}; primal_status is {}",
            model_status(ms),
            solution_status(ps)
        );
        (r.st, r.message) = scipy(ms, &msg);
        return r;
    }
    let (mut x, mut z, mut rv, mut y) = (vec![0.0; n], vec![0.0; n], vec![0.0; m], vec![0.0; m]);
    // SAFETY: live handle, arrays sized to the model.
    unsafe {
        Highs_getSolution(
            h.0,
            x.as_mut_ptr(),
            z.as_mut_ptr(),
            rv.as_mut_ptr(),
            y.as_mut_ptr(),
        )
    };
    (r.st, r.message) = scipy(ms, model_status(ms));
    r.x = Some(x);
    r.fun = Some(obj);
    r.y = Some(y);
    r.z = Some(z);
    if mip {
        r.nodes = Some(h.info_l("mip_node_count"));
        r.dual_bound = Some(h.info_f("mip_dual_bound"));
        r.gap = Some(h.info_f("mip_gap"));
    }
    r
}

/// `scipy.optimize.milp(c, constraints, integrality, bounds, options=dict(time_limit, mip_rel_gap))`.
pub fn milp(
    c: &[f64],
    a: &Csc,
    lo: &[f64],
    hi: &[f64],
    l: &[f64],
    u: &[f64],
    integ: &[u8],
    time_limit: Option<f64>,
    gap: Option<f64>,
) -> Res {
    let mut o = Vec::new();
    if let Some(t) = time_limit {
        o.push(Opt::F("time_limit", t));
    }
    if let Some(g) = gap {
        o.push(Opt::F("mip_rel_gap", g));
    }
    solve(c, a, lo, hi, l, u, Some(integ), &o)
}

/// The LP methods of `scipy.optimize.linprog`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Method {
    /// `highs-ds`: dual simplex.
    Ds,
    /// `highs-ipm`: interior point, crossover at HiGHS's default.
    Ipm,
}

/// `linprog(c, A_ub, b_ub, A_eq, b_eq, bounds, method)`: rows are A_ub then A_eq, as SciPy stacks
/// them. OUTPUT the result with `y` split as (ineqlin, eqlin) marginals by `split_duals`.
pub fn linprog(
    c: &[f64],
    a_ub: Option<(&Csc, &[f64])>,
    a_eq: Option<(&Csc, &[f64])>,
    l: &[f64],
    u: &[f64],
    method: Method,
    time_limit: Option<f64>,
) -> Res {
    let n = c.len();
    let empty = Csc {
        m: 0,
        n,
        p: vec![0; n + 1],
        i: vec![],
        v: vec![],
    };
    let (au, bu) = a_ub.unwrap_or((&empty, &[]));
    let (ae, be) = a_eq.unwrap_or((&empty, &[]));
    let a = Csc::vstack(au, ae);
    let lo: Vec<f64> = bu
        .iter()
        .map(|_| f64::NEG_INFINITY)
        .chain(be.iter().copied())
        .collect();
    let hi: Vec<f64> = bu.iter().chain(be.iter()).copied().collect();
    let mut o = vec![Opt::S("presolve", "on")];
    match method {
        Method::Ds => {
            o.push(Opt::S("solver", "simplex"));
            o.push(Opt::I("simplex_strategy", 1));
        }
        Method::Ipm => o.push(Opt::S("solver", "ipm")),
    }
    if let Some(t) = time_limit {
        o.push(Opt::F("time_limit", t));
    }
    solve(c, &a, &lo, &hi, l, u, None, &o)
}

/// (ineqlin, eqlin) marginals of a `linprog` result with m_ub inequality rows.
pub fn split_duals(r: &Res, m_ub: usize) -> Option<(Vec<f64>, Vec<f64>)> {
    r.y.as_ref()
        .map(|y| (y[..m_ub].to_vec(), y[m_ub..].to_vec()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn version_is_pinned() {
        assert_eq!(version(), "1.12.0");
    }

    #[test]
    #[should_panic(expected = "invalid CSC column pointers")]
    fn rejects_malformed_csc_before_ffi() {
        let a = Csc {
            m: 0,
            n: 1,
            p: vec![0, 0, 0],
            i: vec![],
            v: vec![],
        };
        solve(&[1.0], &a, &[], &[], &[0.0], &[1.0], None, &[]);
    }

    #[test]
    #[should_panic(expected = "invalid integrality array")]
    fn rejects_short_integrality_before_ffi() {
        let a = Csc {
            m: 0,
            n: 1,
            p: vec![0, 0],
            i: vec![],
            v: vec![],
        };
        solve(&[1.0], &a, &[], &[], &[0.0], &[1.0], Some(&[]), &[]);
    }

    #[test]
    #[should_panic(expected = "invalid CSC row indices")]
    fn rejects_out_of_range_row_before_ffi() {
        let a = Csc {
            m: 1,
            n: 1,
            p: vec![0, 1],
            i: vec![1],
            v: vec![1.0],
        };
        solve(&[1.0], &a, &[0.0], &[1.0], &[0.0], &[1.0], None, &[]);
    }

    #[test]
    fn milp_reports_its_dual_bound() {
        // tests/test_toolchain.py: min x1 + x2, x1 + 2 x2 >= 1.5, 0 <= x <= 5 integer.
        let a = Csc::from_triplets(1, 2, &[0, 0], &[0, 1], &[1.0, 2.0]);
        let r = milp(
            &[1.0, 1.0],
            &a,
            &[1.5],
            &[f64::INFINITY],
            &[0.0; 2],
            &[5.0; 2],
            &[1, 1],
            None,
            None,
        );
        assert_eq!(r.st, 0);
        assert_eq!(r.fun, Some(1.0));
        assert_eq!(r.dual_bound, Some(1.0));
        assert!(r.nodes.is_some() && r.gap.is_some());
    }

    #[test]
    fn duplicates_sum_in_scipy_order() {
        let a = Csc::from_triplets(2, 3, &[0, 0, 1, 0], &[2, 0, 1, 2], &[1.0, 4.0, 5.0, 2.0]);
        assert_eq!(a.p, vec![0, 1, 2, 3]);
        assert_eq!(a.i, vec![0, 1, 0]);
        assert_eq!(a.v, vec![4.0, 5.0, 3.0]);
    }
}
