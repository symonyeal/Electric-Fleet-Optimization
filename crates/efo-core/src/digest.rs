//! SHA-256 identities of inputs, sources and results.
//!
//! Legend
//!   digest(x) .. SHA-256 of x as canonical JSON (sorted keys, no whitespace): the identity of a
//!                corridor, a scenario or a route set, independent of file formatting
//!   text(f) .... SHA-256 of a file with CRLF read as LF, so a Windows checkout hashes the same

use crate::json::{J, canon};
use sha2::{Digest, Sha256};
use std::path::Path;

pub fn sha256_hex(b: &[u8]) -> String {
    let h = Sha256::digest(b);
    h.iter().map(|x| format!("{x:02x}")).collect()
}

pub fn digest(x: &J) -> String {
    sha256_hex(canon(x).as_bytes())
}

/// `bench.schema.sha256`: raw bytes with every CRLF replaced by LF.
pub fn text(path: &Path) -> std::io::Result<String> {
    let b = std::fs::read(path)?;
    let mut out = Vec::with_capacity(b.len());
    let mut k = 0;
    while k < b.len() {
        if b[k] == b'\r' && b.get(k + 1) == Some(&b'\n') {
            k += 1;
            continue;
        }
        out.push(b[k]);
        k += 1;
    }
    Ok(sha256_hex(&out))
}
