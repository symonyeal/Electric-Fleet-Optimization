//! Result contract (Algorithms §8).
//!
//! A minimization result carries a feasible objective U, a valid lower bound L, and a gap only
//! when both are finite. Four fields keep apart what each party established:
//!
//!   solver_status ....... the method's own termination (HiGHS, the textbook IPM, OA)
//!   validation_status ... replayed: U is the cost of a solution the independent replay accepted;
//!                         validation_failed: a candidate was rejected (U absent), or the model's
//!                         objective disagrees with the replayed cost (U kept, the bound in doubt);
//!                         not_available
//!   certificate_status .. certified: -tol <= U - L <= tol with a replayed U; open; invalid_bound:
//!                         L > U + tol; not_applicable: no bound is defined (infeasible, local)
//!   status .............. the public state, derived from the three: `optimal` iff certified
//!
//! Legend: tol = eps_abs + eps_rel max(1, |U|). A crossing within tol is floating-point noise and is
//! reported raw, never clamped; a larger one is a defect, never certified.

use crate::jo;
use crate::json::{J, Obj};
use crate::num::fmt_g;
use std::sync::OnceLock;

pub const SOLVER: [&str; 9] = [
    "optimal",
    "feasible_limit",
    "no_incumbent",
    "infeasible",
    "unbounded",
    "local",
    "numerical",
    "stall",
    "limit",
];
pub const VALIDATION: [&str; 3] = ["replayed", "validation_failed", "not_available"];
pub const EPS: f64 = 1e-6;

fn fin(v: Option<f64>) -> Option<f64> {
    v.filter(|x| x.is_finite())
}

/// eps_abs + eps_rel max(1, |U|); eps_abs alone when U is absent.
pub fn tol(u: Option<f64>, ea: f64, er: f64) -> f64 {
    match fin(u) {
        Some(u) => ea + er * 1f64.max(u.abs()),
        None => ea,
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Gap {
    Closed,
    Crossed,
    Open,
}

impl Gap {
    pub fn as_str(self) -> &'static str {
        match self {
            Gap::Closed => "closed",
            Gap::Crossed => "crossed",
            Gap::Open => "open",
        }
    }
}

/// The two-sided rule every stopping test uses.
pub fn gap_state(u: Option<f64>, l: Option<f64>, ea: f64, er: f64) -> Gap {
    let (Some(u), Some(l)) = (fin(u), fin(l)) else {
        return Gap::Open;
    };
    let t = tol(Some(u), ea, er);
    if u - l < -t {
        Gap::Crossed
    } else if u - l <= t {
        Gap::Closed
    } else {
        Gap::Open
    }
}

pub fn certified(u: Option<f64>, l: Option<f64>) -> bool {
    gap_state(u, l, EPS, EPS) == Gap::Closed
}

/// (certificate_status, status) from the solver's termination, the bounds and the replay.
pub fn classify(
    solver: &str,
    u: Option<f64>,
    l: Option<f64>,
    validation: Option<&str>,
    ea: f64,
    er: f64,
) -> (&'static str, String) {
    let g = gap_state(u, l, ea, er);
    let cert = if g == Gap::Crossed {
        "invalid_bound"
    } else if g == Gap::Closed && validation == Some("replayed") {
        "certified"
    } else if fin(u).is_none()
        && fin(l).is_none()
        && ["infeasible", "unbounded", "local"].contains(&solver)
    {
        "not_applicable"
    } else {
        "open"
    };
    let st = if cert == "invalid_bound" {
        "invalid_bound".to_string()
    } else if cert == "certified" {
        "optimal".to_string()
    } else if validation == Some("validation_failed") {
        "validation_failed".to_string()
    } else if solver == "optimal" || solver == "feasible_limit" {
        if fin(u).is_some() {
            "feasible_limit".into()
        } else {
            "no_incumbent".into()
        }
    } else {
        solver.to_string()
    };
    (cert, st)
}

/// One solve, before it becomes a record.
#[derive(Clone, Debug)]
pub struct Rec {
    pub model: String,
    pub instance: String,
    pub status: String,
    pub u: Option<f64>,
    pub l: Option<f64>,
    pub solver: J,
    pub elapsed: f64,
    pub provenance: J,
    pub eps_abs: f64,
    pub eps_rel: f64,
    pub validation: Option<String>,
    pub objective: Option<f64>,
    pub bound_source: Option<String>,
    pub kw: Vec<(String, J)>,
}

impl Rec {
    pub fn new(model: &str, instance: &str, status: &str) -> Rec {
        Rec {
            model: model.into(),
            instance: instance.into(),
            status: status.into(),
            u: None,
            l: None,
            solver: J::Null,
            elapsed: 0.0,
            provenance: J::Null,
            eps_abs: EPS,
            eps_rel: EPS,
            validation: None,
            objective: None,
            bound_source: None,
            kw: Vec::new(),
        }
    }

    pub fn kw(mut self, k: &str, v: impl Into<J>) -> Rec {
        self.kw.push((k.into(), v.into()));
        self
    }
}

/// The record as a JSON object, in the key order of the Python reference.
pub fn record(r: Rec) -> Result<J, String> {
    if !SOLVER.contains(&r.status.as_str()) {
        return Err(format!("solver status {:?} not in {SOLVER:?}", r.status));
    }
    let (u, l) = (fin(r.u), fin(r.l));
    let mut validation = r.validation.unwrap_or_else(|| {
        if u.is_some() {
            "replayed".into()
        } else {
            "not_available".into()
        }
    });
    if !VALIDATION.contains(&validation.as_str()) {
        return Err(format!("validation {validation:?} not in {VALIDATION:?}"));
    }
    let mut defects: Vec<String> = Vec::new();
    if let (Some(o), Some(uu)) = (r.objective, u)
        && (o - uu).abs() > tol(Some(uu), r.eps_abs, r.eps_rel)
    {
        defects.push(format!(
            "objective {} disagrees with replayed {}",
            fmt_g(o, 9),
            fmt_g(uu, 9)
        ));
        validation = "validation_failed".into();
    }
    let (cert, public) = classify(&r.status, u, l, Some(&validation), r.eps_abs, r.eps_rel);
    if cert == "invalid_bound" {
        defects.push("negative gap".into());
    }
    let gap = match (u, l) {
        (Some(u), Some(l)) => Some(u - l),
        _ => None,
    };
    let mut o = jo! {
        "model" => r.model,
        "instance" => r.instance,
        "status" => public,
        "solver_status" => r.status,
        "validation_status" => validation,
        "certificate_status" => cert,
        "U" => u,
        "L" => l,
        "gap_abs" => gap,
        "gap_rel" => gap.map(|g| g / 1f64.max(u.unwrap().abs())),
        "certified" => cert == "certified",
        "defect" => if defects.is_empty() { None } else { Some(defects.join("; ")) },
        "bound_source" => if l.is_some() { r.bound_source } else { None },
        "tolerances" => jo!{"eps_abs" => r.eps_abs, "eps_rel" => r.eps_rel},
        "objective" => r.objective,
        "solver" => r.solver,
        "elapsed" => r.elapsed,
        "provenance" => r.provenance,
    };
    for (k, v) in r.kw {
        o.set(&k, v);
    }
    Ok(o)
}

/// The contract holds within a stored record: its public status, certificate and flags are what
/// `classify` derives from its own fields. OUTPUT the list of contradictions.
pub fn consistent(r: &J) -> Vec<String> {
    let mut out = Vec::new();
    let t = r.get("tolerances").filter(|t| t.truthy());
    let ea = t
        .and_then(|t| t.get("eps_abs"))
        .and_then(J::f)
        .unwrap_or(EPS);
    let er = t
        .and_then(|t| t.get("eps_rel"))
        .and_then(J::f)
        .unwrap_or(EPS);
    let certified = r.get("certified").is_some_and(J::truthy);
    if certified && r.get("defect").is_some_and(J::truthy) {
        out.push("certified with a defect".into());
    }
    let st = r.get("status").and_then(J::s);
    if (st == Some("optimal")) != certified {
        out.push(format!(
            "status {} with certified={}",
            st.unwrap_or("None"),
            if certified { "True" } else { "False" }
        ));
    }
    let num = |k: &str| r.get(k).and_then(J::f);
    if let Some(ss) = r.get("solver_status") {
        let ss = ss.s().unwrap_or("");
        let (cert, st2) = classify(
            ss,
            num("U"),
            num("L"),
            r.get("validation_status").and_then(J::s),
            ea,
            er,
        );
        let sc = r.get("certificate_status").and_then(J::s);
        if sc != Some(cert) || st != Some(st2.as_str()) {
            out.push(format!(
                "stored {}/{}, derived {cert}/{st2}",
                sc.unwrap_or("None"),
                st.unwrap_or("None")
            ));
        }
    } else if gap_state(num("U"), num("L"), ea, er) == Gap::Crossed {
        out.push("negative gap".into());
    }
    out
}

fn git(args: &[&str]) -> String {
    std::process::Command::new("git")
        .args(args)
        .output()
        .ok()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .unwrap_or_default()
}

/// Short git revision, with '+dirty' when the code differs from it (result bundles, planning
/// notes and prose are not code).
pub fn revision() -> &'static str {
    static R: OnceLock<String> = OnceLock::new();
    R.get_or_init(|| {
        let code = git(&[
            "status",
            "--porcelain",
            "--",
            ".",
            ":!docs/results",
            ":!.planning",
            ":!*.md",
        ]);
        format!(
            "{}{}",
            git(&["rev-parse", "--short", "HEAD"]),
            if code.is_empty() { "" } else { "+dirty" }
        )
    })
}

fn cpu() -> String {
    if cfg!(windows) {
        let o = std::process::Command::new("reg")
            .args([
                "query",
                r"HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0",
                "/v",
                "ProcessorNameString",
            ])
            .output()
            .ok()
            .map(|o| String::from_utf8_lossy(&o.stdout).into_owned())
            .unwrap_or_default();
        o.lines()
            .find_map(|l| l.split_once("REG_SZ").map(|(_, v)| v.trim().to_string()))
            .unwrap_or_else(|| "not recorded".into())
    } else {
        std::fs::read_to_string("/proc/cpuinfo")
            .ok()
            .and_then(|t| {
                t.lines().find_map(|l| {
                    l.strip_prefix("model name")
                        .map(|v| v.trim_start_matches([' ', '\t', ':']).to_string())
                })
            })
            .unwrap_or_else(|| std::env::consts::ARCH.to_string())
    }
}

/// The processor and toolchain a result was measured on.
pub fn host() -> J {
    static H: OnceLock<J> = OnceLock::new();
    H.get_or_init(|| {
        jo! {
            "cpu" => cpu(),
            "threads" => std::thread::available_parallelism().map(|n| n.get()).unwrap_or(1),
            "engine" => "rust",
            "rustc" => env!("EFO_RUSTC"),
            "highs" => efo_highs::version(),
        }
    })
    .clone()
}

/// `provenance(p, **params)`.
pub fn provenance(name: &str, key: Option<&str>, sha256: Option<&str>, params: J) -> J {
    jo! {
        "revision" => revision(),
        "host" => host(),
        "instance" => name,
        "key" => key,
        "sha256" => sha256,
        "params" => params,
    }
}

/// An object from pairs, for `params`.
pub fn params(kv: Vec<(&str, J)>) -> J {
    let mut o = Obj::new();
    for (k, v) in kv {
        o.insert(k.into(), v);
    }
    J::O(o)
}
