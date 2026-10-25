//! Sparse LDL' of a symmetric quasi-definite matrix (Vanderbei 1995; Algorithms §2).
//!
//! Legend
//!   K ....... N x N symmetric, given by its lower triangle in compressed columns (p, i, v)
//!   s ....... expected sign of each pivot: -1 on the (1,1) block, +1 on the (2,2) block
//!   eps, del  a pivot of the wrong sign or below eps in magnitude is replaced by s del: a small del
//!             regularizes a quasi-definite K; del = 1e128 drops the pivot's component, the
//!             treatment of a singular normal matrix (Wright 1999)
//!
//! A quasi-definite K = [-E A'; A F], E and F positive definite, has an LDL' factorization for every
//! symmetric permutation (a definite K is the case of one block), so the fill-reducing order
//! (approximate minimum degree) is chosen once from the pattern and reused while the pattern stays
//! the same. The factorization is backward stable for a definite K in any order; for a
//! quasi-definite one its error grows with the inverse of the smallest eigenvalue of E and F
//! (Gill, Saunders and Shinnerl 1996), which interior-point iterates drive to the regularization.
//! A replaced pivot perturbs K; each solve is refined against K.

use faer::dyn_stack::{MemBuffer, MemStack};
use faer::linalg::cholesky::ldlt::factor::LdltRegularization;
use faer::sparse::linalg::cholesky::{
    CholeskySymbolicParams, LdltRef, SymbolicCholesky, SymmetricOrdering,
    factorize_symbolic_cholesky,
};
use faer::sparse::{SparseColMatRef, SymbolicSparseColMatRef};
use faer::{Conj, MatMut, Par, Side};

/// A symmetric matrix by the lower triangle of its compressed columns.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Lower {
    pub n: usize,
    pub p: Vec<usize>,
    pub i: Vec<usize>,
    pub v: Vec<f64>,
}

impl Lower {
    /// From triplets (r, c, v) of either triangle; each entry is mirrored into the lower one and
    /// duplicates are summed. O(nnz log nnz).
    pub fn from_triplets(n: usize, r: &[usize], c: &[usize], v: &[f64]) -> Lower {
        let mut t: Vec<(usize, usize, f64)> = (0..r.len())
            .map(|k| (r[k].min(c[k]), r[k].max(c[k]), v[k]))
            .collect();
        t.sort_unstable_by_key(|e| (e.0, e.1));
        let mut p = vec![0; n + 1];
        let (mut i, mut w) = (Vec::with_capacity(t.len()), Vec::with_capacity(t.len()));
        let mut last = (usize::MAX, usize::MAX);
        for (col, row, x) in t {
            if (col, row) == last {
                *w.last_mut().unwrap() += x;
            } else {
                i.push(row);
                w.push(x);
                p[col + 1] += 1;
                last = (col, row);
            }
        }
        for j in 0..n {
            p[j + 1] += p[j];
        }
        Lower { n, p, i, v: w }
    }

    /// y = K x, from the lower triangle.
    pub fn mul(&self, x: &[f64]) -> Vec<f64> {
        let mut y = vec![0.0; self.n];
        for j in 0..self.n {
            for k in self.p[j]..self.p[j + 1] {
                let i = self.i[k];
                y[i] += self.v[k] * x[j];
                if i != j {
                    y[j] += self.v[k] * x[i];
                }
            }
        }
        y
    }
}

/// The factorization of one K, its symbolic analysis kept for the next K of the same pattern.
pub struct Ldl {
    pattern: (Vec<usize>, Vec<usize>),
    sym: SymbolicCholesky<usize>,
    l: Vec<f64>,
    s: Vec<i8>,
    eps: f64,
    del: f64,
    k: Lower,
    pub analyses: usize,
}

fn analyse(k: &Lower) -> SymbolicCholesky<usize> {
    let a = SymbolicSparseColMatRef::new_checked(k.n, k.n, &k.p, None, &k.i);
    factorize_symbolic_cholesky(
        a,
        Side::Lower,
        SymmetricOrdering::Amd,
        CholeskySymbolicParams::default(),
    )
    .expect("symbolic LDL' of a well-formed pattern")
}

/// Entries of the LDL' factor of k's pattern in the fill-reducing order.
pub fn factor_nnz(k: &Lower) -> usize {
    analyse(k).len_val()
}

impl Ldl {
    /// Analyse the pattern of k and factor it, a pivot of the wrong sign or below eps in
    /// magnitude replaced by s del; None if a pivot is not finite.
    pub fn new(k: Lower, s: Vec<i8>, eps: f64, del: f64) -> Option<Ldl> {
        let sym = analyse(&k);
        let mut f = Ldl {
            pattern: (k.p.clone(), k.i.clone()),
            l: vec![0.0; sym.len_val()],
            sym,
            s,
            eps,
            del,
            k: Lower::default(),
            analyses: 1,
        };
        f.factor(k).then_some(f)
    }

    /// Factor k, re-analysing only if its pattern differs from the last one; false if a pivot is
    /// not finite (K carries an infinite or undefined entry).
    pub fn factor(&mut self, k: Lower) -> bool {
        if k.v.iter().any(|x| !x.is_finite()) {
            return false;
        }
        if (&k.p, &k.i) != (&self.pattern.0, &self.pattern.1) {
            self.sym = analyse(&k);
            self.l = vec![0.0; self.sym.len_val()];
            self.pattern = (k.p.clone(), k.i.clone());
            self.analyses += 1;
        }
        let a = SparseColMatRef::<usize, f64>::new(
            SymbolicSparseColMatRef::new_checked(k.n, k.n, &k.p, None, &k.i),
            &k.v,
        );
        let reg = LdltRegularization {
            dynamic_regularization_signs: Some(&self.s),
            dynamic_regularization_delta: self.del,
            dynamic_regularization_epsilon: self.eps,
        };
        let mut buf = MemBuffer::new(
            self.sym
                .factorize_numeric_ldlt_scratch::<f64>(Par::Seq, Default::default()),
        );
        let ok = self
            .sym
            .factorize_numeric_ldlt(
                &mut self.l,
                a,
                Side::Lower,
                reg,
                Par::Seq,
                MemStack::new(&mut buf),
                Default::default(),
            )
            .is_ok();
        self.k = k;
        ok
    }

    fn apply(&self, r: &mut [f64]) {
        let f = LdltRef::<usize, f64>::new(&self.sym, &self.l);
        let mut buf = MemBuffer::new(f.solve_in_place_scratch::<f64>(1, Par::Seq));
        let x = MatMut::from_column_major_slice_mut(r, self.k.n, 1);
        f.solve_in_place_with_conj(Conj::No, x, Par::Seq, MemStack::new(&mut buf));
    }

    /// K d = r, refined against K at most three times while the residual exceeds 1e-14 (1 + |r|)
    /// and keeps falling. K carries the static regularization: refining against K without it
    /// would drift along the null space of a singular unregularized system.
    pub fn solve(&self, r: &[f64]) -> Vec<f64> {
        let mut d = r.to_vec();
        self.apply(&mut d);
        let tol = 1e-14 * (1.0 + r.iter().fold(0.0f64, |a, x| a.max(x.abs())));
        let mut last = f64::INFINITY;
        for _ in 0..3 {
            let kd = self.k.mul(&d);
            let mut e: Vec<f64> = (0..r.len()).map(|k| r[k] - kd[k]).collect();
            let size = e.iter().fold(0.0f64, |a, x| a.max(x.abs()));
            if size <= tol || size >= last {
                break;
            }
            last = size;
            self.apply(&mut e);
            for (x, y) in d.iter_mut().zip(e) {
                *x += y;
            }
        }
        d
    }

    /// Entries of the factor L.
    pub fn nnz(&self) -> usize {
        self.sym.len_val()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn quasi_definite_solve() {
        // K = [-2 1 0; 1 -3 1; 0 1 4]: the (1,1) block negative definite, (2,2) positive.
        let k = Lower::from_triplets(
            3,
            &[0, 1, 1, 2, 2],
            &[0, 0, 1, 1, 2],
            &[-2.0, 1.0, -3.0, 1.0, 4.0],
        );
        let f = Ldl::new(k.clone(), vec![-1, -1, 1], 1e-13, 1e-8).unwrap();
        let r = [1.0, 2.0, 3.0];
        let d = f.solve(&r);
        let kd = k.mul(&d);
        for j in 0..3 {
            assert!((kd[j] - r[j]).abs() < 1e-12);
        }
    }

    #[test]
    fn duplicates_are_summed_and_mirrored() {
        let k = Lower::from_triplets(2, &[0, 1, 0], &[1, 0, 0], &[1.0, 2.0, 5.0]);
        assert_eq!(k.p, vec![0, 2, 2]);
        assert_eq!(k.i, vec![0, 1]);
        assert_eq!(k.v, vec![5.0, 3.0]);
    }
}
