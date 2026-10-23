//! CEC-2020 EVRP benchmark files (Data §1), pinned to evrp-python commit 16d3499.
//!
//! Legend (an instance P; node k is file identifier k+1; the depot is the DEPOT_SECTION node)
//!   X ...... N x 2 coordinates            D ...... N x N unrounded Euclidean distances
//!   I, F ... customer and station indices b ...... demand per node (0 off customers)
//!   C, Q, h  load capacity, battery capacity, consumption per unit distance
//!   K ...... VEHICLES, the report's minimum number of routes
//!   opt .... OPTIMAL_VALUE as a number, None when 0, '-' or absent

use crate::digest::sha256_hex;
use std::collections::HashMap;
use std::path::{Path, PathBuf};

pub const COMMIT: &str = "16d3499799ab7aa7bc3f11a5eaf8604947389462";
pub const URL: &str = "https://raw.githubusercontent.com/NeiH4207/evrp-python/16d3499799ab7aa7bc3f11a5eaf8604947389462/benchmarks/";

#[derive(Clone, Debug, PartialEq)]
pub struct P {
    pub name: String,
    pub name_hdr: String,
    pub x: Vec<[f64; 2]>,
    pub d: Vec<Vec<f64>>,
    pub depot: usize,
    pub i: Vec<usize>,
    pub f: Vec<usize>,
    pub b: Vec<f64>,
    pub c: f64,
    pub q: f64,
    pub h: f64,
    pub k: i64,
    pub opt: Option<f64>,
    pub key: Option<String>,
    pub sha256: Option<String>,
}

impl P {
    pub fn n(&self) -> usize {
        self.x.len()
    }
    pub fn is_customer(&self, k: usize) -> bool {
        self.i.contains(&k)
    }
}

/// `np.sqrt(((X[:, None] - X[None]) ** 2).sum(-1))`.
pub fn dist(x: &[[f64; 2]]) -> Vec<Vec<f64>> {
    x.iter()
        .map(|a| {
            x.iter()
                .map(|z| {
                    let (dx, dy) = (a[0] - z[0], a[1] - z[1]);
                    (dx * dx + dy * dy).sqrt()
                })
                .collect()
        })
        .collect()
}

/// OPTIMAL_VALUE: leading number; 0 and '-' mean unknown.
pub fn value(s: &str) -> Option<f64> {
    let t = s.trim_start();
    let n: String = t
        .chars()
        .take_while(|c| c.is_ascii_digit() || *c == '.')
        .collect();
    let v = n.parse::<f64>().unwrap_or(0.0);
    if v == 0.0 { None } else { Some(v) }
}

const SECTIONS: [&str; 4] = [
    "NODE_COORD_SECTION",
    "DEMAND_SECTION",
    "STATIONS_COORD_SECTION",
    "DEPOT_SECTION",
];

fn bad(path: &Path, m: String) -> String {
    format!(
        "{}: {m}",
        path.file_name()
            .map(|s| s.to_string_lossy())
            .unwrap_or_default()
    )
}

/// Parse an instance file.
pub fn read(path: &Path) -> Result<P, String> {
    let text = std::fs::read_to_string(path).map_err(|e| bad(path, e.to_string()))?;
    let mut head: HashMap<String, String> = HashMap::new();
    let mut sec: HashMap<&str, Vec<Vec<String>>> = SECTIONS.iter().map(|s| (*s, vec![])).collect();
    let mut cur: Option<&str> = None;
    for line in text.lines() {
        let t: Vec<String> = line.split_whitespace().map(String::from).collect();
        if t.is_empty() || t[0] == "EOF" {
            continue;
        }
        if let Some(s) = SECTIONS.iter().find(|s| **s == t[0]) {
            cur = Some(s);
        } else if let Some(c) = cur {
            sec.get_mut(c).unwrap().push(t);
        } else {
            let (k, v) = line.split_once(':').unwrap_or((line, ""));
            head.insert(k.trim().to_uppercase(), v.trim().to_string());
        }
    }
    let ew = head
        .get("EDGE_WEIGHT_TYPE")
        .or(head.get("EDGE_WEIGHT_FORMAT"))
        .cloned();
    if ew.as_deref() != Some("EUC_2D") {
        return Err(bad(
            path,
            format!("edge weight {ew:?}, only EUC_2D is read"),
        ));
    }
    let num = |k: &str| -> Result<f64, String> {
        head.get(k)
            .ok_or(bad(path, format!("{k} missing")))?
            .parse::<f64>()
            .map_err(|e| bad(path, format!("{k}: {e}")))
    };
    let int = |k: &str| -> Result<i64, String> {
        head.get(k)
            .ok_or(bad(path, format!("{k} missing")))?
            .parse::<i64>()
            .map_err(|e| bad(path, format!("{k}: {e}")))
    };
    let (n, s) = (int("DIMENSION")? as usize, int("STATIONS")? as usize);
    let xy = &sec["NODE_COORD_SECTION"];
    let ids: Vec<i64> = xy.iter().map(|t| t[0].parse().unwrap_or(-1)).collect();
    if ids != (1..=n as i64).collect::<Vec<_>>() {
        return Err(bad(
            path,
            format!("{} coordinates, DIMENSION {n}", xy.len()),
        ));
    }
    let f: Vec<usize> = sec["STATIONS_COORD_SECTION"]
        .iter()
        .map(|t| t[0].parse::<usize>().unwrap() - 1)
        .collect();
    let depot: Vec<usize> = sec["DEPOT_SECTION"]
        .iter()
        .filter(|t| t[0] != "-1")
        .map(|t| t[0].parse::<usize>().unwrap() - 1)
        .collect();
    let mut dem: Vec<(usize, f64)> = vec![];
    for t in &sec["DEMAND_SECTION"] {
        let k = t[0].parse::<usize>().unwrap() - 1;
        let v = t[1].parse::<f64>().map_err(|e| bad(path, e.to_string()))?;
        if let Some(e) = dem.iter_mut().find(|e| e.0 == k) {
            e.1 = v;
        } else {
            dem.push((k, v));
        }
    }
    if f.len() != s || depot.len() != 1 {
        return Err(bad(
            path,
            format!(
                "{} stations for STATIONS {s}, {} depots",
                f.len(),
                depot.len()
            ),
        ));
    }
    let depot = depot[0];
    let i: Vec<usize> = (0..n).filter(|k| !f.contains(k) && *k != depot).collect();
    let mut keys: Vec<usize> = dem.iter().map(|e| e.0).collect();
    keys.sort();
    let mut want: Vec<usize> = i.iter().copied().chain([depot]).collect();
    want.sort();
    let dd = dem.iter().find(|e| e.0 == depot).map(|e| e.1);
    if keys != want || dd != Some(0.0) {
        return Err(bad(
            path,
            "demands do not cover the depot and customers".into(),
        ));
    }
    let x: Vec<[f64; 2]> = xy
        .iter()
        .map(|t| [t[1].parse().unwrap(), t[2].parse().unwrap()])
        .collect();
    let mut b = vec![0.0; n];
    for &k in &i {
        b[k] = dem.iter().find(|e| e.0 == k).unwrap().1;
    }
    let stem = path.file_stem().unwrap().to_string_lossy().into_owned();
    let nm = head.get("NAME").cloned().unwrap_or_default();
    Ok(P {
        name: stem,
        name_hdr: nm.strip_suffix(".evrp").unwrap_or(&nm).to_string(),
        d: dist(&x),
        x,
        depot,
        i,
        f,
        b,
        c: num("CAPACITY")?,
        q: num("ENERGY_CAPACITY")?,
        h: num("ENERGY_CONSUMPTION")?,
        k: int("VEHICLES")?,
        opt: value(head.get("OPTIMAL_VALUE").map(String::as_str).unwrap_or("0")),
        key: None,
        sha256: None,
    })
}

/// The committed manifest `data/evrp.sha256`: (key "evrp-2019/E-n22-k4.evrp", sha256).
pub fn manifest(root: &Path) -> Vec<(String, String)> {
    let t = std::fs::read_to_string(root.join("data/evrp.sha256")).unwrap_or_default();
    t.lines()
        .filter_map(|l| {
            let mut w = l.split_whitespace();
            let h = w.next()?;
            let k = w.next()?;
            Some((k.to_string(), h.to_string()))
        })
        .collect()
}

/// Instance keys, sorted, e.g. "evrp-2019/E-n22-k4".
pub fn keys(root: &Path) -> Vec<String> {
    let mut k: Vec<String> = manifest(root)
        .into_iter()
        .map(|(k, _)| k.trim_end_matches(".evrp").to_string())
        .collect();
    k.sort();
    k
}

pub fn fetched(root: &Path) -> PathBuf {
    root.join("data").join("fetched")
}

/// The unique key ending in "/name", or the key itself when it names a set.
pub fn key(root: &Path, name: &str) -> Result<String, String> {
    if name.contains('/') {
        return Ok(name.to_string());
    }
    let k: Vec<String> = keys(root)
        .into_iter()
        .filter(|k| k.ends_with(&format!("/{name}")))
        .collect();
    if k.len() != 1 {
        return Err(format!(
            "{name}: {} instances match; use set/name, e.g. evrp-2019/{name}",
            k.len()
        ));
    }
    Ok(k[0].clone())
}

/// Fetch an instance with `curl` (evrp-python at the pinned commit) unless present.
pub fn fetch(root: &Path, key: &str) -> Result<(), String> {
    let f = fetched(root).join(format!("{key}.evrp"));
    if f.exists() {
        return Ok(());
    }
    std::fs::create_dir_all(f.parent().unwrap()).map_err(|e| e.to_string())?;
    let st = std::process::Command::new("curl")
        .args(["-fsSL", "-o"])
        .arg(&f)
        .arg(format!("{URL}{key}.evrp"))
        .status()
        .map_err(|e| format!("curl: {e}"))?;
    if !st.success() {
        return Err(format!("{key}: download failed"));
    }
    Ok(())
}

/// Fetch if absent, verify SHA-256 against the committed manifest, read.
pub fn load(root: &Path, key: &str) -> Result<P, String> {
    let want = manifest(root)
        .into_iter()
        .find(|(k, _)| k == &format!("{key}.evrp"))
        .map(|(_, h)| h)
        .ok_or(format!("{key}: not in data/evrp.sha256"))?;
    fetch(root, key)?;
    let f = fetched(root).join(format!("{key}.evrp"));
    let bytes = std::fs::read(&f).map_err(|e| e.to_string())?;
    if sha256_hex(&bytes) != want {
        return Err(format!("{key}: SHA-256 differs from data/evrp.sha256"));
    }
    let mut p = read(&f)?;
    p.key = Some(key.to_string());
    p.sha256 = Some(want);
    Ok(p)
}

/// The instance restricted to the depot, customers I and stations F, renumbered in that order;
/// VEHICLES becomes the capacity bound ceil(sum b / C).
pub fn sub(p: &P, i: &[usize], f: &[usize]) -> P {
    let v: Vec<usize> = [p.depot]
        .into_iter()
        .chain(i.iter().copied())
        .chain(f.iter().copied())
        .collect();
    let x: Vec<[f64; 2]> = v.iter().map(|&k| p.x[k]).collect();
    let b: Vec<f64> = v.iter().map(|&k| p.b[k]).collect();
    let tot = crate::num::np_sum(&b);
    P {
        name: format!(
            "{}[{}]",
            p.name,
            i.iter()
                .map(|k| (k + 1).to_string())
                .collect::<Vec<_>>()
                .join(",")
        ),
        name_hdr: String::new(),
        d: dist(&x),
        x,
        depot: 0,
        i: (1..=i.len()).collect(),
        f: (i.len() + 1..v.len()).collect(),
        b,
        c: p.c,
        q: p.q,
        h: p.h,
        k: (tot / p.c - 1e-9).ceil() as i64,
        opt: None,
        key: None,
        sha256: None,
    }
}
