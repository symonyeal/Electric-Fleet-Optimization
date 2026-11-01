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
}

impl Case {
    /// <instance>[-far<k>][-<scenario>][-until<H>h][-B<kWh>][-alpha<a>]-<model>.
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

fn git(root: &Path, args: &[&str]) -> String {
    Command::new("git")
        .arg("-C")
        .arg(root)
        .args(args)
        .output()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_owned())
        .unwrap_or_default()
}

/// The commit of the tree at root and whether its code differs from it.
pub fn code(root: &Path) -> Code {
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
    );
    Code {
        commit: git(root, &["rev-parse", "HEAD"]),
        dirty: !changed.is_empty(),
    }
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
