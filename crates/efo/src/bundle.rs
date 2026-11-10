//! Result bundles: a record with what is needed to reproduce and admit it (Validation §3).
//!
//! ```text
//! record .... the result contract's record (cert.rs)
//! case ...... track, instance, model and options of the run
//! code ...... commit and whether the code differed from it (prose and results excluded)
//! host ...... processor and thread count: elapsed times compare only on one host
//! inputs .... SHA-256 of every input file, by repository path
//! command ... the command line
//! ```
//!
//! A bundle from a tree whose code differs from its commit is never admitted, so the CLI refuses
//! to write one into docs/results.

use crate::cert::Record;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::Path;
use std::process::Command;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Case {
    pub track: String,
    pub instance: String,
    pub model: String,
    pub time: f64,
    /// Routing: the instance restricted to its k customers farthest from the depot.
    pub far: Option<usize>,
    /// Transit: trips departing before this hour; the scenario suffix; the battery (kWh).
    pub until: Option<f64>,
    pub scenario: Option<String>,
    pub battery: Option<f64>,
    /// The loss coefficient, replacing the scenario's.
    pub alpha: Option<f64>,
    /// M1: start HiGHS from the cover start (fleet::cover); absent in earlier bundles.
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    pub cover: bool,
}

impl Case {
    /// <instance>[-far<k>][-<scenario>][-until<H>h][-B<kWh>][-alpha<a>][-cover]-<model>.
    pub fn stem(&self) -> String {
        let mut s = self.instance.clone();
        if let Some(k) = self.far {
            s += &format!("-far{k}");
        }
        if let Some(x) = &self.scenario {
            s += &format!("-{x}");
        }
        if let Some(h) = self.until {
            s += &format!("-until{h}h");
        }
        if let Some(b) = self.battery {
            s += &format!("-B{b}");
        }
        if let Some(a) = self.alpha {
            s += &format!("-alpha{a:e}");
        }
        if self.cover {
            s += "-cover";
        }
        s + "-" + &self.model
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Code {
    pub commit: String,
    pub dirty: bool,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Bundle {
    pub record: Record,
    pub case: Case,
    pub code: Code,
    pub host: BTreeMap<String, String>,
    pub inputs: BTreeMap<String, String>,
    pub command: Vec<String>,
}

/// Publish a complete bundle once; an existing result path is never replaced.
pub fn write_new(path: &Path, bundle: &Bundle) -> Result<(), String> {
    let mut bytes = serde_json::to_vec_pretty(bundle).map_err(|e| e.to_string())?;
    bytes.push(b'\n');
    let name = path
        .file_name()
        .ok_or_else(|| format!("{}: no file name", path.display()))?;
    let dir = path.parent().unwrap_or_else(|| Path::new("."));
    let mut staged = None;
    let mut file = None;
    for n in 0..128 {
        let temp = dir.join(format!(
            ".{}.{}.{}.tmp",
            name.to_string_lossy(),
            std::process::id(),
            n
        ));
        match OpenOptions::new().write(true).create_new(true).open(&temp) {
            Ok(f) => {
                staged = Some(temp);
                file = Some(f);
                break;
            }
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(e) => return Err(format!("{}: {e}", temp.display())),
        }
    }
    let temp =
        staged.ok_or_else(|| format!("{}: could not reserve a staging path", path.display()))?;
    let result = match file {
        Some(mut file) => file
            .write_all(&bytes)
            .and_then(|_| file.sync_all())
            .map_err(|e| format!("{}: {e}", temp.display()))
            .and_then(|_| {
                drop(file);
                fs::hard_link(&temp, path).map_err(|e| format!("{}: {e}", path.display()))
            }),
        None => Err(format!("{}: staging file was not opened", temp.display())),
    };
    let _ = fs::remove_file(&temp);
    result
}

fn git(root: &Path, args: &[&str]) -> Result<String, String> {
    let o = Command::new("git")
        .arg("-C")
        .arg(root)
        .args(args)
        .output()
        .map_err(|e| format!("git {}: {e}", args[0]))?;
    if !o.status.success() {
        return Err(format!(
            "git {} failed: {}",
            args[0],
            String::from_utf8_lossy(&o.stderr).trim()
        ));
    }
    Ok(String::from_utf8_lossy(&o.stdout).trim().to_owned())
}

/// The commit of the tree at root and whether its code differs from it; an error when git
/// cannot say, so that no run starts that could not be admitted.
pub fn code(root: &Path) -> Result<Code, String> {
    let changed = git(
        root,
        &[
            "status",
            "--porcelain",
            "--",
            ".",
            ":!docs/results",
            ":!*.md",
        ],
    )?;
    Ok(Code {
        commit: git(root, &["rev-parse", "HEAD"])?,
        dirty: !changed.is_empty(),
    })
}

pub fn host() -> BTreeMap<String, String> {
    let cpu = if cfg!(windows) {
        let key = r"HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0";
        let out = Command::new("reg")
            .args(["query", key, "/v", "ProcessorNameString"])
            .output()
            .ok();
        out.and_then(|o| {
            String::from_utf8_lossy(&o.stdout)
                .split("REG_SZ")
                .nth(1)
                .map(|s| s.trim().to_owned())
        })
    } else {
        let info = std::fs::read_to_string("/proc/cpuinfo").unwrap_or_default();
        info.lines()
            .find(|l| l.starts_with("model name"))
            .and_then(|l| l.split_once(':'))
            .map(|(_, v)| v.trim().to_owned())
    };
    let threads = std::thread::available_parallelism().map_or(0, |n| n.get());
    BTreeMap::from([
        (
            "cpu".to_owned(),
            cpu.unwrap_or_else(|| "not recorded".into()),
        ),
        ("threads".to_owned(), threads.to_string()),
        ("os".to_owned(), std::env::consts::OS.to_owned()),
    ])
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cert::Record;

    #[test]
    fn code_is_an_error_where_git_cannot_answer() {
        let missing = std::env::temp_dir().join("efo-no-such-directory");
        assert!(code(&missing).is_err());
    }

    #[test]
    fn result_bundle_is_published_once_without_replacing_existing_bytes() {
        let dir = std::env::var_os("EFO_TEST_ROOT").map_or_else(
            || {
                std::env::current_exe()
                    .unwrap()
                    .parent()
                    .unwrap()
                    .to_owned()
            },
            std::path::PathBuf::from,
        );
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let path = dir.join(format!("efo-bundle-write-once-{stamp}.json"));
        let bundle = Bundle {
            record: Record {
                model: "R1".into(),
                instance: "test".into(),
                status: "open".into(),
                solver_status: "optimal".into(),
                validation_status: "not_available".into(),
                certificate_status: "open".into(),
                u: None,
                l: None,
                gap_rel: None,
                certified: false,
                defect: None,
                bound_source: None,
                objective: None,
                message: String::new(),
                elapsed: 0.0,
                detail: serde_json::json!({}),
            },
            case: Case {
                track: "evrp".into(),
                instance: "test".into(),
                model: "R1".into(),
                time: 1.0,
                far: None,
                until: None,
                scenario: None,
                battery: None,
                alpha: None,
                cover: false,
            },
            code: Code {
                commit: "test".into(),
                dirty: false,
            },
            host: BTreeMap::new(),
            inputs: BTreeMap::new(),
            command: vec![],
        };

        write_new(&path, &bundle).unwrap();
        let original = fs::read(&path).unwrap();
        assert!(write_new(&path, &bundle).is_err());
        assert_eq!(fs::read(&path).unwrap(), original);
        fs::remove_file(path).unwrap();

        let path = dir.join(format!("efo-bundle-race-{stamp}.json"));
        let gate = std::sync::Barrier::new(2);
        let wins = std::thread::scope(|s| {
            let a = s.spawn(|| {
                gate.wait();
                write_new(&path, &bundle)
            });
            let b = s.spawn(|| {
                gate.wait();
                write_new(&path, &bundle)
            });
            usize::from(a.join().unwrap().is_ok()) + usize::from(b.join().unwrap().is_ok())
        });
        assert_eq!(wins, 1);
        let stored: Bundle = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(stored.case, bundle.case);
        fs::remove_file(path).unwrap();
    }
}
