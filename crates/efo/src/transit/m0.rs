//! M0: the battery-free fleet on the trip compatibility DAG (Models §2).
//!
//! With x_ij = 1 when trip j immediately follows trip i on a bus, the chosen arcs form a
//! matching of the bipartite graph (out-copies, in-copies); time forbids cycles, so a matching is
//! a path cover and the least fleet is n minus the largest matching (Dilworth; Fulkerson 1956).
//! The largest matching is found by augmenting paths (Kuhn 1955), O(n m).

use super::{Corridor, compile, replay::replay};
use crate::cert::{Outcome, Record, record};
use crate::scenario::Transit;
use serde_json::json;
use std::collections::{BTreeMap, HashSet};
use std::time::Instant;

pub const FORMULATION: &str = "M0/2";

/// Largest matching of left i to right j along adj[i]: mate[j] = Some(i).
fn matching(n: usize, adj: &[Vec<usize>]) -> Vec<Option<usize>> {
    fn augment(
        i: usize,
        adj: &[Vec<usize>],
        mate: &mut [Option<usize>],
        seen: &mut [bool],
    ) -> bool {
        for &j in &adj[i] {
            if !seen[j] {
                seen[j] = true;
                if mate[j].is_none_or(|k| augment(k, adj, mate, seen)) {
                    mate[j] = Some(i);
                    return true;
                }
            }
        }
        false
    }
    let mut mate = vec![None; n];
    for i in 0..n {
        augment(i, adj, &mut mate, &mut vec![false; n]);
    }
    mate
}

/// M0: U is the number of duties after the independent replay accepts them as a time-connected
/// cover; L = n minus the largest matching, the least fleet. The agency's blocks are compared
/// with the deadhead model: block_violations counts consecutive block trips it does not allow.
pub fn m0(c: &Corridor, v: &Transit, name: &str) -> Record {
    let t0 = Instant::now();
    let m = compile(c, v);
    let n = c.trips.len();
    let mut adj = vec![Vec::new(); n];
    for &(i, j, _) in &m.arcs {
        adj[i].push(j);
    }
    let mate = matching(n, &adj);
    let mut succ = vec![None; n];
    for (j, i) in mate.iter().enumerate() {
        if let Some(i) = *i {
            succ[i] = Some(j);
        }
    }
    let mut heads: Vec<usize> = (0..n).filter(|&j| mate[j].is_none()).collect();
    heads.sort_by(|a, b| c.trips[*a].dep.total_cmp(&c.trips[*b].dep));
    let duties: Vec<Vec<String>> = heads
        .iter()
        .map(|&s| {
            std::iter::successors(Some(s), |&k| succ[k])
                .map(|k| c.trips[k].id.clone())
                .collect()
        })
        .collect();
    let rp = replay(c, &duties, v);
    let ok: HashSet<(usize, usize)> = m.arcs.iter().map(|&(i, j, _)| (i, j)).collect();
    let mut blocks: BTreeMap<&str, Vec<usize>> = BTreeMap::new();
    let mut order: Vec<usize> = (0..n).collect();
    order.sort_by(|a, b| c.trips[*a].dep.total_cmp(&c.trips[*b].dep));
    for k in order {
        if let Some(b) = &c.trips[k].block {
            blocks.entry(b).or_default().push(k);
        }
    }
    let violations = blocks
        .values()
        .flat_map(|b| b.windows(2))
        .filter(|e| !ok.contains(&(e[0], e[1])))
        .count();
    let lower = n - mate.iter().filter(|j| j.is_some()).count();
    record(
        "M0",
        name,
        Outcome {
            solver_status: "optimal",
            u: rp.ok.then_some(duties.len() as f64),
            l: Some(lower as f64),
            replayed: Some(rp.ok),
            objective: None,
            bound_source: "matching",
            message: "largest matching by augmenting paths".into(),
            elapsed: t0.elapsed().as_secs_f64(),
            detail: json!({"formulation": FORMULATION, "trips": n, "pairs": m.arcs.len(), "fleet": duties.len(),
            "blocks": blocks.len(), "block_violations": violations, "deadhead_km": rp.deadhead_km,
            "replay": {"ok": rp.ok, "defects": rp.defects}, "duties": duties}),
        },
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::transit::fixtures::route100;

    #[test]
    fn route100_needs_16_buses() {
        // Revision 89e967d: matching LP, min-cost flow and Hopcroft-Karp all gave 16; 21041
        // pairs; 23 blocks, none violating the deadhead model.
        let (c, v) = route100();
        let r = m0(&c, &v, "route100");
        assert!(r.certified && r.u == Some(16.0));
        assert_eq!(
            (
                r.detail["pairs"].as_u64(),
                r.detail["blocks"].as_u64(),
                r.detail["block_violations"].as_u64()
            ),
            (Some(21041), Some(23), Some(0))
        );
    }
}
