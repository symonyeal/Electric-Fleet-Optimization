//! The results page and the README block, from the admitted bundles of docs/results.
//!
//! A bundle is admitted only if its code was committed, its record is self-consistent, its
//! formulation is current, its inputs are unchanged, and the independent replay of its stored
//! decisions reproduces its U. An upper bound needs no other provenance: routes or a schedule the
//! replay accepts certify their own cost, so the seed routes count too. A lower bound cannot be
//! replayed and counts only from an admitted bundle.

use crate::bundle::Bundle;
use crate::cert::{Gap, gap, tol};
use crate::evrp::{self, r1, r2, r3, replay};
use crate::run::{self, replayed};
use crate::transit::{fleet, m0};
use std::fmt::Write;
use std::fs;
use std::path::{Path, PathBuf};

/// The benchmark instances of the results table, in order.
pub const EVRP: [&str; 7] = [
    "E-n22-k4",
    "E-n23-k3",
    "E-n30-k3",
    "E-n33-k4",
    "E-n51-k5",
    "E-n76-k7",
    "E-n101-k8",
];

fn formulation(model: &str) -> &'static str {
    match model {
        "R1" => r1::FORMULATION,
        "R2" => r2::FORMULATION,
        "R3" => r3::FORMULATION,
        "M0" => m0::FORMULATION,
        "M1" => fleet::M1,
        _ => fleet::M2,
    }
}

/// Bundles admitted, with the replayed U, and those refused, with reasons.
pub struct Collected {
    pub admitted: Vec<(PathBuf, Bundle, Option<f64>)>,
    pub refused: Vec<(PathBuf, Vec<String>)>,
}

pub fn collect(root: &Path) -> Collected {
    let mut c = Collected {
        admitted: Vec::new(),
        refused: Vec::new(),
    };
    let mut paths: Vec<PathBuf> = ["evrp", "transit"]
        .iter()
        .flat_map(|t| {
            fs::read_dir(root.join("docs/results").join(t))
                .into_iter()
                .flatten()
        })
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().is_some_and(|x| x == "json"))
        .collect();
    paths.sort();
    for p in paths {
        let b: Bundle = match fs::read_to_string(&p)
            .map_err(|e| e.to_string())
            .and_then(|s| serde_json::from_str(&s).map_err(|e| e.to_string()))
        {
            Ok(b) => b,
            Err(e) => {
                c.refused.push((p, vec![format!("unreadable: {e}")]));
                continue;
            }
        };
        let mut why = b.record.contradictions();
        if b.code.dirty || b.code.commit.is_empty() {
            why.push("code not committed".into());
        }
        if b.record.detail["formulation"] != formulation(&b.case.model) {
            why.push(format!(
                "formulation {} is not current",
                b.record.detail["formulation"]
            ));
        }
        match replayed(root, &b) {
            Ok((u, files)) => {
                if files != b.inputs {
                    why.push("inputs changed".into());
                }
                let same = match (u, b.record.u) {
                    (Some(a), Some(z)) => (a - z).abs() <= tol(z),
                    (a, z) => a.is_none() && z.is_none(),
                };
                if !same {
                    why.push(format!(
                        "replay gives U = {u:?}, the record {:?}",
                        b.record.u
                    ));
                }
                if why.is_empty() {
                    c.admitted.push((p, b, u));
                    continue;
                }
            }
            Err(e) => why.push(e),
        }
        c.refused.push((p, why));
    }
    c
}

fn num(x: Option<f64>, d: usize) -> String {
    x.map_or("-".into(), |v| {
        let s = format!("{v:.d$}");
        let (int, frac) = s
            .split_once('.')
            .map_or((s.as_str(), None), |(a, b)| (a, Some(b)));
        let (sign, int) = int.strip_prefix('-').map_or(("", int), |i| ("-", i));
        let mut g = String::new();
        for (k, ch) in int.chars().enumerate() {
            if k > 0 && (int.len() - k) % 3 == 0 {
                g.push(',');
            }
            g.push(ch);
        }
        format!(
            "{sign}{g}{}",
            frac.map_or(String::new(), |f| format!(".{f}"))
        )
    })
}

fn pct(g: Option<f64>) -> String {
    g.map_or("-".into(), |g| format!("{:.3}%", 100.0 * g))
}

fn short(b: &Bundle) -> &str {
    &b.code.commit[..7.min(b.code.commit.len())]
}

/// Per benchmark instance: published value, best U, best L, gap and verdict.
fn evrp_rows(root: &Path, c: &Collected) -> Vec<String> {
    let mut out = vec![
        "| Instance | Report value | U (replayed) | L | Gap | Verdict | Revisions |".to_owned(),
        "|---|---:|---:|---:|---:|---|---|".to_owned(),
    ];
    for name in EVRP {
        let mine: Vec<_> = c
            .admitted
            .iter()
            .filter(|(_, b, _)| {
                b.case.track == "evrp"
                    && b.case.instance == name
                    && b.case.far.is_none()
                    && b.case.model != "R3"
            })
            .collect();
        let mut files = run::Files::new();
        let probe = crate::bundle::Case {
            track: "evrp".into(),
            instance: name.into(),
            model: "R2".into(),
            time: 0.0,
            far: None,
            until: None,
            scenario: None,
            battery: None,
            alpha: None,
            cover: false,
        };
        let Ok(p) = run::instance(root, &probe, &mut files) else {
            continue;
        };
        let seeds = fs::read_dir(root.join("data/seeds"))
            .into_iter()
            .flatten()
            .filter_map(|e| e.ok().map(|e| e.path()))
            .filter(|f| {
                f.file_name()
                    .and_then(|n| n.to_str())
                    .is_some_and(|n| n.starts_with(&format!("{name}-")))
            });
        let seeded = seeds
            .filter_map(|f| replay::read_routes(&f).ok())
            .map(|r| evrp::replay::replay(&p, &r, true))
            .filter(|r| r.ok)
            .map(|r| r.length);
        let u = mine
            .iter()
            .filter_map(|m| m.2)
            .chain(seeded)
            .reduce(f64::min);
        let l = mine.iter().filter_map(|m| m.1.record.l).reduce(f64::max);
        let report = p.published.unwrap_or(f64::NAN);
        let mut verdict = match gap(u, l) {
            Gap::Closed => "certified optimal".to_owned(),
            Gap::Crossed => "inconsistent bounds".to_owned(),
            Gap::Open if u.is_some() && l.is_some() => "bracketed".to_owned(),
            Gap::Open => "open".to_owned(),
        };
        if u.is_some_and(|u| report > u + 1e-6 * (1.0 + report)) {
            verdict += "; report value not optimal";
        } else if l.is_some_and(|l| report < l - 1e-6 * (1.0 + report)) {
            verdict += "; report value below a valid bound";
        }
        let mut revs: Vec<&str> = mine.iter().map(|m| short(&m.1)).collect();
        revs.sort();
        revs.dedup();
        let g = u.zip(l).map(|(u, l)| (u - l) / u.abs().max(1.0));
        out.push(format!(
            "| {name} | {report:.6} | {} | {} | {} | {verdict} | {} |",
            num(u, 6),
            num(l, 6),
            pct(g),
            revs.join(", ")
        ));
    }
    out
}

fn transit_rows(c: &Collected) -> Vec<String> {
    let mut out = vec![
        "| Case | Model | Fleet | U | L | Gap | Status | Seconds | Processor |".to_owned(),
        "|---|---|---:|---:|---:|---:|---|---:|---|".to_owned(),
    ];
    for (_, b, _) in c.admitted.iter().filter(|(_, b, _)| {
        b.case.track == "transit" && b.case.alpha.is_none() && b.case.battery.is_none()
    }) {
        let r = &b.record;
        let fleet = r.detail["fleet"]
            .as_u64()
            .or(r.detail["schedule"]["fleet"].as_u64());
        let d = if r.model == "M0" { 0 } else { 2 };
        out.push(format!(
            "| {} | {} | {} | {} | {} | {} | {} | {:.1} | {} |",
            r.instance,
            r.model,
            fleet.map_or("-".into(), |f| f.to_string()),
            num(r.u, d),
            num(r.l, d),
            pct(r.gap_rel),
            r.status,
            r.elapsed,
            b.host["cpu"]
        ));
    }
    out
}

/// R3 against R1 (route length) and M2 against M1 (cost) at each declared loss coefficient.
fn physics_rows(c: &Collected) -> Vec<String> {
    let mut out = vec![
        "| Pair | Instance | alpha | Without | With | Increase | OA gap | Status | Seconds |"
            .to_owned(),
        "|---|---|---:|---:|---:|---:|---:|---|---:|".to_owned(),
    ];
    let mut rows: Vec<&Bundle> = c
        .admitted
        .iter()
        .map(|(_, b, _)| b)
        .filter(|b| b.case.alpha.is_some())
        .collect();
    rows.sort_by(|a, z| {
        let k = |b: &Bundle| {
            (
                b.case.model.clone(),
                b.case.far,
                b.case.battery.map(f64::to_bits),
            )
        };
        k(a).cmp(&k(z))
            .then(a.case.alpha.partial_cmp(&z.case.alpha).unwrap())
    });
    for b in rows {
        let (base_model, measure) = if b.case.model == "R3" {
            ("R1", "length")
        } else {
            ("M1", "cost")
        };
        let base = c.admitted.iter().find(|(_, z, _)| {
            z.case.model == base_model
                && z.case.instance == b.case.instance
                && z.case.far == b.case.far
                && z.case.until == b.case.until
                && z.case.battery == b.case.battery
                && z.case.alpha.is_none()
        });
        let r = &b.record;
        let with = r
            .certified
            .then(|| {
                if measure == "length" {
                    r.detail["length"].as_f64()
                } else {
                    r.u
                }
            })
            .flatten();
        let without = base.and_then(|z| z.1.record.u);
        let name = if b.case.model == "R3" {
            r.instance.clone()
        } else {
            format!(
                "{} before {}h, {} kWh",
                b.case.instance,
                b.case.until.unwrap_or(24.0),
                b.case.battery.unwrap_or(f64::NAN)
            )
        };
        let base_status = base.map_or("missing".to_owned(), |z| z.1.record.status.clone());
        out.push(format!(
            "| {} / {base_model} | {name} | {} | {} ({base_status}) | {} | {} | {} | {} | {:.1} |",
            r.model,
            b.case.alpha.unwrap(),
            num(without, 3),
            num(with, 3),
            num(with.zip(without).map(|(a, z)| a - z), 3),
            pct(r.gap_rel),
            r.status,
            r.elapsed
        ));
    }
    out
}

/// docs/results/README.md and the lines of the README results block.
pub fn render(root: &Path) -> (String, Vec<String>) {
    let c = collect(root);
    let evrp = evrp_rows(root, &c);
    let mut revs: Vec<&str> = c.admitted.iter().map(|(_, b, _)| short(b)).collect();
    revs.sort();
    revs.dedup();
    let mut page = String::from(
        "# Results\n\nRegenerated by `efo report` from the bundles in this directory. A bundle is admitted only if its code was committed, its record is self-consistent under the result contract ([Algorithms](../ALGORITHMS.md) §8), its formulation is current, its inputs are unchanged, and the independent replay of its stored routes or schedule reproduces its U. A replayed route set certifies its own length whoever produced it, so U may also come from the seed routes in `data/seeds`; L counts only from an admitted bundle.\n\n",
    );
    page += "## CEC-2020 E instances\n\nL is the best admitted bound of R1 and R2; U the shortest replayed solution.\n\n";
    page += &(evrp.join("\n")
        + "\n\n## Route 100\n\nM0 is the battery-free fleet; M1 schedules and charges the declared 250 kWh fleet. Seconds compare only on one processor.\n\n");
    page += &(transit_rows(&c).join("\n")
        + "\n\n## Charging physics\n\nEach row fixes the loss coefficient alpha (illustrative). R3 and M2 are solved by outer approximation, R1 and M1 by HiGHS, on the same instance. R3 against R1 compares the replayed route length, since R3 also prices energy and dwell time; M2 against M1 compares cost. 'With' is filled only when outer approximation certified its value.\n\n");
    page += &physics_rows(&c).join("\n");
    page += "\n";
    if !c.refused.is_empty() {
        page += "\n## Bundles not admitted\n\n| Bundle | Reasons |\n|---|---|\n";
        for (p, why) in &c.refused {
            let _ = writeln!(
                page,
                "| {} | {} |",
                p.strip_prefix(root.join("docs/results"))
                    .unwrap_or(p)
                    .to_string_lossy()
                    .replace('\\', "/"),
                why.join("; ")
            );
        }
    }
    let mut block = vec![
        format!(
            "Regenerated by `efo report` from the admitted bundles in [docs/results](docs/results/README.md), produced by revision {}. Every U is a replayed solution; every L comes from an admitted bundle.",
            revs.join(", ")
        ),
        String::new(),
    ];
    block.extend(evrp);
    (page, block)
}

/// Write docs/results/README.md and the block between the README's results markers.
pub fn write(root: &Path) -> Result<String, String> {
    let (page, block) = render(root);
    fs::write(root.join("docs/results/README.md"), &page).map_err(|e| e.to_string())?;
    let readme = root.join("README.md");
    let s = fs::read_to_string(&readme).map_err(|e| e.to_string())?;
    let (i, j) = (
        s.find("<!-- results:begin -->")
            .ok_or("README has no results:begin")?,
        s.find("<!-- results:end -->")
            .ok_or("README has no results:end")?,
    );
    fs::write(
        &readme,
        format!(
            "{}<!-- results:begin -->\n{}\n{}",
            &s[..i],
            block.join("\n"),
            &s[j..]
        ),
    )
    .map_err(|e| e.to_string())?;
    Ok(page)
}
