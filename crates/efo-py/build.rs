//! SOURCE: FNV-1a (64 bit) over the kernel sources, so that methods/native.py can refuse an
//! installed module built from other sources. Files: Cargo.toml, Cargo.lock and every crate's
//! Cargo.toml, build.rs and src/*.rs, sorted by path, each as "path\0bytes\0" with CRLF read as LF.

use std::path::{Path, PathBuf};

fn files(root: &Path) -> Vec<PathBuf> {
    let mut f = vec![root.join("Cargo.toml"), root.join("Cargo.lock")];
    let mut crates: Vec<PathBuf> = std::fs::read_dir(root.join("crates"))
        .unwrap()
        .map(|e| e.unwrap().path())
        .collect();
    crates.sort();
    for c in crates {
        f.push(c.join("Cargo.toml"));
        if c.join("build.rs").exists() {
            f.push(c.join("build.rs"));
        }
        let mut src: Vec<PathBuf> = std::fs::read_dir(c.join("src"))
            .unwrap()
            .map(|e| e.unwrap().path())
            .filter(|p| p.extension().is_some_and(|x| x == "rs"))
            .collect();
        src.sort();
        f.extend(src);
    }
    f
}

fn main() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let root = root.canonicalize().unwrap();
    let mut h: u64 = 0xcbf29ce484222325;
    let mut eat = |b: &[u8]| {
        for &x in b {
            h ^= x as u64;
            h = h.wrapping_mul(0x100000001b3);
        }
    };
    for p in files(&root) {
        println!("cargo:rerun-if-changed={}", p.display());
        let rel = p
            .strip_prefix(&root)
            .unwrap()
            .to_string_lossy()
            .replace('\\', "/");
        let bytes = std::fs::read(&p).unwrap_or_default();
        let text = String::from_utf8_lossy(&bytes).replace("\r\n", "\n");
        eat(rel.as_bytes());
        eat(&[0]);
        eat(text.as_bytes());
        eat(&[0]);
    }
    println!("cargo:rustc-env=EFO_SOURCE={h:016x}");
}
