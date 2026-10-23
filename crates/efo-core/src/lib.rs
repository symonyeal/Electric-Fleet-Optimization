//! Shared core of the engine: instance and scenario data, the result contract, digests, and the
//! JSON and floating-point conventions that keep results comparable with the Python reference.

pub mod cert;
pub mod corridor;
pub mod digest;
pub mod evrp;
pub mod json;
pub mod num;
pub mod rows;
pub mod scenario;

pub use json::J;

/// The repository root: the nearest ancestor of the working directory holding `data/evrp.sha256`.
pub fn root() -> std::path::PathBuf {
    let mut d = std::env::current_dir().expect("working directory");
    loop {
        if d.join("data").join("evrp.sha256").exists() {
            return d;
        }
        if !d.pop() {
            return std::env::current_dir().unwrap();
        }
    }
}
