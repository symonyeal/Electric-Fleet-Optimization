//! Floating-point primitives in the operation order of the Python reference.
//!
//! Legend
//!   np_sum ... numpy's `add.reduce` on a contiguous float64 array: the first element, plus the
//!              pairwise sum of the rest (blocks of 8 accumulators below 128 elements)
//!   hypot .... CPython's `math.hypot(x, y)` (vector_norm: scaled, compensated, one correction)
//!   fsum ..... `math.fsum`, exactly rounded (Shewchuk partials)
//!   fmt_g .... `format(x, ".{p}g")`;  fmt_f .. `format(x, ",.{p}f")` with thousands separators

fn pairwise(a: &[f64]) -> f64 {
    let n = a.len();
    if n < 8 {
        let mut r = 0.0;
        for &x in a {
            r += x;
        }
        r
    } else if n <= 128 {
        let mut r = [a[0], a[1], a[2], a[3], a[4], a[5], a[6], a[7]];
        let mut i = 8;
        while i < n - (n % 8) {
            for j in 0..8 {
                r[j] += a[i + j];
            }
            i += 8;
        }
        let mut res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        while i < n {
            res += a[i];
            i += 1;
        }
        res
    } else {
        let mut n2 = n / 2;
        n2 -= n2 % 8;
        pairwise(&a[..n2]) + pairwise(&a[n2..])
    }
}

/// `np.sum(a)` for a 1-D float64 array.
pub fn np_sum(a: &[f64]) -> f64 {
    match a.len() {
        0 => 0.0,
        _ => a[0] + pairwise(&a[1..]),
    }
}

/// Python's built-in `sum()` over Python floats (CPython >= 3.12): the first item, then Neumaier's
/// compensated loop over the rest, the compensation added once at the end. Over numpy float64
/// items `sum()` takes the generic path instead, which is `seq_sum`.
pub fn pysum(a: &[f64]) -> f64 {
    let Some((&f0, rest)) = a.split_first() else {
        return 0.0;
    };
    let (mut f, mut c) = (f0, 0.0f64);
    for &x in rest {
        let t = f + x;
        if f.abs() >= x.abs() {
            c += (f - t) + x;
        } else {
            c += (x - t) + f;
        }
        f = t;
    }
    if c != 0.0 && c.is_finite() {
        f += c;
    }
    f
}

/// Left-to-right addition from 0, as `sum()` of numpy scalars or a `+=` loop computes it.
pub fn seq_sum(a: &[f64]) -> f64 {
    let mut s = 0.0;
    for &x in a {
        s += x;
    }
    s
}

/// Python's `round(x)`: half to even.
pub fn round_even(x: f64) -> f64 {
    x.round_ties_even()
}

/// `np.dot(a, b)` / `a @ b` for 1-D float64 arrays is BLAS ddot; numpy without BLAS for tiny
/// vectors gives the same sequential order used here.
pub fn dot(a: &[f64], b: &[f64]) -> f64 {
    let mut s = 0.0;
    for k in 0..a.len() {
        s += a[k] * b[k];
    }
    s
}

#[inline]
fn dl_mul(x: f64, y: f64) -> (f64, f64) {
    let z = x * y;
    (z, x.mul_add(y, -z))
}

#[inline]
fn dl_fast_sum(a: f64, b: f64) -> (f64, f64) {
    let x = a + b;
    let z = x - a;
    (x, b - z)
}

/// CPython 3.14 `math.hypot(x, y)`.
pub fn hypot(x: f64, y: f64) -> f64 {
    let v = [x.abs(), y.abs()];
    let max = v[0].max(v[1]);
    if x.is_nan() || y.is_nan() {
        return if max.is_infinite() { max } else { f64::NAN };
    }
    norm(&v, max)
}

fn norm(v: &[f64], max: f64) -> f64 {
    if max.is_infinite() {
        return max;
    }
    if max == 0.0 || v.len() <= 1 {
        return max;
    }
    let (_, max_e) = frexp(max);
    if max_e < -1023 {
        let w: Vec<f64> = v.iter().map(|x| x / f64::MIN_POSITIVE).collect();
        return f64::MIN_POSITIVE * norm(&w, max / f64::MIN_POSITIVE);
    }
    let scale = ldexp(1.0, -max_e);
    let (mut csum, mut frac1, mut frac2) = (1.0f64, 0.0f64, 0.0f64);
    for &x0 in v {
        let x = x0 * scale;
        let pr = dl_mul(x, x);
        let sm = dl_fast_sum(csum, pr.0);
        csum = sm.0;
        frac1 += pr.1;
        frac2 += sm.1;
    }
    let mut h = (csum - 1.0 + (frac1 + frac2)).sqrt();
    let pr = dl_mul(-h, h);
    let sm = dl_fast_sum(csum, pr.0);
    csum = sm.0;
    frac1 += pr.1;
    frac2 += sm.1;
    let x = csum - 1.0 + (frac1 + frac2);
    h += x / (2.0 * h);
    h / scale
}

/// C `frexp`: x = m 2^e, 0.5 <= |m| < 1.
pub fn frexp(x: f64) -> (f64, i32) {
    if x == 0.0 || !x.is_finite() {
        return (x, 0);
    }
    let bits = x.to_bits();
    let exp = ((bits >> 52) & 0x7ff) as i32;
    if exp == 0 {
        let (m, e) = frexp(x * f64::powi(2.0, 64));
        return (m, e - 64);
    }
    let e = exp - 1022;
    let m = f64::from_bits((bits & !(0x7ffu64 << 52)) | (1022u64 << 52));
    (m, e)
}

/// C `ldexp`.
pub fn ldexp(x: f64, e: i32) -> f64 {
    let mut x = x;
    let mut e = e;
    while e > 1000 {
        x *= f64::powi(2.0, 1000);
        e -= 1000;
    }
    while e < -1000 {
        x *= f64::powi(2.0, -1000);
        e += 1000;
    }
    x * f64::powi(2.0, e)
}

/// `math.fsum`.
pub fn fsum(a: &[f64]) -> f64 {
    let mut p: Vec<f64> = Vec::new();
    for &x0 in a {
        let mut x = x0;
        let mut i = 0;
        for k in 0..p.len() {
            let mut y = p[k];
            if x.abs() < y.abs() {
                std::mem::swap(&mut x, &mut y);
            }
            let hi = x + y;
            let lo = y - (hi - x);
            if lo != 0.0 {
                p[i] = lo;
                i += 1;
            }
            x = hi;
        }
        p.truncate(i);
        p.push(x);
    }
    let mut hi = 0.0;
    if let Some(mut n) = p.len().checked_sub(1) {
        hi = p[n];
        let mut lo = 0.0;
        while n > 0 {
            let x = hi;
            n -= 1;
            let y = p[n];
            hi = x + y;
            let yr = hi - x;
            lo = y - yr;
            if lo != 0.0 {
                break;
            }
        }
        if n > 0 && ((lo < 0.0 && p[n - 1] < 0.0) || (lo > 0.0 && p[n - 1] > 0.0)) {
            let y = lo * 2.0;
            let x = hi + y;
            let yr = x - hi;
            if y == yr {
                hi = x;
            }
        }
    }
    hi
}

/// Python `format(x, f".{p}g")`.
pub fn fmt_g(x: f64, p: usize) -> String {
    if x.is_nan() {
        return "nan".into();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf".into() } else { "-inf".into() };
    }
    let p = p.max(1);
    if x == 0.0 {
        return if x.is_sign_negative() {
            "-0".into()
        } else {
            "0".into()
        };
    }
    let e = format!("{:.*e}", p - 1, x);
    let (m, ex) = e.split_once('e').unwrap();
    let ex: i32 = ex.parse().unwrap();
    if ex < -4 || ex >= p as i32 {
        let m = strip(m);
        format!("{m}e{}{:02}", if ex < 0 { '-' } else { '+' }, ex.abs())
    } else {
        let dec = (p as i32 - 1 - ex).max(0) as usize;
        strip(&format!("{:.*}", dec, x))
    }
}

fn strip(s: &str) -> String {
    if s.contains('.') {
        s.trim_end_matches('0').trim_end_matches('.').to_string()
    } else {
        s.to_string()
    }
}

/// Python `format(x, f",.{p}f")`.
pub fn fmt_f(x: f64, p: usize) -> String {
    let s = format!("{:.*}", p, x);
    let (sign, s) = s.strip_prefix('-').map_or(("", s.as_str()), |r| ("-", r));
    let (int, frac) = s.split_once('.').map_or((s, None), |(a, b)| (a, Some(b)));
    let mut g = String::new();
    for (k, ch) in int.chars().enumerate() {
        if k > 0 && (int.len() - k) % 3 == 0 {
            g.push(',');
        }
        g.push(ch);
    }
    match frac {
        Some(f) => format!("{sign}{g}.{f}"),
        None => format!("{sign}{g}"),
    }
}

/// Python `format(x, "g")` (6 significant digits), as f-strings `{x:g}` print.
pub fn g(x: f64) -> String {
    fmt_g(x, 6)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn formats_match_python() {
        assert_eq!(fmt_g(384.67809299999996, 9), "384.678093");
        assert_eq!(fmt_g(1e-7, 9), "1e-07");
        assert_eq!(fmt_g(8.0, 6), "8");
        assert_eq!(fmt_g(0.5, 6), "0.5");
        assert_eq!(fmt_g(6.7e-5, 6), "6.7e-05");
        assert_eq!(fmt_g(1234567.0, 6), "1.23457e+06");
        assert_eq!(fmt_f(1234567.891, 2), "1,234,567.89");
        assert_eq!(fmt_f(-1234.5, 1), "-1,234.5");
        assert_eq!(fmt_f(12.0, 0), "12");
    }

    #[test]
    fn hypot_basic() {
        assert_eq!(hypot(3.0, 4.0), 5.0);
        assert_eq!(hypot(0.0, 0.0), 0.0);
        assert_eq!(hypot(-5.0, 12.0), 13.0);
    }

    #[test]
    fn fsum_exact() {
        assert_eq!(fsum(&[0.1; 10]), 1.0);
        assert_eq!(fsum(&[1e100, 1.0, -1e100, 1e-100]), 1.0);
    }
}
