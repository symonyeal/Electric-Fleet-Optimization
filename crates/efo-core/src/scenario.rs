//! Declared engineering scenarios (Data §3).
//!
//! A scenario is a TOML file. Every numerical entry is a table {value, unit, source}, where source
//! is a citation recorded in docs/SOURCES.md or the word `illustrative`; strings and lists (names,
//! stop ids) are structure and carry neither. `load` returns the values with the tables stripped
//! (a J object in document order) and a provenance list "path.to.key" -> (unit, source), after
//! `validate` has checked every domain the models assume.
//!
//! Legend
//!   v ......... scenario values           w0, w1 .. billing window, seconds of the day
//!   billed .... t (seconds, possibly past midnight) lies in [w0, w1) of its day; w0 > w1 wraps

use crate::json::{J, Obj};
use crate::num::g;
use std::path::Path;

pub type Prov = Vec<(String, String, String)>;

fn walk(t: &toml::Table, path: &str, prov: &mut Prov) -> Result<J, String> {
    let mut out = Obj::new();
    for (k, v) in t {
        let p = if path.is_empty() {
            k.clone()
        } else {
            format!("{path}.{k}")
        };
        match v {
            toml::Value::Table(d) if d.contains_key("value") => {
                let unit = d.get("unit").and_then(|u| u.as_str()).unwrap_or("");
                let src = d.get("source").and_then(|u| u.as_str()).unwrap_or("");
                if unit.is_empty() || src.is_empty() {
                    return Err(format!("{p}: a value needs a unit and a source"));
                }
                let x = match &d["value"] {
                    toml::Value::Float(f) => *f,
                    toml::Value::Integer(i) => *i as f64,
                    _ => return Err(format!("{p}: value is not a number")),
                };
                out.insert(k.clone(), J::F(x));
                prov.push((p, unit.to_string(), src.to_string()));
            }
            toml::Value::Table(d) => {
                out.insert(k.clone(), walk(d, &p, prov)?);
            }
            toml::Value::String(s) => {
                out.insert(k.clone(), J::S(s.clone()));
            }
            toml::Value::Array(a) => {
                let mut l = Vec::new();
                for x in a {
                    l.push(match x {
                        toml::Value::String(s) => J::S(s.clone()),
                        toml::Value::Integer(i) => J::I(*i),
                        toml::Value::Float(f) => J::F(*f),
                        toml::Value::Boolean(b) => J::B(*b),
                        _ => return Err(format!("{p}: nested structure in a list")),
                    });
                }
                out.insert(k.clone(), J::A(l));
            }
            _ => return Err(format!("{p}: bare number; write {{value, unit, source}}")),
        }
    }
    Ok(J::O(out))
}

type Rule = (&'static str, &'static str, fn(f64) -> bool, &'static str);

const RULES: [Rule; 18] = [
    ("time", "delta", |x| x > 0.0, "> 0"),
    ("time", "window", |x| x > 0.0, "> 0"),
    ("time", "layover", |x| x >= 0.0, ">= 0"),
    ("time", "speed", |x| x > 0.0, "> 0"),
    ("time", "service", |x| x >= 0.0, ">= 0"),
    ("time", "T", |x| x > 0.0, "> 0"),
    ("time", "tau_min", |x| x > 0.0, "> 0"),
    ("deadhead", "speed", |x| x > 0.0, "> 0"),
    ("deadhead", "detour", |x| x > 0.0, "> 0"),
    ("battery", "B", |x| x > 0.0, "> 0"),
    ("battery", "kappa", |x| x >= 0.0, ">= 0"),
    ("charger", "P", |x| x > 0.0, "> 0"),
    ("charger", "eta", |x| 0.0 < x && x <= 1.0, "in (0, 1]"),
    ("charger", "alpha", |x| x >= 0.0, ">= 0"),
    ("charger", "gamma", |x| x >= 0.0, ">= 0"),
    ("cost", "rider", |x| x > -1.0, "> -1 (a credit below 100%)"),
    (
        "cost",
        "peak_from",
        |x| (0.0..24.0).contains(&x),
        "in [0, 24)",
    ),
    ("cost", "peak_to", |x| 0.0 < x && x <= 24.0, "in (0, 24]"),
];

const SITE: [(&str, fn(f64) -> bool, &str); 4] = [
    (
        "nbar",
        |x| x >= 0.0 && x == x.trunc(),
        "a nonnegative integer",
    ),
    ("hbar", |x| x >= 0.0, ">= 0"),
    ("G0", |x| x >= 0.0, ">= 0"),
    ("L", |x| x >= 0.0, ">= 0"),
];

fn fl(v: &J, t: &str, k: &str) -> Option<f64> {
    match v.get(t)?.get(k)? {
        J::F(x) => Some(*x),
        _ => None,
    }
}

/// Every value of scenario v outside its domain, as Python's `validate` names them.
pub fn validate(v: &J) -> Result<(), String> {
    let mut err: Vec<String> = Vec::new();
    fn walk_nf(d: &J, path: &str, err: &mut Vec<String>) {
        if let J::O(o) = d {
            for (k, x) in o {
                match x {
                    J::O(_) => walk_nf(x, &format!("{path}{k}."), err),
                    J::F(f) if !f.is_finite() => {
                        err.push(format!("{path}{k} = {}: not finite", py_float(*f)))
                    }
                    _ => {}
                }
            }
        }
    }
    walk_nf(v, "", &mut err);
    for (t, k, ok, words) in RULES {
        if let Some(x) = fl(v, t, k)
            && x.is_finite()
            && !ok(x)
        {
            err.push(format!("{t}.{k} = {}: must be {words}", g(x)));
        }
    }
    if let (Some(r), Some(s0), Some(sm)) = (
        fl(v, "battery", "reserve"),
        fl(v, "battery", "s0"),
        fl(v, "battery", "smax"),
    ) && !(0.0 <= r && r <= s0 && s0 <= sm && sm <= 1.0)
    {
        err.push(format!(
            "battery: needs 0 <= reserve <= s0 <= smax <= 1, got {}, {}, {}",
            g(r),
            g(s0),
            g(sm)
        ));
    }
    if let Some(J::O(co)) = v.get("cost") {
        for (k, x) in co {
            if !["rider", "peak_from", "peak_to"].contains(&k.as_str())
                && let J::F(x) = x
                && *x < 0.0
            {
                err.push(format!(
                    "cost.{k} = {}: a cost coefficient must be >= 0",
                    g(*x)
                ));
            }
        }
        if co.contains_key("peak_from") != co.contains_key("peak_to") {
            err.push("cost: peak_from and peak_to are given together or not at all".into());
        } else if co.contains_key("peak_from") && co["peak_from"] == co["peak_to"] {
            err.push("cost: the billing window [peak_from, peak_to) is empty".into());
        }
    }
    let mut owner: Vec<(String, String)> = Vec::new();
    if let Some(J::O(sites)) = v.get("sites") {
        for (s, d) in sites {
            for (k, ok, words) in SITE {
                if let Some(J::F(x)) = d.get(k)
                    && x.is_finite()
                    && !ok(*x)
                {
                    err.push(format!("sites.{s}.{k} = {}: must be {words}", g(*x)));
                }
            }
            for stop in d.get("stops").and_then(J::a).into_iter().flatten() {
                let stop = stop.s().unwrap_or_default().to_string();
                if let Some((_, o)) = owner.iter().find(|(st, _)| *st == stop) {
                    err.push(format!("stop {stop} belongs to sites {o} and {s}"));
                } else {
                    owner.push((stop, s.clone()));
                }
            }
        }
    }
    if err.is_empty() {
        Ok(())
    } else {
        Err(format!("invalid scenario: {}", err.join("; ")))
    }
}

fn py_float(x: f64) -> String {
    if x.is_nan() {
        "nan".into()
    } else if x > 0.0 {
        "inf".into()
    } else {
        "-inf".into()
    }
}

/// M4's scenario set [(weight, kappa)]: nonempty, weights finite, >= 0 and summing to one,
/// consumptions finite and >= 0 (Models §7).
pub fn weights(s: &[(f64, f64)]) -> Result<(), String> {
    if s.is_empty() {
        return Err("M4 needs at least one scenario".into());
    }
    let w: Vec<f64> = s.iter().map(|x| x.0).collect();
    if !w.iter().all(|p| p.is_finite() && *p >= 0.0) {
        return Err(format!("M4 weights must be finite and >= 0, got {w:?}"));
    }
    let t = crate::num::fsum(&w);
    if (t - 1.0).abs() > 1e-9 {
        return Err(format!(
            "M4 weights must sum to one, got {}",
            crate::json::repr(t)
        ));
    }
    if !s.iter().all(|x| x.1.is_finite() && x.1 >= 0.0) {
        return Err("M4 consumptions must be finite and >= 0".into());
    }
    Ok(())
}

/// Read, strip the {value, unit, source} tables, validate.
pub fn load(path: &Path) -> Result<(J, Prov), String> {
    let t = std::fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let tab: toml::Table = toml::from_str(&t).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut prov = Prov::new();
    let v = walk(&tab, "", &mut prov)?;
    validate(&v)?;
    Ok((v, prov))
}

/// Slot index of time t (seconds after midnight of the service day, possibly >= 86400).
pub fn slot(t: f64, delta: f64) -> i64 {
    (t / delta).floor() as i64
}

/// Python's `t % 86400` on floats (the result takes the sign of the divisor).
pub fn pymod(t: f64, m: f64) -> f64 {
    let r = t % m;
    if r != 0.0 && (r < 0.0) != (m < 0.0) {
        r + m
    } else {
        r
    }
}

pub fn billed(t: f64, w0: f64, w1: f64) -> bool {
    let s = pymod(t, 86400.0);
    if w0 <= w1 {
        w0 <= s && s < w1
    } else {
        s >= w0 || s < w1
    }
}

/// Number at a dotted path, e.g. f(v, "battery.B").
pub fn f(v: &J, path: &str) -> f64 {
    v.at(path)
        .and_then(J::f)
        .unwrap_or_else(|| panic!("scenario value {path} missing"))
}

/// Number at a dotted path, or a default (Python's `.get(k, default)`).
pub fn f_or(v: &J, path: &str, d: f64) -> f64 {
    v.at(path).and_then(J::f).unwrap_or(d)
}
