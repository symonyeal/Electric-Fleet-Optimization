//! Electric vehicle routing on the CEC-2020 benchmark (Routing; Data §1).
//!
//! Legend (an Instance)
//!   node k ... file identifier k + 1; o the depot, i the customers, f the stations
//!   x, d ..... coordinates and unrounded Euclidean distances
//!   b ........ demand per node (0 off customers);  cap .. load capacity C
//!   q, h ..... battery capacity Q and consumption per unit distance; e_ij = h d_ij
//!
//! Routes are exchanged as 1-based node lists, depot at both ends (replay.rs).

#[cfg(test)]
pub mod enumerate;
pub mod paths;
pub mod r1;
pub mod r2;
pub mod r3;
pub mod replay;

use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

#[derive(Clone, Debug)]
pub struct Instance {
    pub name: String,
    pub x: Vec<[f64; 2]>,
    pub d: Vec<Vec<f64>>,
    pub o: usize,
    pub i: Vec<usize>,
    pub f: Vec<usize>,
    pub b: Vec<f64>,
    pub cap: f64,
    pub q: f64,
    pub h: f64,
    /// OPTIMAL_VALUE of the file, the report's published value; None when 0 or absent.
    pub published: Option<f64>,
}

impl Instance {
    /// The instance on coordinates x with the depot first, then customers i, then stations.
    fn new(
        name: String,
        x: Vec<[f64; 2]>,
        o: usize,
        f: Vec<usize>,
        b: Vec<f64>,
        cap: f64,
        q: f64,
        h: f64,
    ) -> Instance {
        let d = x
            .iter()
            .map(|a| x.iter().map(|c| (a[0] - c[0]).hypot(a[1] - c[1])).collect())
            .collect();
        let i = (0..x.len()).filter(|k| *k != o && !f.contains(k)).collect();
        Instance {
            name,
            x,
            d,
            o,
            i,
            f,
            b,
            cap,
            q,
            h,
            published: None,
        }
    }

    /// Restricted to the depot, customers i and stations f, renumbered in that order.
    pub fn sub(&self, i: &[usize], f: &[usize]) -> Instance {
        let v: Vec<usize> = std::iter::once(self.o)
            .chain(i.iter().copied())
            .chain(f.iter().copied())
            .collect();
        let ids: Vec<String> = i.iter().map(|k| (k + 1).to_string()).collect();
        Instance::new(
            format!("{}[{}]", self.name, ids.join(",")),
            v.iter().map(|&k| self.x[k]).collect(),
            0,
            (i.len() + 1..v.len()).collect(),
            v.iter().map(|&k| self.b[k]).collect(),
            self.cap,
            self.q,
            self.h,
        )
    }

    /// The k customers farthest from the depot, nearest of them last.
    pub fn far(&self, k: usize) -> Vec<usize> {
        let mut i = self.i.clone();
        i.sort_by(|a, c| self.d[self.o][*c].total_cmp(&self.d[self.o][*a]));
        i.truncate(k);
        i
    }
}

fn fail(path: &Path, why: impl std::fmt::Display) -> String {
    format!("{}: {why}", path.display())
}

/// Read a CEC-2020 EUC_2D file.
pub fn read(path: &Path) -> Result<Instance, String> {
    let text = fs::read_to_string(path).map_err(|e| fail(path, e))?;
    const SECTIONS: [&str; 4] = [
        "NODE_COORD_SECTION",
        "DEMAND_SECTION",
        "STATIONS_COORD_SECTION",
        "DEPOT_SECTION",
    ];
    let mut head = BTreeMap::new();
    let mut sec: BTreeMap<&str, Vec<Vec<&str>>> = BTreeMap::new();
    let mut cur = None;
    for line in text.lines() {
        let t: Vec<&str> = line.split_whitespace().collect();
        if t.is_empty() || t[0] == "EOF" {
            continue;
        }
        if let Some(s) = SECTIONS.iter().find(|s| **s == t[0]) {
            cur = Some(*s);
        } else if let Some(s) = cur {
            sec.entry(s).or_default().push(t);
        } else if let Some((k, v)) = line.split_once(':') {
            head.insert(k.trim().to_ascii_uppercase(), v.trim().to_owned());
        }
    }
    let get = |k: &str| {
        head.get(k)
            .map(String::as_str)
            .ok_or_else(|| fail(path, format!("no {k}")))
    };
    let num = |k: &str| -> Result<f64, String> {
        get(k)?.parse().map_err(|e| fail(path, format!("{k}: {e}")))
    };
    let parse =
        |s: &str| -> Result<f64, String> { s.parse().map_err(|e| fail(path, format!("{s}: {e}"))) };
    let rows = |s: &str| sec.get(s).cloned().unwrap_or_default();
    let kind = get("EDGE_WEIGHT_TYPE").or_else(|_| get("EDGE_WEIGHT_FORMAT"))?;
    if kind != "EUC_2D" {
        return Err(fail(
            path,
            format!("edge weight {kind}, only EUC_2D is read"),
        ));
    }
    let n = num("DIMENSION")? as usize;
    let xy = rows("NODE_COORD_SECTION");
    if xy.len() != n
        || xy
            .iter()
            .enumerate()
            .any(|(k, t)| t.len() < 3 || t[0] != (k + 1).to_string())
    {
        return Err(fail(
            path,
            format!("{} coordinates, DIMENSION {n}", xy.len()),
        ));
    }
    let x = xy
        .iter()
        .map(|t| Ok([parse(t[1])?, parse(t[2])?]))
        .collect::<Result<Vec<_>, String>>()?;
    let id = |t: &Vec<&str>| -> Result<usize, String> {
        match t[0].parse::<usize>() {
            Ok(k) if (1..=n).contains(&k) => Ok(k - 1),
            _ => Err(fail(path, format!("node {} out of range", t[0]))),
        }
    };
    let f = rows("STATIONS_COORD_SECTION")
        .iter()
        .map(id)
        .collect::<Result<Vec<_>, _>>()?;
    let depots = rows("DEPOT_SECTION")
        .iter()
        .filter(|t| t[0] != "-1")
        .map(id)
        .collect::<Result<Vec<_>, _>>()?;
    if f.len() != num("STATIONS")? as usize || depots.len() != 1 {
        return Err(fail(
            path,
            format!("{} stations, {} depots", f.len(), depots.len()),
        ));
    }
    let mut b = vec![0.0; n];
    let mut seen = Vec::new();
    for t in rows("DEMAND_SECTION") {
        let k = id(&t)?;
        b[k] = parse(t.get(1).ok_or_else(|| fail(path, "short demand row"))?)?;
        seen.push(k);
    }
    let mut p = Instance::new(
        path.file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("instance")
            .to_owned(),
        x,
        depots[0],
        f,
        b,
        num("CAPACITY")?,
        num("ENERGY_CAPACITY")?,
        num("ENERGY_CONSUMPTION")?,
    );
    let mut want = p.i.clone();
    want.push(p.o);
    want.sort_unstable();
    seen.sort_unstable();
    if seen != want || p.b[p.o] != 0.0 {
        return Err(fail(path, "demands do not cover the depot and customers"));
    }
    p.published = get("OPTIMAL_VALUE")
        .ok()
        .and_then(|s| s.split_whitespace().next()?.parse().ok())
        .filter(|v: &f64| *v > 0.0);
    Ok(p)
}

/// SHA-256 of a file, hexadecimal.
pub fn sha256(path: &Path) -> Result<String, String> {
    Ok(format!(
        "{:x}",
        Sha256::digest(fs::read(path).map_err(|e| fail(path, e))?)
    ))
}

/// The benchmark file of key (e.g. evrp-2019/E-n22-k4) under data/fetched, checked against the
/// pinned digests of data/evrp.sha256; its path and digest.
pub fn pinned(root: &Path, key: &str) -> Result<(std::path::PathBuf, String), String> {
    let manifest = root.join("data/evrp.sha256");
    let sums = fs::read_to_string(&manifest).map_err(|e| fail(&manifest, e))?;
    let want = format!("{key}.evrp");
    let pin = sums
        .lines()
        .find_map(|l| {
            l.split_once(char::is_whitespace)
                .filter(|(_, k)| k.trim() == want)
                .map(|(h, _)| h.to_owned())
        })
        .ok_or_else(|| fail(&manifest, format!("{want} is not pinned")))?;
    let path = root.join("data/fetched").join(&want);
    let got =
        sha256(&path).map_err(|e| format!("{e}; fetch the pinned benchmark (README, Run)"))?;
    if got != pin {
        return Err(fail(&path, "SHA-256 differs from data/evrp.sha256"));
    }
    Ok((path, got))
}

#[cfg(test)]
pub(crate) fn fixture(name: &str) -> Instance {
    read(
        &Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../tests/fixtures")
            .join(name),
    )
    .unwrap()
}

#[cfg(test)]
mod tests {
    #[test]
    fn tiny_is_read_as_written() {
        let p = super::fixture("tiny.evrp");
        assert_eq!(
            (p.o, p.i.clone(), p.f.clone()),
            (0, vec![1, 2, 3], vec![4, 5])
        );
        assert_eq!((p.cap, p.q, p.h, p.published), (10.0, 10.0, 1.0, None));
        assert_eq!(p.d[0][1], 5.0);
    }
}
