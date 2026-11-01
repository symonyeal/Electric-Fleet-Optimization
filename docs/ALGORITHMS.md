# Algorithms and certificates

This page explains how the optimization methods produce operating recommendations with an explicit bound, rather than presenting
a feasible schedule as a certified optimum.

**1. Methods and their roles**

| Method | Where | Role |
| --- | --- | --- |
| HiGHS (`crates/efo/src/lp.rs`, through the `highs` crate) | R1, M1, OA masters, the R2 restricted master | MILP and LP solves; a bound is HiGHS's MIP dual bound; R2 duals are its simplex duals |
| ng-route labeling (`crates/efo-kernels/src/price.rs`) | R2 | Exact pricing for the bound (R2.4), [Routing](ROUTING.md) §3 |
| Primal-dual interior-point method (`crates/efo-kernels/src/ipm.rs`, `ldl.rs`) | M2, R3 | Kernel of the barrier subproblems, §2-§3 |
| Barrier wrapper (`crates/efo/src/barrier.rs`) | M2, R3 | Reduces a fixed-integer convex subproblem to the kernel, §4 |
| Outer approximation (`crates/efo/src/oa.rs`) | M2, R3 | Convex MINLP with a master dual bound, §5 |

A bound is admitted only from a trusted source (HiGHS's MIP dual bound, (R2.4) after exact pricing, the OA master's dual bound,
the M0 matching), and a solution only through the independent replay ([Validation](VALIDATION.md) §3); the contract is §6. The
barrier subproblems and the labeling are this project's own code, so their points are checked by the replay and their values
never enter a bound directly. The operational rows of a model are written once and shared by its MILP, its fixed-integer
subproblem and its OA master; the replay and the enumeration oracles are written separately from them. HiGHS is the production
MILP solver. The labeling and the factorization are native because they were the measured costs in the Python implementation
(revision 89e967d). No conic or convex solver was added: adopting one first requires citing its formulation and implementation
in [Sources](SOURCES.md) and measuring it here.

**2. Primal-dual method for the LP**

Use minimization standard form

$$
\min c^Tx\quad\text{s.t.}\quad Ax=b,\ x\ge0,
\qquad
\max b^Ty\quad\text{s.t.}\quad A^Ty+s=c,\ s\ge0.
$$

Let X=diag(x), S=diag(s), r_p=Ax-b, r_d=A^Ty+s-c, and mu=x^Ts/n. The central path satisfies

$$Ax=b,\quad A^Ty+s=c,\quad Xs=\mu\mathbf1,\quad x,s>0.$$

For centering parameter sigma in (0,1), fixed at 0.1, the Newton equations are

$$
\begin{bmatrix}
0&A^T&I\\ A&0&0\\ S&0&X
\end{bmatrix}
\begin{bmatrix}\Delta x\\\Delta y\\\Delta s\end{bmatrix}
=
\begin{bmatrix}-r_d\\-r_p\\\sigma\mu\mathbf1-Xs\end{bmatrix}. \tag{A1}
$$

Follow Vanderbei Chapters 17-20 for the central-path and KKT derivations, and BT Ch. 9 for the primal-dual path-following
algorithm in the same notation. His chapters change conventions; the equations here consistently use minimization. Beck Chapter
5 supplies the Newton and damping interpretation.

    Input:          A, b, c; residual tolerance eps; centering sigma;
                    fraction-to-boundary eta in (0,1); iteration limit
    Initialization: x > 0, s > 0, y arbitrary; scale rows and columns
    General step:   (a) compute primal, dual, and complementarity residuals
                    (b) stop if all residual tests pass
                    (c) solve (A1) for the Newton direction
                    (d) choose positive primal and dual step lengths
                    (e) backtrack on a scaled residual merit function if needed
                    (f) update x, y, s; stop on a numerical or resource limit

For x, the fraction-to-boundary bound is

$$\alpha_x=\min\left\{1,\eta\min_{j:\Delta x_j<0}
\frac{-x_j}{\Delta x_j}\right\},$$

with the inner minimum omitted if there is no negative direction; define alpha_s similarly.

With finite upper bounds, x + w = u, w >= 0 and multiplier v >= 0 join the system, with residual r_u = u - x - w. The stopping
rule requires normalized primal and dual residuals and complementarity:

$$
\frac{\|r_p\|_\infty}{1+\|b\|_\infty}\le\epsilon,
\quad
\max_j\frac{|r_{u,j}|}{1+u_j}\le\epsilon,
\quad
\|r_d\|_\infty\max\Big\{\frac{1}{1+\|c\|_\infty},\frac{\|x\|_1}{1+|c^Tx|}\Big\}\le\epsilon,
\quad
\frac{x^Tz+w^Tv}{1+|c^Tx|}\le\epsilon. \tag{A2}
$$

Each bound row is scaled by its own bound, and the gap by the primal objective alone. The second dual term bounds |x'r_d|, the
objective error a dual residual causes. Without these, one large finite bound makes the rule vacuous: with a box of width 1e8, a
first version scaled all residuals by the largest bound and reported `optimal` on infeasible LPs. The start is centered: x = u/2
on finite boxes, 1 otherwise, z = 1/x, v = 1/w. An empty box (l > u, including a row whose minimum over the box exceeds its
right-hand side) is returned as `infeasible` with the columns that prove it.

Also check nonnegativity in original units. Neither a small step nor a small barrier parameter alone proves optimality. Failure
of the iteration is `numerical` or `limit`, never `infeasible`: infeasibility needs a certificate (A^Ty >= 0 and b^Ty < 0 in
standard form, or an empty box). A ray without the conditions needed for its interpretation is not a certificate.

Fixed variables are eliminated and the original variable map restored after solution. At fixed integer schedules, many powers,
energies, and arcs are fixed to zero; putting a log barrier on a variable fixed at zero is invalid, so such faces are removed
before the kernel runs (§4).

*As implemented* (`crates/efo-kernels/src/ipm.rs`, `ldl.rs`). Each Newton system is factored by a sparse LDL' (faer) in an
approximate-minimum-degree order chosen once from the pattern. For an LP the normal matrix A(D + d_p I)^{-1}A' + d_d I is
positive definite, and its LDL' is backward stable in any order. The quasi-definite system loses accuracy as D spreads near the
optimum (Gill, Saunders and Shinnerl, 1996). The normal equations are therefore used unless their factor would hold more than
twice the entries of the quasi-definite one, which happens when A has dense columns; both counts come from the symbolic
analysis. A pivot lost to cancellation in the normal matrix is replaced by 1e128, which drops its component (Wright, 1999). A
quasi-definite pivot of the wrong sign, or below 1e-13, is replaced by ±1e-8. Every solve is refined against the regularized
matrix itself, at most three times. Refining against the unregularized system drifts along its null space when that system is
singular. A direction that is not finite ends the method as `numerical` at the last finite iterate. The order is chosen for fill
alone because an LDL' of a quasi-definite matrix exists for every symmetric permutation (Vanderbei, 1995).

**3. Convex rows**

The method of §2 extends to convex rows h(x) <= 0 (Vanderbei Ch. 25): slacks s = -h(x) with multipliers lam, s lam = mu.
Eliminating ds and dlam adds Hh + Jh'(lam/s)Jh to the (1,1) block of the quasi-definite system, where Hh is the Hessian of sum
lam_k h_k and Jh the Jacobian. Steps are common to primal and dual and backtrack on a residual merit. The rows supply analytic
derivatives of the Lagrangian, not merely of the objective: for M2 the loss rows contribute diagonal charging-power curvature,
and for R3 the 2 x 2 blocks of the perspective q^2/tau. A finite-difference check of every Jacobian and Hessian is part of the
suite ([Validation](VALIDATION.md) §2).

The barrier objective is c'x - mu sum_i log(s_i), with slacks s = -h(x) and multipliers lambda. Beck Chapters 10-12 provide the
KKT and duality interpretation. KKT sufficiency follows from convexity. Existence of multipliers and textbook convergence claims
additionally require appropriate qualifications; remove fixed faces before invoking Slater, and report degenerate cases rather
than silently assuming strict feasibility.

**4. Barrier subproblems**

Collect continuous variables v and bounded integer decisions y. M2 and R3 are

$$
\min c^Tz\quad\text{s.t.}\quad lo\le Az\le hi,\quad h(z)\le0,
\quad l\le z\le u,\quad y\in\mathbb Z^q, \tag{A3}
$$

with z=(v,y) and h convex in the full relaxed vector (a convex objective is brought to this form by an epigraph variable).
Bounds and affine rows remain explicit. At fixed y, `barrier.rs` eliminates the fixed columns and shifts the rest to 0 <= x' <=
u - l. A row left without free columns is checked as a constant and dropped. Each finite side of a ranged row gets a slack in
[0, side - min over the box of its row], finite whenever the box makes it so. The kernel then sees A x' = b with the convex rows
h restricted to the free columns.

Primal feasibility, dual signs, stationarity and complementarity are checked independently. The barrier point is a candidate,
not a certificate: the bound of a MINLP comes from the OA master. A fixed-integer value must never be reported as a fleet-wide
lower bound.

**5. Outer approximation**

Introduce an objective epigraph theta. At a point z^j=(v^j,y^j), add globally valid supporting planes

$$
\theta\ge F(z^j)+\nabla F(z^j)^T(z-z^j),\qquad
h_i(z^j)+\nabla h_i(z^j)^T(z-z^j)\le0. \tag{A4}
$$

Retain all original affine rows, finite bounds, and integrality. Initialize with nonnegative lower bounds for nonlinear costs
and loss tangents at zero and the power ceiling. Keep objective linear costs explicit to improve the master.

    Input:          convex model (A3); bound tolerances; MILP/NLP budgets
    Initialization: valid master cuts
    General step:   (a) solve the master MILP; read its dual bound L
                    (b) extract a candidate integer vector from a master incumbent
                    (c) fix those integers and solve the convex subproblem by the
                        barrier method (§4)
                    (d) validate a feasible solution, reconstruct cost, and update U
                    (e) add supporting planes at the master point and at the
                        subproblem point
                    (f) stop when U-L meets tolerance; otherwise repeat

Tangents of convex differentiable functions are valid even if the subproblem point is not optimal. A numerical failure may
therefore supply useful evaluated cuts, but never an infeasibility assertion or a no-good cut. No assignment is excluded: a
subproblem that fails adds only the cuts at the master point.

If the master repeats the same assignment and no violated cut is found while the certificate gap remains open, the run returns
`stall`. Finite numerical termination is not guaranteed merely by naming the method OA; the source algorithms' regularity and
exact-solve assumptions are distinct from a resource-limited implementation. One deadline covers the run, and each master gets
at most the time left.

At every iteration use a feasible objective for U and the master dual bound for L. A time-limited master may provide both, only
one, or neither. A local subproblem objective is an upper bound only after independent feasibility checks. The design follows
Duran and Grossmann (1986) and the convex-MINLP survey of Bonami, Kılınç and Linderoth, which are supplementary sources rather
than chapters of the supplied books ([Sources](SOURCES.md) §3).

Branch-and-price is not used for the transit models: a route pool restricted to generated duties gives feasible upper bounds,
but its LP value is not a lower bound on the unrestricted master unless pricing is complete and certified, and charging timing
makes duty pricing a substantial independent problem. R2 uses column generation deliberately ([Routing](ROUTING.md) §3).

**6. Result contract**

A result keeps apart what each party established (`crates/efo/src/cert.rs`):

| Field | Values | Established by |
| --- | --- | --- |
| `solver_status` | optimal, feasible_limit, no_incumbent, infeasible, unbounded, local, numerical, stall, limit | the method's own termination: HiGHS, the kernel, OA, R2's loop |
| `validation_status` | replayed, validation_failed, not_available | the independent replay of the returned solution, and the agreement of the model's objective with the replayed cost |
| `certificate_status` | certified, open, invalid_bound, not_applicable | the gap rule below |
| `status` | the solver values, invalid_bound, validation_failed | derived; `optimal` if and only if certified |

The solver's code and message are stored beside them. For a minimization problem with valid finite L and U,

$$\operatorname{gap}_{abs}=U-L,\qquad
\operatorname{gap}_{rel}=\frac{U-L}{\max(1,|U|)},\qquad
\tau=\epsilon_{abs}+\epsilon_{rel}\max(1,|U|),$$

with epsilon_abs = epsilon_rel = 1e-6. The certificate is two-sided: certified when -tau <= U - L <= tau and U is replayed;
`invalid_bound` when L > U + tau. A crossing within tau is floating-point noise, reported raw and never clamped; a larger one
carries the defect `negative gap` and is never certified, so `certified` and a defect never coexist. The same rule decides every
published verdict and stops OA and R2.

A solver's `optimal` becomes the public `optimal` only through the certificate. With a replay that fails, the status is
`validation_failed`; with no U, `no_incumbent`; with an objective that differs from the replayed cost by more than tau,
`validation_failed`, U kept and L in doubt. An unknown quantity is absent with a reason, never zero. Solver tolerances and
numerical residuals qualify all certificates: these are floating-point optimization certificates, not formally verified rational
proofs.

Every bound records model, graph, scenario, time grid, and provenance. A bundle stores the record with its case, code revision,
host and input digests ([Validation](VALIDATION.md) §3). A local stationary point must not populate a field named global
optimality gap unless a separate valid lower bound is also supplied.
