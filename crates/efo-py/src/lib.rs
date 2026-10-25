//! The Python module `efo`: the kernels of efo-kernels on numpy arrays. methods/native.py is its
//! only importer; it checks SOURCE against the sources on disk before anything is called.

use efo_kernels::ipm::{self, Convex, Csc, Opts, Trip};
use efo_kernels::price::{Arc, Graph};
use numpy::{PyArray1, PyReadonlyArray1, ToPyArray};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

/// The pricing graph of one instance (Routing §5); built once per column generation run.
#[pyclass(frozen)]
struct Pricer(Graph);

#[pymethods]
impl Pricer {
    /// nodes, depot o, pos[k] (position of customer k in the ng masks, -1 off customers),
    /// demand b, capacities C and Q, arcs as arrays (i, j, l, a, w, direct), ng[k] = N_k as an int.
    #[new]
    fn new(
        nodes: usize,
        o: usize,
        pos: Vec<i64>,
        b: PyReadonlyArray1<f64>,
        c: f64,
        q: f64,
        i: Vec<usize>,
        j: Vec<usize>,
        l: PyReadonlyArray1<f64>,
        a: PyReadonlyArray1<f64>,
        w: PyReadonlyArray1<f64>,
        direct: Vec<bool>,
        ng: Vec<u128>,
    ) -> PyResult<Pricer> {
        if pos.iter().filter(|&&k| k >= 0).count() > 128 {
            return Err(PyValueError::new_err(
                "ng-memory holds at most 128 customers",
            ));
        }
        let (l, a, w) = (l.as_slice()?, a.as_slice()?, w.as_slice()?);
        let arcs = (0..i.len())
            .map(|k| Arc {
                i: i[k],
                j: j[k],
                l: l[k],
                a: a[k],
                w: w[k],
                direct: direct[k],
            })
            .collect();
        let pos = pos
            .iter()
            .map(|&k| (k >= 0).then_some(k as usize))
            .collect();
        Ok(Pricer(Graph::new(
            nodes,
            o,
            pos,
            b.as_slice()?.to_vec(),
            c,
            q,
            arcs,
            ng,
        )))
    }

    /// (best, exact, [(rc, arc indices)], labels created); see efo_kernels::price.
    #[pyo3(signature = (pi, w=None, cap=None, time_limit=f64::INFINITY, tol=1e-9, ub=0.0, ncols=1000))]
    fn price(
        &self,
        py: Python<'_>,
        pi: PyReadonlyArray1<f64>,
        w: Option<PyReadonlyArray1<f64>>,
        cap: Option<usize>,
        time_limit: f64,
        tol: f64,
        ub: f64,
        ncols: usize,
    ) -> PyResult<(f64, bool, Vec<(f64, Vec<usize>)>, usize)> {
        let pi = pi.as_slice()?.to_vec();
        let w = w.map(|w| w.as_slice().map(|s| s.to_vec())).transpose()?;
        let g = &self.0;
        let r = py.detach(|| g.price(&pi, w.as_deref(), cap, time_limit, tol, ub, ncols));
        let cols = r.cols.into_iter().map(|c| (c.rc, c.arcs)).collect();
        Ok((r.best, r.exact, cols, r.labels))
    }
}

/// h, Jh, Hh of methods/ipm.py, called back on the free x; the first Python error is kept and
/// NaN returned, which ends the method as `numerical`, and the error is raised after it.
struct Callbacks<'py> {
    h: Bound<'py, PyAny>,
    jh: Bound<'py, PyAny>,
    hh: Bound<'py, PyAny>,
    err: Option<PyErr>,
}

fn trip(o: &Bound<'_, PyAny>) -> PyResult<Trip> {
    let (r, c, v): (Vec<usize>, Vec<usize>, Vec<f64>) = o.extract()?;
    Ok(Trip { r, c, v })
}

impl Callbacks<'_> {
    fn call<T>(&mut self, f: impl FnOnce(&Self) -> PyResult<T>, nan: T) -> T {
        if self.err.is_some() {
            return nan;
        }
        match f(self) {
            Ok(t) => t,
            Err(e) => {
                self.err = Some(e);
                nan
            }
        }
    }
}

impl Convex for Callbacks<'_> {
    fn h(&mut self, x: &[f64]) -> Vec<f64> {
        self.call(
            |s| s.h.call1((x.to_pyarray(s.h.py()),))?.extract(),
            vec![f64::NAN],
        )
    }
    fn jac(&mut self, x: &[f64]) -> Trip {
        self.call(
            |s| trip(&s.jh.call1((x.to_pyarray(s.jh.py()),))?),
            Trip::default(),
        )
    }
    fn hess(&mut self, x: &[f64], lam: &[f64]) -> Trip {
        self.call(
            |s| {
                let py = s.hh.py();
                trip(&s.hh.call1((x.to_pyarray(py), lam.to_pyarray(py)))?)
            },
            Trip::default(),
        )
    }
}

fn csc(
    m: usize,
    n: usize,
    p: PyReadonlyArray1<i64>,
    i: PyReadonlyArray1<i64>,
    v: PyReadonlyArray1<f64>,
) -> PyResult<Csc> {
    Ok(Csc {
        m,
        n,
        p: p.as_slice()?.iter().map(|&k| k as usize).collect(),
        i: i.as_slice()?.iter().map(|&k| k as usize).collect(),
        v: v.as_slice()?.to_vec(),
    })
}

/// The interior-point core of efo_kernels::ipm on min c'x + x'Qx/2, Ax = b, 0 <= x <= u, with
/// A (m x n) and Q (n x n, both triangles) by compressed columns; h, jh, hh optional callbacks.
#[pyfunction]
#[pyo3(signature = (m, n, ap, ai, av, b, c, u, qp, qi, qv, f0, h=None, jh=None, hh=None,
                    eps=1e-8, delta=None, sigma=None, eta=0.9995, kmax=200, dp=1e-10, dd=1e-10,
                    time_limit=f64::INFINITY, trace=false))]
fn ipm_core<'py>(
    py: Python<'py>,
    m: usize,
    n: usize,
    ap: PyReadonlyArray1<i64>,
    ai: PyReadonlyArray1<i64>,
    av: PyReadonlyArray1<f64>,
    b: PyReadonlyArray1<f64>,
    c: PyReadonlyArray1<f64>,
    u: PyReadonlyArray1<f64>,
    qp: PyReadonlyArray1<i64>,
    qi: PyReadonlyArray1<i64>,
    qv: PyReadonlyArray1<f64>,
    f0: f64,
    h: Option<Bound<'py, PyAny>>,
    jh: Option<Bound<'py, PyAny>>,
    hh: Option<Bound<'py, PyAny>>,
    eps: f64,
    delta: Option<f64>,
    sigma: Option<f64>,
    eta: f64,
    kmax: usize,
    dp: f64,
    dd: f64,
    time_limit: f64,
    trace: bool,
) -> PyResult<Bound<'py, PyDict>> {
    let a = csc(m, n, ap, ai, av)?;
    let q = csc(n, n, qp, qi, qv)?;
    let o = Opts {
        eps,
        delta,
        sigma,
        eta,
        kmax,
        dp,
        dd,
        time_limit,
        trace,
    };
    let (b, c, u) = (b.as_slice()?, c.as_slice()?, u.as_slice()?);
    let mut cb = match (h, jh, hh) {
        (Some(h), Some(jh), Some(hh)) => Some(Callbacks {
            h,
            jh,
            hh,
            err: None,
        }),
        (None, None, None) => None,
        _ => return Err(PyValueError::new_err("h, Jh and Hh are given together")),
    };
    let r = match cb.as_mut() {
        Some(cb) => ipm::ipm(&a, b, c, u, &q, f0, Some(cb as &mut dyn Convex), o),
        None => {
            let (b, c, u) = (b.to_vec(), c.to_vec(), u.to_vec());
            py.detach(|| ipm::ipm(&a, &b, &c, &u, &q, f0, None, o))
        }
    };
    if let Some(e) = cb.and_then(|c| c.err) {
        return Err(e);
    }
    let d = PyDict::new(py);
    d.set_item("x", PyArray1::from_vec(py, r.x))?;
    d.set_item("y", PyArray1::from_vec(py, r.y))?;
    d.set_item("lam", PyArray1::from_vec(py, r.lam))?;
    d.set_item("status", r.status.name())?;
    d.set_item("k", r.k)?;
    d.set_item("err", (r.err[0], r.err[1], r.err[2]))?;
    let s = &r.stats;
    let st = PyDict::new(py);
    st.set_item("kkt", if s.normal { "normal" } else { "augmented" })?;
    st.set_item("t_factor", s.t_factor)?;
    st.set_item("t_solve", s.t_solve)?;
    st.set_item("nnz_K", s.nnz_k)?;
    st.set_item("nnz_factor", s.nnz_l)?;
    st.set_item("analyses", s.analyses)?;
    st.set_item("backtracks", s.backtracks)?;
    d.set_item("stats", st)?;
    let tr = PyList::empty(py);
    for t in r.trace {
        let e = PyDict::new(py);
        e.set_item("k", t.k)?;
        e.set_item("f", t.f)?;
        e.set_item("err", (t.err[0], t.err[1], t.err[2]))?;
        e.set_item("x", PyArray1::from_vec(py, t.x))?;
        e.set_item("y", PyArray1::from_vec(py, t.y))?;
        e.set_item("lam", PyArray1::from_vec(py, t.lam))?;
        tr.append(e)?;
    }
    d.set_item("trace", tr)?;
    Ok(d)
}

#[pymodule]
fn efo(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("SOURCE", env!("EFO_SOURCE"))?;
    m.add_class::<Pricer>()?;
    m.add_function(wrap_pyfunction!(ipm_core, m)?)?;
    Ok(())
}
