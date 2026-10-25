//! The two computations the Python code cannot do quickly: ng-route pricing for the R2 bound
//! (Routing §5) and the primal-dual interior-point method of Algorithms §2-§3 with a sparse LDL'
//! factorization. Everything else (formulations, HiGHS calls, replays, bundles) stays in Python.

#![forbid(unsafe_code)]

pub mod ipm;
pub mod ldl;
pub mod price;
