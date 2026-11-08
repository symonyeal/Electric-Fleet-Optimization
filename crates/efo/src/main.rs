//! Command line: one case, one result bundle; the replay of a route file; the report.

use efo::bundle::{self, Bundle, Case};
use efo::{evrp, report, run};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

const USAGE: &str = "usage:
  efo evrp <instance> R1|R2|R3 [--time S] [--far K] [--alpha A] [--out DIR]
  efo transit <corridor> M0|M1|M2 [--time S] [--until H] [--scenario NAME] [--battery KWH] [--alpha A] [--out DIR]
  efo replay <instance> <routes file>
  efo report

Run from the repository root. A case writes docs/results/<track>/<stem>.json unless --out is given.";

fn value<T: std::str::FromStr>(flag: &str, v: Option<&String>) -> Result<T, String> {
    v.ok_or(format!("{flag} needs a value"))?
        .parse()
        .map_err(|_| format!("{flag}: not a valid value"))
}

fn case(args: &[String]) -> Result<(Case, Option<PathBuf>), String> {
    let [track, instance, model, rest @ ..] = args else {
        return Err(USAGE.into());
    };
    let mut c = Case {
        track: track.clone(),
        instance: instance.clone(),
        model: model.clone(),
        time: 600.0,
        far: None,
        until: None,
        scenario: None,
        battery: None,
        alpha: None,
    };
    let mut out = None;
    let mut it = rest.iter();
    while let Some(flag) = it.next() {
        let v = it.next();
        match (flag.as_str(), track.as_str()) {
            ("--time", _) => c.time = value(flag, v)?,
            ("--alpha", _) => c.alpha = Some(value(flag, v)?),
            ("--out", _) => out = Some(PathBuf::from(value::<String>(flag, v)?)),
            ("--far", "evrp") => c.far = Some(value(flag, v)?),
            ("--until", "transit") => c.until = Some(value(flag, v)?),
            ("--scenario", "transit") => c.scenario = Some(value(flag, v)?),
            ("--battery", "transit") => c.battery = Some(value(flag, v)?),
            _ => return Err(format!("{flag} does not apply to track {track}\n\n{USAGE}")),
        }
    }
    if !(c.time > 0.0 && c.time.is_finite()) {
        return Err("--time must be positive".into());
    }
    if c.alpha.is_some() && !matches!(c.model.as_str(), "R3" | "M2") {
        return Err("--alpha applies to R3 and M2".into());
    }
    Ok((c, out))
}

fn main_() -> Result<(), String> {
    let args: Vec<String> = std::env::args().collect();
    let root = Path::new(".");
    if !root.join("data/evrp.sha256").exists() {
        return Err("run from the repository root (data/evrp.sha256 not found)".into());
    }
    match args.get(1).map(String::as_str) {
        Some("report") => {
            print!("{}", report::write(root)?);
            Ok(())
        }
        Some("replay") => {
            let [_, _, inst, routes] = &args[..] else {
                return Err(USAGE.into());
            };
            let c = Case {
                track: "evrp".into(),
                instance: inst.clone(),
                model: "R1".into(),
                time: 0.0,
                far: None,
                until: None,
                scenario: None,
                battery: None,
                alpha: None,
            };
            let p = run::instance(root, &c, &mut run::Files::new())?;
            let r = evrp::replay::replay(&p, &evrp::replay::read_routes(Path::new(routes))?, true);
            println!(
                "{}",
                serde_json::to_string_pretty(&r).map_err(|e| e.to_string())?
            );
            Ok(())
        }
        Some("evrp" | "transit") => {
            let (c, out) = case(&args[1..])?;
            let code = bundle::code(root);
            let dir = out.unwrap_or_else(|| root.join("docs/results").join(&c.track));
            std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
            if code.dirty && out_is_results(&dir) {
                return Err("refusing to write a result from uncommitted code into docs/results: commit first, or pass --out".into());
            }
            let f = dir.join(format!("{}.json", c.stem()));
            if f.try_exists().map_err(|e| e.to_string())? {
                return Err(format!(
                    "{} already exists; use a fresh --out DIR",
                    f.display()
                ));
            }
            let (record, inputs) = run::run(root, &c)?;
            println!(
                "{} {}: status={} U={:?} L={:?} gap={:?} {:.1} s",
                record.instance,
                record.model,
                record.status,
                record.u,
                record.l,
                record.gap_rel,
                record.elapsed
            );
            let b = Bundle {
                record,
                case: c.clone(),
                code,
                host: bundle::host(),
                inputs,
                command: args[1..].to_vec(),
            };
            bundle::write_new(&f, &b)?;
            Ok(())
        }
        _ => Err(USAGE.into()),
    }
}

fn out_is_results(dir: &Path) -> bool {
    let (a, b) = (
        dir.canonicalize().ok(),
        Path::new("docs/results").canonicalize().ok(),
    );
    matches!((a, b), (Some(a), Some(b)) if a.starts_with(&b))
}

fn main() -> ExitCode {
    match main_() {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("{e}");
            ExitCode::FAILURE
        }
    }
}
