---
phase: 02-interior-point-core
verified: 2026-09-29T00:30:00Z
status: passed
score: 8/8 must-haves verified
covered_files:
  - .planning/REQUIREMENTS.md
  - .planning/phases/02-interior-point-core/02-01-PLAN.md
  - .planning/phases/02-interior-point-core/02-01-SUMMARY.md
  - .planning/phases/02-interior-point-core/02-02-PLAN.md
  - .planning/phases/02-interior-point-core/02-02-SUMMARY.md
  - .planning/phases/02-interior-point-core/02-03-PLAN.md
  - .planning/phases/02-interior-point-core/02-03-SUMMARY.md
  - methods/ipm.py
  - tests/test_ipm.py
covered_digest: "v1:sha256:5c3cca334d2e7c77b28399d869d3d79af9b3686047a589939fde53e9befaad54"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "Infeasible and unbounded constructions end with status numerical or limit, never optimal (ROADMAP SC3)"
    status: failed
    reason: >
      The primal test of the stopping rule divides the residual by 1 + max(|b1|, |U_B|), and the gap test
      divides by |dobj|, which contains U'v. One large finite upper bound anywhere in the problem therefore
      makes both tests nearly vacuous. Three infeasible two- or three-variable LPs end status optimal.
    artifacts:
      - path: methods/ipm.py
        issue: "err[0] normalised by max(|b1|, |U_B|) and err[2] by |dobj| containing U_B'v_B (lines computing err); (A2) in docs/ALGORITHMS.md §2 normalises by 1 + |b|"
    missing:
      - "Scale the primal test so an unrelated large bound cannot absorb a violated row: e.g. test rp against 1 + |b1| and ru against 1 + |U_B| separately, and use a gap measure not inflated by U'v"
      - "Regression tests: min x1+x2, -x1-x2 <= -3, x3 <= 1e8, 0 <= x <= (1,1,1e8) must not end optimal; min x1+x2, x1+x2 = -0.01, 0 <= x <= 1e9 must not end optimal"
  - truth: "Status optimal is returned only when the returned value is optimal to tolerance (IPM-01, stopping rule (A2))"
    status: failed
    reason: >
      Same root cause. On a feasible LP with a finite box, min -x1 + 2x2 s.t. x1 + x2 >= 2 - 1e-4, x3 <= 1e8,
      0 <= x <= (1, 1, 1e8), the method returns status optimal, f = 1.0, while highs-ds gives 0.9998
      (relative error 1e-4, tolerance 1e-6). The method's own bound L = -1006.9 at that point; f - L = 1008 is
      reported under status optimal. Eight such cases found in a 30-case sweep (bounds 1e6-1e8).
    artifacts:
      - path: methods/ipm.py
        issue: "stopping rule accepts an O(1) true duality gap when |U_B| is large"
    missing:
      - "Fix as above; add the near-infeasible family (t in 1e-3..1e-6, big in 1e6..1e8) as a highs-ds agreement test"
  - truth: "standard() gives a slack a finite upper bound only when the box makes it finite (key link, plan 02-01)"
    status: failed
    reason: >
      standard() substitutes 1e300 for u = inf and declares the slack bound infinite only if the row minimum is
      below -1e299. A negative coefficient of magnitude <= 0.1 on a variable with u = inf yields a finite slack
      bound of 1e297-1e299. The feasible LP min -x1 s.t. x1 + a x2 <= 5, x1 + x2 = 1, x >= 0 ends status
      numerical at k = 1 for a in {-0.1, -0.05, -1e-3} (optimal for a in {-1, -0.5, -0.2}); bound() also
      overflows (RuntimeWarning) on these slacks.
    artifacts:
      - path: methods/ipm.py
        issue: "standard(): lo = Ai.maximum(0) @ l + Ai.minimum(0) @ where(isinf(u), 1e300, u); smax = where(lo < -1e299, inf, bi - lo)"
    missing:
      - "Mark smax_i = inf exactly when some a_ij < 0 has u_j = inf (a boolean product of the sign pattern and isinf(u)), with no sentinel"
      - "Test with a small negative coefficient on an unbounded variable"
---

# Phase 2: Interior-point core. Verification report

**Phase goal:** A user can solve LPs and convex QPs with a readable primal-dual method whose every iterate carries a valid bound
**Verified:** 2026-09-29
**Status:** gaps_found
**Re-verification:** No (initial)

The bound half of the goal holds without exception in everything I ran. The solve half does not: the
stopping rule declares `optimal` on infeasible LPs, and on feasible LPs at a suboptimal point, whenever one
finite upper bound is large (1e6 or more). The shipped tests pass because every test instance has
`u <= 3`.

## Goal achievement

### Observable truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | SC1: optimal values agree with highs-ds on Vanderbei's worked examples and random feasible bounded LPs | VERIFIED | Tests: (2.1), 20 random LPs, 5 nonzero-l LPs. My runs: Vanderbei Ch. 2 exercise (31), Ch. 3 degenerate examples (1, 0), dependent equality rows (u finite and u = inf), duplicate rows, tiny boxes (width 1e-9, 1e-7, nonzero l), fixed variables, u = inf with negative l, and 160 random LPs with 30% of bounds at 1e4-1e10: all agree to 1e-6 relative. Only one Vanderbei optimum is in the test suite. |
| 2 | SC2: (A3) never exceeds the highs-ds optimum at any iterate | VERIFIED | 10 000 random (x, y) pairs on 2000 boxed equality LPs: max (L - z)/(1 + |z|) = 0.0. Every trace in every run above, including the failing ones, had max L <= z. Derivation below. |
| 3 | SC3: infeasible and unbounded constructions end numerical or limit, never optimal | FAILED | Vanderbei §1.1 pair ends `limit` (test and my run). Counterexamples ending `optimal`: (B) min x1+x2, -x1-x2 <= -3, x3 <= 1e8, 0 <= x <= (1,1,1e8): residual 1.0 on row 1; (C) min x1+x2, x1+x2 = -0.01, 0 <= x <= 1e9: residual 0.01; also u = 1e12 and an equality-plus-slack variant. |
| 4 | SC4: stopped at relative gap delta, returns interior duals and the gap reached | VERIFIED | 30 LPs x delta in {1e-1, 1e-2, 1e-4, 1e-6}: status feasible_limit or optimal, err[2] <= delta, err[0], err[1] <= 1e-8, x strictly inside the box, L <= z. Five QPs with delta = 1e-3: feasible_limit, L <= z. `err` carries the gap reached. |
| 5 | Fixed variables are removed before the barrier acts | VERIFIED | `J = flatnonzero(u - l > 0)`; barrier acts on J only; `xs()` restores l. Test plus my all-fixed and all-but-one cases. |
| 6 | Convex QPs agree with exact active-set enumeration | VERIFIED | Tests: 10 PD QPs. My runs: 400 QPs with PSD Q of rank 1..n (singular included), nonzero l, all optimal and equal to enumeration to 1e-6; 20 QPs with a dependent equality row and a fixed variable; 20 with u = inf. Max L along iterates - z: -7e-13 relative. |
| 7 | Derived (IPM-01, (A2)): status optimal only when the value is optimal to tolerance | FAILED | Feasible LP (A) above: f = 1.0 vs 0.9998, status optimal, L = -1006.9. 8/30 failures in the near-infeasible sweep for bounds 1e6-1e8. |
| 8 | Key link: standard() slack bounds finite only when the box makes them so | FAILED | Coefficient -0.1 or smaller in magnitude on a u = inf variable gives smax of 1e299, 5e298 or 1e297; the feasible 2-variable LP ends `numerical` at k = 1. |

**Score:** 6/8 truths verified (0 present, behaviour unverified)

### Newton system against the code

With `rp = b1 - A1 x`, `ru = U - x - w`, `rd = c1 - A1'y - z + v + Q1 x`, `rxz = mu - xz`, `rwv = mu - wv`,
the Newton equations are `A dx = rp`, `dx + dw = ru`, `A'dy + dz - dv - Q dx = rd`, `Z dx + X dz = rxz`,
`V dw + W dv = rwv`. Hence `dz = X^-1(rxz - Z dx)`, `dw = ru - dx`, `dv = W^-1(rwv - V dw)`, all as in the code.
Substituting into the dual row gives `-(Q + X^-1 Z + W^-1 V) dx + A'dy = rd - X^-1 rxz + W^-1(rwv - V ru)`,
which is the docstring's `rho` and the code's `rho`. The regularised matrix, with `-(Q + D + dp I)` and `+dd I`,
is quasi-definite. The residuals are evaluated on the unregularised equations. Common steps are used for QP
and separate steps for LP; this is correct, because `rd` depends on x only through Q. `ru` stays 0, so
iterates satisfy 0 < x < U and the traced bound is evaluated inside the box. No sign errors.

### Bound (A3)/(A5)

`L(x) = c'x + x'Qx/2 - y'(Ax - b)` is convex for PSD Q and any y, so `L(x') >= L(x) + a'(x' - x)` with
`a = c + Qx - A'y`; minimising the tangent over the box gives the code's sum. For `a_j >= 0` the code uses
`min(a_j(l_j - x_j), 0)`. This equals the exact term for x in the box, and for x outside the box it is no
larger than the exact term, so it remains valid. For `a_j < 0` with `u_j = inf` it returns -inf. For LP
(Q = 0) the tangent is exact, which gives (A3) for any y. The randomized checks in truths 2 and 6 agree.

### Required artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `methods/ipm.py` | ipm(), standard(), bound() | VERIFIED (with defects above) | 151 lines, substantive, used by tests/test_ipm.py |
| `tests/test_ipm.py` | Tests for every must-have | VERIFIED | 51 test cases; every instance has u <= 3, which is why truths 3, 7 and 8 went undetected |

### Key link verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| standard() | ipm() | slacks with box-implied upper bounds | PARTIAL | Sentinel 1e300 misclassifies small coefficients (truth 8) |
| bound() | ipm() trace and result | (A3) LP / (A5) QP | WIRED | Called per iterate with `xs(x), y` and at return |
| Q | (1,1) block of K | `-(Q1 + diag(D + dp))` | WIRED | Q1 = Q[J][:, J]; linear term c + Ql for the shift |

### Behavioural spot-checks

| Behaviour | Command | Result | Status |
| --- | --- | --- | --- |
| Full suite | `py -3.14 -m pytest -q` | 86 passed | PASS |
| Lint | `py -3.14 -m ruff check .` | All checks passed | PASS |
| Dependencies | `py -3.14 -m pip check` | No broken requirements | PASS |
| Infeasible, large bound | case (B) | status optimal, row residual 1.0 | FAIL |
| Feasible, large bound | case (A) | optimal, f = 1.0 vs 0.9998 | FAIL |
| Small negative coefficient, u = inf | `standard([-1,0],[[1,-0.05]],[5],[[1,1]],[1])` | numerical at k = 1 | FAIL |

### Probe execution

None declared. No `scripts/*/tests/probe-*.sh`.

### Requirements coverage

| Requirement | Plan | Status | Evidence |
| --- | --- | --- | --- |
| IPM-01 | 02-01 | BLOCKED (partial) | Method, fraction-to-boundary and outputs present. The stopping rule is not (A2) as documented: it normalises by the box and accepts violated rows (truths 3, 7). |
| IPM-02 | 02-01 | SATISFIED | Truth 1 |
| IPM-03 | 02-02 | SATISFIED | Truth 2 |
| IPM-04 | 02-03 | SATISFIED | Truth 6; residuals <= 1e-8 |
| IPM-05 | 02-02 | SATISFIED | Truth 4. The multipliers z and v are not returned; y and a = z - v are. |
| IPM-06 | 02-02 | SATISFIED | stats: m, n, n_free, nnz_K, nnz_LU, t_factor, t_solve, reg; `err` is computed on the unregularised equations |

No orphaned requirements. REQUIREMENTS.md already marks IPM-01 as Complete, which this report contradicts.

### Anti-patterns and warnings

| File | Issue | Severity |
| --- | --- | --- |
| methods/ipm.py | Stopping-rule scaling (truths 3, 7) | Blocker |
| methods/ipm.py `standard()` | 1e300 sentinel (truth 8) | Blocker |
| methods/ipm.py `ipm()` | `l > u` is treated as fixed at l: min x1+x2, x1+x2 <= 5, (2,0) <= x <= (1,3) returns optimal with x1 = 2 > u1. Malformed data should end as a named failure, not optimal. | Warning |
| methods/ipm.py `ipm()` | `l = -inf` is unguarded (the docstring requires finite l) | Info |
| methods/ipm.py `bound()` | Overflow warning when the slack bound is 1e298 | Info |
| tests/test_ipm.py | Only one Vanderbei optimum is tested, although SC1 says "worked examples" | Info |

No TBD/FIXME/XXX/TODO markers.

### Human verification required

None.

### Gaps summary

One root cause produces two of the three failures. The stopping rule measures primal infeasibility relative to
`max(|b1|, |U_B|)` and measures the gap relative to a dual objective that contains `U'v`. A single large finite
bound therefore licenses `optimal` at a point that violates a row (SC3 fails) or at a feasible but suboptimal
point (the value is wrong by 1e-4 relative). The fleet models will carry large physical bounds, and Phase 4 will
take `optimal` from this method at its nodes. The third failure is independent: `standard()` uses a 1e300
sentinel, so a small negative coefficient on an unbounded variable yields a finite slack bound of about
1e298, and a trivial feasible LP ends `numerical`. The bound itself was never violated. In every wrong-optimal
case the returned L was far below f, so `f - L` would have exposed the error.

---

_Verified: 2026-09-29_
_Verifier: Claude (gsd-verifier)_


## Gap Closure (2026-09-29)

Re-checked by the orchestrator; the verifier's findings above are kept as written.

| Finding | Fix | Evidence |
|---------|-----|----------|
| Infeasible LPs reported optimal when one bound is large | Each bound row scaled by its own bound in (A2); primal rows by 1 + max abs(b) | `test_large_bound_does_not_hide_infeasibility` (u = 1e4 ... 1e12) |
| Feasible LP stopped 2e-4 above its optimum | Gap scaled by 1 + abs(f); dual residual also scaled by norm1(x)/(1 + abs(f)); centered start | `test_near_infeasible_with_a_large_bound`: 18 cases, all equal to highs-ds; the verifier's s4.py sweep: 30 of 30 optimal and equal |
| standard() made the slack of a row with a u = inf column finite | Exact test for a negative coefficient on a u = inf column | `test_unbounded_column_keeps_its_slack_unbounded` |
| l > u treated as fixed; l = -inf unguarded | l > u (and a row impossible on the box) returns `infeasible` naming the columns; l = -inf raises | `test_empty_box_is_infeasible_and_infinite_lower_bound_is_an_error` |
| One Vanderbei optimum only | Vanderbei ex. 3.1 (p. 35) and ten further cases against highs-ds | `test_cases_agree_with_highs_ds` |

(A2) in docs/ALGORITHMS.md now states the rule the code implements. Full suite: 140 passed.

**Status after closure:** passed, 8/8.
