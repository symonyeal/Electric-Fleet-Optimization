//! A case's inputs, its run, and the replay of a stored result (the shell around the models).
//!
//! Inputs live in the repository: data/evrp.sha256 pins the fetched benchmark files, data/seeds
//! holds replayed routes that seed R2, data/scenarios the declared scenarios, data/corridors the
//! GTFS extracts.

use crate::bundle::{Bundle, Case};
use crate::cert::Record;
use crate::evrp::{self, Instance, r1::r1, r2::r2, r3::r3, replay};
use crate::scenario::{self, Recharge, Transit};
use crate::transit::{self, Corridor, fleet, m0::m0, replay::replay_energy};
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

/// Files read, by repository path, with their SHA-256.
pub type Files = BTreeMap<String, String>;

fn rel(root: &Path, p: &Path) -> String {
    p.strip_prefix(root)
        .unwrap_or(p)
        .to_string_lossy()
        .replace('\\', "/")
}

/// Record the digest of a tracked text input, CRLF read as LF, so that a Windows and a Linux
/// checkout of one commit agree.
fn sha(root: &Path, p: &Path, files: &mut Files) -> Result<(), String> {
    let text = fs::read(p).map_err(|e| format!("{}: {e}", p.display()))?;
    let lf: Vec<u8> = (0..text.len())
        .filter(|&k| !(text[k] == b'\r' && text.get(k + 1) == Some(&b'\n')))
        .map(|k| text[k])
        .collect();
    files.insert(
        rel(root, p),
        format!("{:x}", <sha2::Sha256 as sha2::Digest>::digest(&lf)),
    );
    Ok(())
}

/// The pinned instance of case (restricted to its far customers when asked).
pub fn instance(root: &Path, case: &Case, files: &mut Files) -> Result<Instance, String> {
    let sums = fs::read_to_string(root.join("data/evrp.sha256"))
        .map_err(|e| format!("data/evrp.sha256: {e}"))?;
    let keys: Vec<&str> = sums
        .lines()
        .filter_map(|l| l.split_whitespace().nth(1)?.strip_suffix(".evrp"))
        .filter(|k| k.rsplit('/').next() == Some(&case.instance))
        .collect();
    let [key] = keys[..] else {
        return Err(format!(
            "{}: {} pinned instances match",
            case.instance,
            keys.len()
        ));
    };
    let (path, digest) = evrp::pinned(root, key)?;
    files.insert(rel(root, &path), digest);
    let p = evrp::read(&path)?;
    Ok(match case.far {
        Some(k) => p.sub(&p.far(k), &p.f),
        None => p,
    })
}

pub fn recharge(root: &Path, case: &Case, files: &mut Files) -> Result<Recharge, String> {
    let path = root.join("data/scenarios/r3.toml");
    sha(root, &path, files)?;
    let mut s = scenario::recharge(&path)?;
    if let Some(a) = case.alpha {
        s.charger.alpha = a;
    }
    Ok(s)
}

/// The corridor (cut at case.until) and scenario (with case's battery and alpha) of case.
pub fn transit(root: &Path, case: &Case, files: &mut Files) -> Result<(Corridor, Transit), String> {
    let cp = root
        .join("data/corridors")
        .join(format!("{}.json", case.instance));
    let name = match &case.scenario {
        Some(s) => format!("{}-{s}.toml", case.instance),
        None => format!("{}.toml", case.instance),
    };
    let sp = root.join("data/scenarios").join(name);
    sha(root, &cp, files)?;
    sha(root, &sp, files)?;
    let c = transit::corridor(&cp)?;
    let mut v = scenario::transit(&sp)?;
    if let Some(b) = case.battery {
        v.battery.b = b;
    }
    if let Some(a) = case.alpha {
        v.charger.alpha = a;
    }
    Ok((case.until.map_or(c.clone(), |h| transit::until(&c, h)), v))
}

/// Replayed routes of data/seeds/<instance>-*.routes.
fn seeds(root: &Path, p: &Instance, files: &mut Files) -> Result<Vec<Vec<usize>>, String> {
    let mut out = Vec::new();
    let Ok(dir) = fs::read_dir(root.join("data/seeds")) else {
        return Ok(out);
    };
    let mut paths: Vec<_> = dir
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|f| {
            f.file_name()
                .and_then(|n| n.to_str())
                .is_some_and(|n| n.starts_with(&format!("{}-", p.name)) && n.ends_with(".routes"))
        })
        .collect();
    paths.sort();
    for f in paths {
        let r = replay::read_routes(&f)?;
        if replay::replay(p, &r, true).ok {
            sha(root, &f, files)?;
            out.extend(r);
        }
    }
    Ok(out)
}

/// Run case; its record and the files it read.
pub fn run(root: &Path, case: &Case) -> Result<(Record, Files), String> {
    let mut files = Files::new();
    let r = match (case.track.as_str(), case.model.as_str()) {
        ("evrp", "R1") => r1(&instance(root, case, &mut files)?, case.time, 1e-7),
        ("evrp", "R2") => {
            let p = instance(root, case, &mut files)?;
            let init = if case.far.is_none() {
                seeds(root, &p, &mut files)?
            } else {
                Vec::new()
            };
            r2(&p, &init, case.time)
        }
        ("evrp", "R3") => {
            let p = instance(root, case, &mut files)?;
            r3(&p, &recharge(root, case, &mut files)?, 60, case.time)
        }
        ("transit", m) => {
            let (c, v) = transit(root, case, &mut files)?;
            let name = case.stem();
            let name = name.strip_suffix(&format!("-{m}")).unwrap_or(&name);
            match m {
                "M0" => m0(&c, &v, name),
                "M1" => fleet::m1(&c, &v, name, &BTreeMap::new(), case.time, 1e-6),
                "M2" => fleet::m2(&c, &v, name, &BTreeMap::new(), 40, case.time),
                _ => return Err(format!("transit models are M0, M1, M2, not {m}")),
            }
        }
        (t, m) => {
            return Err(format!(
                "no model {m} on track {t}: evrp has R1, R2, R3; transit M0, M1, M2"
            ));
        }
    };
    Ok((r, files))
}

/// U recomputed by the independent replay from the stored decisions, None when they do not
/// replay; with the inputs' current digests.
pub fn replayed(root: &Path, b: &Bundle) -> Result<(Option<f64>, Files), String> {
    let mut files = Files::new();
    let d = &b.record.detail;
    let get = |k: &str| d.get(k).cloned().unwrap_or_default();
    let json = |e: serde_json::Error| e.to_string();
    let u = match (b.case.track.as_str(), b.case.model.as_str()) {
        ("evrp", m) => {
            let p = instance(root, &b.case, &mut files)?;
            if m == "R2" && b.case.far.is_none() {
                seeds(root, &p, &mut files)?;
            }
            // read even without routes, so that the digests match those the run recorded
            let sc = (m == "R3")
                .then(|| recharge(root, &b.case, &mut files))
                .transpose()?;
            let routes: Option<Vec<Vec<usize>>> =
                serde_json::from_value(get("routes")).map_err(json)?;
            match (routes, m) {
                (None, _) => None,
                (Some(r), "R3") => {
                    let sc = sc.as_ref().unwrap();
                    let ch: BTreeMap<String, (f64, f64)> =
                        serde_json::from_value(get("charges")).map_err(json)?;
                    let ch = ch.into_iter().map(|(k, v)| {
                        let (a, z) = k.split_once(':').unwrap_or(("0", "0"));
                        ((a.parse().unwrap_or(0), z.parse().unwrap_or(0)), v)
                    });
                    let rp = replay::replay_charge(&p, sc, &r, &ch.collect());
                    rp.ok.then_some(rp.cost)
                }
                (Some(r), _) => Some(replay::replay(&p, &r, true))
                    .filter(|rp| rp.ok)
                    .map(|rp| rp.length),
            }
        }
        (_, "M0") => {
            let (c, v) = transit(root, &b.case, &mut files)?;
            let duties: Vec<Vec<String>> = serde_json::from_value(get("duties")).map_err(json)?;
            transit::replay::replay(&c, &duties, &v)
                .ok
                .then_some(duties.len() as f64)
        }
        (_, m) => {
            let (c, v) = transit(root, &b.case, &mut files)?;
            let s = get("schedule");
            if s.is_null() {
                None
            } else {
                let duties: Vec<Vec<String>> =
                    serde_json::from_value(s["duties"].clone()).map_err(json)?;
                let plan = serde_json::from_value(s["plan"].clone()).map_err(json)?;
                let infra = serde_json::from_value(s["infra"].clone()).map_err(json)?;
                let rp = replay_energy(&c, &v, &duties, &plan, &infra, m == "M2");
                rp.ok.then_some(rp.cost)
            }
        }
    };
    Ok((u, files))
}
