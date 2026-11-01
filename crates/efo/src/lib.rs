//! Electric fleet optimization: EVRP formulations (evrp), bus scheduling and charging (transit),
//! their independent replays, and the result contract every bound passes through (cert).

#![forbid(unsafe_code)]

pub mod barrier;
pub mod bundle;
pub mod cert;
pub mod evrp;
pub mod lp;
pub mod oa;
pub mod report;
pub mod run;
pub mod scenario;
pub mod transit;
