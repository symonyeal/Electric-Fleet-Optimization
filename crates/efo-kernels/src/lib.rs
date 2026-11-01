//! Numerical kernels without domain knowledge: ng-route pricing for the R2 bound (Routing §3) and
//! the primal-dual interior-point method of Algorithms §2-§3 with a sparse LDL' factorization.

#![forbid(unsafe_code)]

pub mod ipm;
pub mod ldl;
pub mod price;
