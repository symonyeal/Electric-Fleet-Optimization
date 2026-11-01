//! Result contract (Algorithms §6).
//!
//! A minimization result carries a feasible objective U, a valid lower bound L, and a gap only
//! when both are finite. Four fields keep apart what each party established:
//!
//! ```text
//! solver_status ....... the method's own termination (HiGHS, outer approximation, R2)
//! validation_status ... replayed: U is the cost of a solution the independent replay accepted;
//!                       validation_failed: a candidate was rejected, or the model's objective
//!                       disagrees with its replayed cost; not_available
//! certificate_status .. certified: |U - L| <= tol with a replayed U; open; invalid_bound:
//!                       L > U + tol; not_applicable: no bound is defined (infeasible)
//! status .............. the public state, derived from the three: optimal iff certified
//! ```
//!
//! with tol = eps (1 + max(1, |U|)), eps = 1e-6. A crossing within tol is floating-point noise
//! and is reported raw, never clamped; a larger one is a defect, never certified.

use serde::{Deserialize, Serialize};
use serde_json::Value;

pub const EPS: f64 = 1e-6;

pub fn tol(u: f64) -> f64 {
    EPS + EPS * u.abs().max(1.0)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Gap {
    Open,
    Closed,
    Crossed,
}

/// The two-sided rule every stopping test uses: closed (|U - L| <= tol), crossed (L > U + tol),
/// or open (either side absent, or U - L > tol).
pub fn gap(u: Option<f64>, l: Option<f64>) -> Gap {
    match (u, l) {
        (Some(u), Some(l)) if u - l < -tol(u) => Gap::Crossed,
        (Some(u), Some(l)) if u - l <= tol(u) => Gap::Closed,
        _ => Gap::Open,
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Record {
    pub model: String,
    pub instance: String,
    pub status: String,
    pub solver_status: String,
    pub validation_status: String,
    pub certificate_status: String,
    #[serde(rename = "U")]
    pub u: Option<f64>,
    #[serde(rename = "L")]
    pub l: Option<f64>,
    pub gap_rel: Option<f64>,
    pub certified: bool,
    pub defect: Option<String>,
    pub bound_source: Option<String>,
    pub objective: Option<f64>,
    pub message: String,
    pub elapsed: f64,
    /// Decisions (routes, duties, plans), parameters and counts of the model.
    pub detail: Value,
}

/// What a model returns before the contract classifies it.
pub struct Outcome {
    pub solver_status: &'static str,
    pub u: Option<f64>,
    pub l: Option<f64>,
    /// None: replayed when U is given, else not_available; Some(false): a replay refused it.
    pub replayed: Option<bool>,
    pub objective: Option<f64>,
    pub bound_source: &'static str,
    pub message: String,
    pub elapsed: f64,
    pub detail: Value,
}

/// (certificate_status, status) from the solver's termination, the bounds and the replay.
pub fn classify(
    solver: &str,
    u: Option<f64>,
    l: Option<f64>,
    validation: &str,
) -> (&'static str, String) {
    let cert = match gap(u, l) {
        Gap::Crossed => "invalid_bound",
        Gap::Closed if validation == "replayed" => "certified",
        _ if u.is_none() && l.is_none() && matches!(solver, "infeasible" | "unbounded") => {
            "not_applicable"
        }
        _ => "open",
    };
    let status = match cert {
        "invalid_bound" => "invalid_bound",
        "certified" => "optimal",
        _ if validation == "validation_failed" => "validation_failed",
        _ if matches!(solver, "optimal" | "feasible_limit") => {
            if u.is_some() {
                "feasible_limit"
            } else {
                "no_incumbent"
            }
        }
        _ => solver,
    };
    (cert, status.to_owned())
}

/// The record of outcome o of model on instance.
pub fn record(model: &str, instance: &str, o: Outcome) -> Record {
    let fin = |v: Option<f64>| v.filter(|x| x.is_finite());
    let (u, l) = (fin(o.u), fin(o.l));
    let mut validation = match (o.replayed, u) {
        (Some(false), _) => "validation_failed",
        (_, Some(_)) => "replayed",
        _ => "not_available",
    };
    let mut defects = Vec::new();
    if let (Some(f), Some(u)) = (o.objective, u)
        && (f - u).abs() > tol(u)
    {
        defects.push(format!("objective {f:.9} disagrees with replayed {u:.9}"));
        validation = "validation_failed";
    }
    let (cert, status) = classify(o.solver_status, u, l, validation);
    if cert == "invalid_bound" {
        defects.push("negative gap".into());
    }
    Record {
        model: model.into(),
        instance: instance.into(),
        status,
        solver_status: o.solver_status.into(),
        validation_status: validation.into(),
        certificate_status: cert.into(),
        u,
        l,
        gap_rel: u.zip(l).map(|(u, l)| (u - l) / u.abs().max(1.0)),
        certified: cert == "certified",
        defect: (!defects.is_empty()).then(|| defects.join("; ")),
        bound_source: l.map(|_| o.bound_source.to_owned()),
        objective: o.objective,
        message: o.message,
        elapsed: o.elapsed,
        detail: o.detail,
    }
}

impl Record {
    /// Contradictions between the stored public fields and what classify derives from the rest.
    pub fn contradictions(&self) -> Vec<String> {
        let (cert, status) = classify(&self.solver_status, self.u, self.l, &self.validation_status);
        let mut out = Vec::new();
        if (cert, status.as_str()) != (self.certificate_status.as_str(), self.status.as_str()) {
            out.push(format!(
                "stored {}/{}, derived {cert}/{status}",
                self.certificate_status, self.status
            ));
        }
        if self.certified != (cert == "certified") {
            out.push("certified flag".into());
        }
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rec(u: f64, l: f64) -> Record {
        record(
            "R1",
            "x",
            Outcome {
                solver_status: "optimal",
                u: Some(u),
                l: Some(l),
                replayed: None,
                objective: None,
                bound_source: "highs_dual",
                message: String::new(),
                elapsed: 0.0,
                detail: Value::Null,
            },
        )
    }

    #[test]
    fn the_certificate_is_two_sided() {
        let r = rec(100.0, 100.5);
        assert_eq!(
            (r.certificate_status.as_str(), r.status.as_str()),
            ("invalid_bound", "invalid_bound")
        );
        assert!(!r.certified && r.defect.is_some());
        // tol = 1e-6 + 1e-4: a crossing of 1e-5 is noise, certified and reported raw.
        let r = rec(100.0, 100.0 + 1e-5);
        assert!(r.certified && r.defect.is_none() && r.gap_rel.unwrap() < 0.0);
        assert_eq!(gap(Some(100.0), Some(99.0)), Gap::Open);
        assert_eq!(gap(None, Some(99.0)), Gap::Open);
        assert!(rec(5.0, 1.0).contradictions().is_empty());
    }
}
