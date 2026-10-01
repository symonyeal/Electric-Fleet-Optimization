# Result-integrity repair

This change repairs the result contract at audited revision `098642b` and replaces the
old report path with one that admits only reproducible, compatible evidence.

## Root causes repaired

| Area | Root cause | Repair |
| --- | --- | --- |
| Certificate | A one-sided gap test let a lower bound above the replayed upper bound certify `optimal`. | The result contract now separates solver, validation, certificate and public statuses; an out-of-tolerance crossed bound is `invalid_bound`. |
| Branch-and-bound | A node with a small but material fractional value could be rounded, rejected and pruned as integral. | Integral-looking nodes are fixed and independently checked; hidden fractions branch, and rejected nodes remain open at their valid bound. |
| Transit M1 | Base load appeared only in charging-slot rows, while terminal restoration could become a negative depot cost. | Base load is attached once to the open site's meter in capacity and demand rows. Depot restoration is nonnegative external recovery to the initial energy target. |
| Scenarios and time limits | Scenario domains, model/track pairs and nested R2 budgets were not all checked at their boundary. | Scenario and CLI validation now fail before model construction, and one deadline reaches every R2 subproblem. |
| Published bundles | The old report accepted files by presence, including dirty, stale and self-contradictory records. | Schema 2 records code, inputs, scenario, formulation, command, toolchain and artifact digests. Report generation replays every upper bound and admits a lower bound only after the schema check or an explicit retained legacy decision. |

## Changed components

- `checks/certificate.py`, `methods/branch.py`, `methods/oa.py` and `models/colgen.py` implement the common result-state contract and its two-sided stopping rule.
- `models/fleet.py`, `checks/schedule.py`, `checks/enum_transit.py`, `models/charge.py`, `models/taper.py` and `models/scenario.py` align transit pricing, replay and extensions.
- `models/milp.py` and `models/transit.py` centralize neutral matrix plumbing and compiled transit inputs without coupling `checks/` to `models/`.
- `bench/`, `run_case.py` and `run_bench.py` define, validate, collect and render immutable result bundles. A failed child run leaves reports unchanged.
- `docs/results/MIGRATION.json` gives one decision for every legacy artifact. The regenerated [Results](results/README.md) page shows only admitted evidence and lists exclusions.

## Verification

On 2026-10-01, from this checkout:

| Command | Outcome |
| --- | --- |
| `python -m pytest -q tests/test_regressions.py --basetemp <project work folder>` | 38 passed in 5.90 s |
| `python -m pytest -q --basetemp <project work folder>` | 365 passed in 492.63 s; 17 SciPy optimizer warnings in nonlinear checks, no failures |
| `python -m ruff check .` | All checks passed |
| `python -m pip check` | No broken requirements |
| `python run_bench.py` | Re-rendered result pages and figures from admitted bundles; no model case was launched |

The regression suite covers the crossed-bound, hidden-fraction, base-load, depot-restoration,
scenario, bundle, child-process, CLI and deadline counterexamples. It was written against the
audited code and recorded as failing there in [Validation](VALIDATION.md).

## Remaining work

No headline result was recomputed. The 15 unfinished routing cases, four full-day sourced Route
100 cases, the E-n30-k3 interior-point limit, the empty 250 kWh comparison and the stalled R3
grid remain disclosed open work. The four Route 100 runs require a clean checkout and must use
the documented stress-pack, normalized-demand and external-depot interpretations.
