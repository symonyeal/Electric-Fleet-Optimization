//! Declared engineering scenarios (Data §3).
//!
//! A scenario is a TOML file. Every number is a table {value, unit, source}, source a citation
//! recorded in docs/SOURCES.md or the word `illustrative`; strings and lists (names, stop ids)
//! are structure and carry neither. load() strips the tables, refuses unknown keys, and checks
//! every domain the models assume: a value outside its domain is refused before any row is built.

use serde::Deserialize;
use serde::de::DeserializeOwned;
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Charger {
    #[serde(rename = "P")]
    pub p: f64,
    pub eta: f64,
    pub alpha: f64,
}

/// R3 (Routing §5), in the benchmark's units: distance u, energy e = h u, hours.
#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Recharge {
    pub time: RechargeTime,
    pub charger: Charger,
    pub cost: RechargeCost,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RechargeTime {
    pub speed: f64,
    pub service: f64,
    #[serde(rename = "T")]
    pub t: f64,
    pub tau_min: f64,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RechargeCost {
    pub distance: f64,
    pub energy: f64,
    pub dwell: f64,
}

/// A transit scenario (Models §1, §3): seconds, km, kWh, kW, CAD.
#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Transit {
    pub time: Time,
    pub deadhead: Deadhead,
    pub depot: Place,
    pub battery: Battery,
    pub charger: Charger,
    pub sites: BTreeMap<String, Site>,
    pub cost: Cost,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Time {
    pub delta: f64,
    pub window: f64,
    pub layover: f64,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Deadhead {
    pub speed: f64,
    pub detour: f64,
}

#[derive(Clone, Copy, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Place {
    pub lat: f64,
    pub lon: f64,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Battery {
    #[serde(rename = "B")]
    pub b: f64,
    pub reserve: f64,
    pub smax: f64,
    pub s0: f64,
    pub kappa: f64,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Site {
    pub name: String,
    pub stops: Vec<String>,
    pub nbar: f64,
    #[serde(rename = "G0")]
    pub g0: f64,
    pub hbar: f64,
    #[serde(rename = "L")]
    pub l: f64,
}

/// Tariff terms (Data §3): rider multiplies every electricity charge by 1 + rider; demand is
/// billed over [peak_from, peak_to) hours of the day, wrapping past midnight when
/// peak_from > peak_to; absent, the whole day.
#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Cost {
    #[serde(rename = "F")]
    pub f: f64,
    pub deadhead: f64,
    pub energy: f64,
    pub depot_energy: f64,
    pub peak: f64,
    pub site: f64,
    pub plug: f64,
    pub upgrade: f64,
    #[serde(default)]
    pub basic: f64,
    #[serde(default)]
    pub rider: f64,
    pub peak_from: Option<f64>,
    pub peak_to: Option<f64>,
}

impl Cost {
    /// 1 + rider, and the billing window [w0, w1) in seconds of the day.
    pub fn tariff(&self) -> (f64, f64, f64) {
        (
            1.0 + self.rider,
            3600.0 * self.peak_from.unwrap_or(0.0),
            3600.0 * self.peak_to.unwrap_or(24.0),
        )
    }
}

/// Second t of the service day lies in the billing window [w0, w1) of its day.
pub fn billed(t: f64, w0: f64, w1: f64) -> bool {
    let s = t.rem_euclid(86400.0);
    if w0 <= w1 {
        w0 <= s && s < w1
    } else {
        s >= w0 || s < w1
    }
}

/// Replace each {value, unit, source} by its value; refuse bare numbers and incomplete tables.
fn strip(v: toml::Value, path: &str, err: &mut Vec<String>) -> toml::Value {
    match v {
        toml::Value::Table(t) if t.contains_key("value") => {
            let named = |k: &str| {
                t.get(k)
                    .and_then(|x| x.as_str())
                    .is_some_and(|s| !s.is_empty())
            };
            if !named("unit") || !named("source") || t.len() != 3 {
                err.push(format!("{path}: a value needs exactly a unit and a source"));
            }
            match t["value"]
                .as_float()
                .or_else(|| t["value"].as_integer().map(|i| i as f64))
            {
                Some(x) if x.is_finite() => toml::Value::Float(x),
                _ => {
                    err.push(format!("{path}: value is not a finite number"));
                    toml::Value::Float(f64::NAN)
                }
            }
        }
        toml::Value::Table(t) => toml::Value::Table(
            t.into_iter()
                .map(|(k, x)| {
                    let p = if path.is_empty() {
                        k.clone()
                    } else {
                        format!("{path}.{k}")
                    };
                    let x = strip(x, &p, err);
                    (k, x)
                })
                .collect(),
        ),
        toml::Value::Float(_) | toml::Value::Integer(_) => {
            err.push(format!(
                "{path}: bare number; write {{value, unit, source}}"
            ));
            v
        }
        v => v,
    }
}

fn parse<T: DeserializeOwned>(path: &Path) -> Result<T, String> {
    let at = |e: &dyn std::fmt::Display| format!("{}: {e}", path.display());
    let raw: toml::Value =
        toml::from_str(&fs::read_to_string(path).map_err(|e| at(&e))?).map_err(|e| at(&e))?;
    let mut err = Vec::new();
    let v = strip(raw, "", &mut err);
    if !err.is_empty() {
        return Err(at(&err.join("; ")));
    }
    v.try_into().map_err(|e| at(&e))
}

/// Collects "name = x: must be domain" for every failed test.
struct Domains(Vec<String>);

impl Domains {
    fn check(&mut self, name: &str, x: f64, ok: bool, domain: &str) {
        if !ok {
            self.0.push(format!("{name} = {x}: must be {domain}"));
        }
    }

    fn positive(&mut self, name: &str, x: f64) {
        self.check(name, x, x > 0.0, "> 0");
    }

    fn nonneg(&mut self, name: &str, x: f64) {
        self.check(name, x, x >= 0.0, ">= 0");
    }

    fn charger(&mut self, c: &Charger) {
        self.positive("charger.P", c.p);
        self.check(
            "charger.eta",
            c.eta,
            c.eta > 0.0 && c.eta <= 1.0,
            "in (0, 1]",
        );
        self.nonneg("charger.alpha", c.alpha);
    }

    fn done(self, path: &Path) -> Result<(), String> {
        if self.0.is_empty() {
            Ok(())
        } else {
            Err(format!(
                "{}: invalid scenario: {}",
                path.display(),
                self.0.join("; ")
            ))
        }
    }
}

/// Command-line overrides obey the domains of the scenario files: alpha >= 0, battery B > 0.
pub fn overrides(alpha: Option<f64>, battery: Option<f64>) -> Result<(), String> {
    let mut d = Domains(Vec::new());
    if let Some(a) = alpha {
        d.nonneg("--alpha", a);
    }
    if let Some(b) = battery {
        d.positive("--battery", b);
    }
    if d.0.is_empty() {
        Ok(())
    } else {
        Err(format!("invalid override: {}", d.0.join("; ")))
    }
}

pub fn recharge(path: &Path) -> Result<Recharge, String> {
    let s: Recharge = parse(path)?;
    let mut d = Domains(Vec::new());
    d.positive("time.speed", s.time.speed);
    d.nonneg("time.service", s.time.service);
    d.positive("time.T", s.time.t);
    d.positive("time.tau_min", s.time.tau_min);
    d.charger(&s.charger);
    for (k, x) in [
        ("distance", s.cost.distance),
        ("energy", s.cost.energy),
        ("dwell", s.cost.dwell),
    ] {
        d.nonneg(&format!("cost.{k}"), x);
    }
    d.done(path)?;
    Ok(s)
}

pub fn transit(path: &Path) -> Result<Transit, String> {
    let s: Transit = parse(path)?;
    let mut d = Domains(Vec::new());
    d.positive("time.delta", s.time.delta);
    d.positive("time.window", s.time.window);
    d.nonneg("time.layover", s.time.layover);
    d.positive("deadhead.speed", s.deadhead.speed);
    d.positive("deadhead.detour", s.deadhead.detour);
    d.positive("battery.B", s.battery.b);
    d.nonneg("battery.kappa", s.battery.kappa);
    let b = &s.battery;
    d.check(
        "battery.s0",
        b.s0,
        0.0 <= b.reserve && b.reserve <= b.s0 && b.s0 <= b.smax && b.smax <= 1.0,
        "within 0 <= reserve <= s0 <= smax <= 1",
    );
    d.charger(&s.charger);
    let c = &s.cost;
    for (k, x) in [
        ("F", c.f),
        ("deadhead", c.deadhead),
        ("energy", c.energy),
        ("depot_energy", c.depot_energy),
        ("peak", c.peak),
        ("site", c.site),
        ("plug", c.plug),
        ("upgrade", c.upgrade),
        ("basic", c.basic),
    ] {
        d.nonneg(&format!("cost.{k}"), x);
    }
    d.check("cost.rider", c.rider, c.rider > -1.0, "> -1");
    match (c.peak_from, c.peak_to) {
        (None, None) => {}
        (Some(a), Some(z)) => {
            d.check("cost.peak_from", a, (0.0..24.0).contains(&a), "in [0, 24)");
            d.check(
                "cost.peak_to",
                z,
                z > 0.0 && z <= 24.0 && z != a,
                "in (0, 24] and not peak_from",
            );
        }
        _ => {
            d.0.push("cost: peak_from and peak_to are given together or not at all".into())
        }
    }
    let mut owner = BTreeMap::new();
    for (k, t) in &s.sites {
        d.check(
            &format!("sites.{k}.nbar"),
            t.nbar,
            t.nbar >= 0.0 && t.nbar.fract() == 0.0,
            "a nonnegative integer",
        );
        d.nonneg(&format!("sites.{k}.hbar"), t.hbar);
        d.nonneg(&format!("sites.{k}.G0"), t.g0);
        d.nonneg(&format!("sites.{k}.L"), t.l);
        for stop in &t.stops {
            if let Some(o) = owner.insert(stop, k) {
                d.0.push(format!("stop {stop} belongs to sites {o} and {k}"));
            }
        }
    }
    d.done(path)?;
    Ok(s)
}

#[cfg(test)]
pub(crate) fn data(name: &str) -> std::path::PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../data/scenarios")
        .join(name)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_committed_scenario_loads() {
        for f in fs::read_dir(data("")).unwrap() {
            let p = f.unwrap().path();
            let ok = if p.file_name().unwrap() == "r3.toml" {
                recharge(&p).map(|_| ())
            } else {
                transit(&p).map(|_| ())
            };
            assert!(ok.is_ok(), "{ok:?}");
        }
    }

    #[test]
    fn domains_and_declarations_are_enforced() {
        let dir = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../target/scenario-test");
        fs::create_dir_all(&dir).unwrap();
        let base = fs::read_to_string(data("route100.toml")).unwrap();
        for (from, to, why) in [
            ("eta = {value = 0.92", "eta = {value = 1.5", "charger.eta"),
            (
                "reserve = {value = 0.20",
                "reserve = {value = 0.95",
                "battery.s0",
            ),
            (
                "delta = {value = 300.0, unit = \"s\", source = \"illustrative\"}",
                "delta = 300.0",
                "bare number",
            ),
            (
                "[cost]",
                "[cost]\npeak_from = {value = 6.0, unit = \"h\", source = \"x\"}",
                "together",
            ),
            (
                "stops = [\"5989\", \"10929\"]",
                "stops = [\"745\"]",
                "belongs to",
            ),
        ] {
            let f = dir.join("s.toml");
            fs::write(&f, base.replacen(from, to, 1)).unwrap();
            let e = transit(&f).unwrap_err();
            assert!(e.contains(why), "{e}");
        }
        for (a, b) in [
            (Some(-1.0), None),
            (Some(f64::NAN), None),
            (None, Some(0.0)),
            (None, Some(f64::NAN)),
        ] {
            assert!(overrides(a, b).is_err(), "{a:?} {b:?}");
        }
        assert!(overrides(Some(0.0), Some(100.0)).is_ok());
        assert!(
            billed(23.5 * 3600.0, 22.0 * 3600.0, 6.0 * 3600.0)
                && !billed(12.0 * 3600.0, 22.0 * 3600.0, 6.0 * 3600.0)
        );
        assert!(billed(86400.0 + 3600.0, 0.0, 7200.0));
    }
}
