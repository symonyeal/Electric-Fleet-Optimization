# Algorithms and certificates

**1. Where interior-point methods enter**

The computational study has two tracks sharing the same physical models.

| Track | Method | Role |
| --- | --- | --- |
| Textbook | Readable primal-dual LP/QP method | Expose central path, Newton equations, sparse factorization, and stopping rules |
| Integer experiment | Small branch-and-bound with LP IPM nodes | Demonstrate how continuous lower bounds support integer decisions |
| Practical MILP | SciPy `milp` / HiGHS | Reference bounds and schedules for R0, R1, M1, and OA masters |
| Column generation | Restricted master by the textbook IPM, stopped early; exact labeling pricing | R2 bound (R2.2), [Routing](ROUTING.md) §5 |
| Convex MINLP | MILP outer approximation plus barrier NLP/QP subproblems | Main M2 and R3 method |
| Nonconvex extension | Fixed-schedule `trust-constr`, multiple starts | M3 feasible incumbents and local diagnostics |

The design does not assume that selecting an IPM for an LP selects it for all
HiGHS MIP nodes. SciPy's MILP interface is not an IPM branch-and-bound interface.
The educational tree explicitly controls its LP node solver. Benchmark it against
HiGHS; do not promise a speed improvement. [SciPy MILP](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html),
[SciPy LP IPM](https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs-ipm.html).

**2. LP primal-dual method**

Use minimization standard form

$$
\min c^Tx\quad\text{s.t.}\quad Ax=b,\ x\ge0,
\qquad
\max b^Ty\quad\text{s.t.}\quad A^Ty+s=c,\ s\ge0.
$$

Let X=diag(x), S=diag(s), r_p=Ax-b, r_d=A^Ty+s-c,
and mu=x^Ts/n. The central path satisfies

$$Ax=b,\quad A^Ty+s=c,\quad Xs=\mu\mathbf1,\quad x,s>0.$$

For centering parameter sigma in (0,1), the Newton equations are

$$
\begin{bmatrix}
0&A^T&I\\ A&0&0\\ S&0&X
\end{bmatrix}
\begin{bmatrix}\Delta x\\\Delta y\\\Delta s\end{bmatrix}
=
\begin{bmatrix}-r_d\\-r_p\\\sigma\mu\mathbf1-Xs\end{bmatrix}. \tag{A1}
$$

Follow Vanderbei Chapters 17-20 for the central-path and KKT derivations, and
BT Ch. 9 for the primal-dual path-following algorithm in the same notation. His
chapters change conventions; the equations here consistently use minimization.
Beck Chapter 5 supplies the Newton and damping interpretation.

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

with the inner minimum omitted if there is no negative direction; define
alpha_s similarly. An experimental predictor-corrector variant can reuse the
factorization, but must be documented separately from the basic path-following
algorithm and validated before entering the branch-and-bound experiment.

With finite upper bounds, x + w = u, w >= 0 and multiplier v >= 0 join the
system, with residual r_u = u - x - w. The stopping rule requires normalized
primal and dual residuals and complementarity:

$$
\frac{\|r_p\|_\infty}{1+\|b\|_\infty}\le\epsilon,
\quad
\max_j\frac{|r_{u,j}|}{1+u_j}\le\epsilon,
\quad
\|r_d\|_\infty\max\Big\{\frac{1}{1+\|c\|_\infty},\frac{\|x\|_1}{1+|c^Tx|}\Big\}\le\epsilon,
\quad
\frac{x^Tz+w^Tv}{1+|c^Tx|}\le\epsilon. \tag{A2}
$$

Each bound row is scaled by its own bound, and the gap by the primal objective
alone. The second dual term bounds |x'r_d|, the objective error a dual residual
causes. Without these, one large finite bound makes the rule vacuous. With a box
of width 1e8, a first version scaled all residuals by the largest bound. It
reported `optimal` on infeasible LPs, and on a feasible LP at a point 2e-4 above
the optimum; the Phase 2 verification found both. The start is centered:
x = u/2 on finite boxes, 1 otherwise, z = 1/x, v = 1/w. An empty box (l > u,
including a row whose minimum over the box exceeds its right-hand side) is
returned as `infeasible` with the columns that prove it.

Also check nonnegativity in original units. Neither a small step nor a small
barrier parameter alone proves optimality. Slightly infeasible iterates require
the explicit lower-bound construction below before pruning a tree node.

Eliminate fixed variables, identify dependent equality rows, and restore the
original variable map after solution. At fixed integer schedules, many powers,
energies, and arcs are fixed to zero. Such faces need relative-interior treatment;
putting a log barrier on a variable fixed at zero is invalid.

For convex QP objective c^Tx+(1/2)x^TQx, Q positive semidefinite, replace the top
left block of (A1) by -Q and use r_d=A^Ty+s-Qx-c. This follows Vanderbei
Chapter 24. Supply Q directly; no numerical Hessian approximation is needed.

For dense A of size m by n, forming the LP normal matrix costs O(m^2 n) and
factoring it costs O(m^3). Sparse cost depends on elimination fill and cannot be
claimed from nonzero counts alone. Record matrix dimensions, factor nonzeros,
factorization time, and solve time. Compare reduced KKT and normal-equation
routes only on cases where both have validated residuals. Never form A inverse
or H inverse explicitly. Regularization must be reported and residuals checked
against the unregularized original equations.

**3. Infeasibility, unboundedness, and bounded dual estimates**

Failure of the textbook iteration is `numerical` or `limit`, not `infeasible`.
A reference solve can classify a node while the pedagogical solver is incomplete.
Vanderbei Chapter 22 motivates an optional homogeneous self-dual implementation;
it is deferred until the basic IPM is verified.

For standard form, a primal infeasibility certificate has A^Ty >= 0 and b^Ty<0.
An unboundedness certificate requires both a feasible primal base point and a
direction d >= 0 with Ad=0 and c^Td<0. Check the original problem after undoing
presolve/scaling. A ray without the conditions needed for its interpretation is
not a certificate.

The physical fleet models have explicit finite bounds l <= x <= u. For an
equality-constrained LP, any y defines a lower bound

$$
L(y)=b^Ty+\sum_j\min\{r_jl_j,r_ju_j\},\qquad r=c-A^Ty. \tag{A3}
$$

This is the exact box minimum of the Lagrangian. It remains valid when
stationarity is approximate. Incorporate inequalities with multipliers of the
correct sign, or transform them with explicitly bounded slacks. Do not set a
tiny reduced cost to zero without bounding its effect. If some bounds are
infinite, (A3) may be minus infinity; that is an unusable lower bound, not zero.

For MIP solves, the reported master lower bound is the solver's dual bound,
not the incumbent objective. Solver tolerances and numerical residuals qualify
all certificates: these are floating-point optimization certificates, not
formally verified rational proofs.

**4. Educational branch-and-bound**

Run on tiny M1 instances only. Solve the root LP with the textbook IPM or
`highs-ipm`; evaluate (A3). Branch on a fractional integer variable, using
x_j <= floor(x_j*) and x_j >= ceil(x_j*). Use a deterministic most-fractional
rule first, with lexicographic tie breaking. A feasible M1 schedule initializes
the incumbent U; otherwise U is infinite.

    Input:          bounded MILP; LP method; eps_abs, eps_rel; node/time limits
    Initialization: root node; U from a independently checked feasible schedule
    General step:   (a) select an open node and solve its LP relaxation
                    (b) retain a valid lower bound for that node
                    (c) prune only for certified infeasibility or bound >= U-tol
                    (d) if the discrete point is integral, fix integers and
                        re-solve continuous variables; validate before updating U
                    (e) otherwise create the two branches
                    (f) stop at a global bound gap or resource limit

The global lower bound is the minimum valid bound over all open nodes, capped
by U once a feasible incumbent exists. Numerical failure leaves a node open
with its inherited bound. If no usable bound exists, report no gap. An integral
LP point must still satisfy every original physical row after fixing integers.
Rounding an LP route is not an incumbent construction.

The tree demonstrates Vanderbei Chapter 23 and BT §11.2. It is not intended to reproduce
commercial presolve, cutting planes, or advanced branching.

**5. Convex nonlinear subproblems**

Collect continuous variables v and bounded integer decisions y. Write M2 as

$$
\min F(v,y),\quad Av+By=b,\quad g_i(v,y)\le0,
\quad l\le(v,y)\le u,\quad y\in\mathbb Z^q. \tag{A4}
$$

F and every g_i are convex in the full relaxed variable vector. Bounds and
affine constraints remain explicit. At fixed y, solve the reduced continuous
problem with `trust-constr`, analytic Jacobians, and the analytic Lagrangian
Hessian. For M1-Q the Hessian is constant. For M2 the nonlinear constraints
contribute diagonal charging-power curvature.

The generic barrier equations use positive slacks w and multipliers lambda:

$$
\nabla_v F+A^T\nu+J_g^T\lambda=0,\quad
Av+By=b,\quad g(v,y)+w=0,\quad W\lambda=\mu\mathbf1.
$$

The barrier objective is F-mu sum_i log(w_i). Supply derivatives of the
Lagrangian, not merely the objective, in the nonlinear Newton system. Beck
Chapters 10-12 provide the KKT and duality interpretation; Vanderbei Chapter 25
provides the barrier/Newton construction. SciPy supplies the production
globalization mechanics, rather than requiring a second general NLP solver to
be written for this project.

Check primal feasibility, dual signs, stationarity, and complementarity
independently. KKT sufficiency follows from convexity. Existence of multipliers
and textbook convergence claims additionally require appropriate qualifications;
remove fixed faces before invoking Slater. Report degenerate cases rather than
silently assuming strict feasibility.

For approximate multipliers lambda >= 0 and arbitrary nu, define the convex
Lagrangian L(v)=F(v,y)+nu^T(Av+By-b)+lambda^T g(v,y). At any vhat and on its
finite box, a computable lower bound is

$$
\underline L=L(\hat v)+\sum_j\min\{a_j(l_j-\hat v_j),
a_j(u_j-\hat v_j)\},\qquad a=\nabla L(\hat v). \tag{A5}
$$

Convexity makes the tangent a global minorant, and weak duality gives the bound.
This bounds the fixed-integer NLP. To bound the full MINLP using this construction,
the tangent and box minimization must include the relaxed integer variables as
well. A fixed-schedule dual must never be reported as a fleet-wide lower bound.

**6. Outer approximation for M2**

Introduce an objective epigraph theta. At a point z^j=(v^j,y^j), add globally
valid supporting planes

$$
\theta\ge F(z^j)+\nabla F(z^j)^T(z-z^j),\qquad
g_i(z^j)+\nabla g_i(z^j)^T(z-z^j)\le0. \tag{A6}
$$

Retain all original affine rows, finite bounds, and integrality. Initialize with
nonnegative lower bounds for nonlinear costs and loss tangents at zero and the
power ceiling. Keep objective linear costs explicit to improve the master.

    Input:          convex model (A4); bound tolerances; MILP/NLP budgets
    Initialization: valid master cuts; U from M2-P upper approximation if feasible
    General step:   (a) solve the master MILP; read its dual bound L
                    (b) extract a candidate integer vector from a master incumbent
                    (c) fix those integers and solve the convex NLP by a barrier method
                    (d) validate a feasible solution, reconstruct cost, and update U
                    (e) add supporting planes for nonlinear constraints and objective
                    (f) stop when U-L meets tolerance; otherwise repeat

Tangents of convex differentiable functions are valid even if the NLP point
is not optimal. A numerical failure may therefore supply useful evaluated cuts,
but never an infeasibility assertion or an unjustified no-good cut.

For a suspected infeasible integer choice, solve the convex restoration problem
minimize sum_i xi_i, subject to g_i <= xi_i, xi_i >= 0, while retaining affine
rows and finite bounds. Linear infeasibility can be certified separately. A
strictly positive *certified lower bound* for the restoration objective proves
infeasibility of that integer assignment. A merely positive incumbent does not.
Use restoration tangents; if an assignment-exclusion cut is added, encode its
bounded integer variables correctly and record the proof. No-good cuts must not
discard feasible assignments just because a local solve stalled.

If the master repeats the same assignment and no violated cut is found while
the certificate gap remains open, tighten or repair the NLP/certificate or
return `stall`. Finite numerical termination is not guaranteed merely by naming
the method OA. The source algorithms' regularity and exact-solve assumptions must
be distinguished from a resource-limited implementation.

At every iteration use a feasible objective for U and the master dual bound for
L. A time-limited master may provide both, only one, or neither. A local NLP
objective is an upper bound only after independent feasibility checks.
The OA design follows Durán-Grossmann and the convex-MINLP survey, which are
supplementary sources rather than chapters of the supplied books.
[Original paper](https://link.springer.com/article/10.1007/BF02592064),
[survey](https://optimization-online.org/2009/10/2429/).

**7. Decomposition and acceleration boundary**

This section concerns the transit models. The routing bound R2 uses column
generation deliberately; [Routing](ROUTING.md) §5 states why its pricing problem
differs.

Do not begin with branch-and-price. A route pool restricted to generated duties
can produce feasible upper bounds, but its LP value is not a lower bound on the
unrestricted route master unless pricing is complete and certified. Battery and
charging timing also make duty pricing a substantial independent problem.

First exploit smaller fixed-schedule charging problems and the sparse time
structure. Cache graph and linear rows; warm-start continuous variables after
fixing integers; release a small neighborhood of bus paths only as a clearly
labeled incumbent heuristic. Add Benders or Lagrangian decomposition only after
a measured bottleneck and an explicit valid cut/bound derivation. The reference
Electricity-Market-Model's decomposition style motivates certificates, not a
requirement to reproduce every algorithm in that repository.

**8. Result contract**

Each result distinguishes `optimal`, `feasible_limit`, `infeasible`, `unbounded`,
`local`, `numerical`, `stall`, and `no_incumbent`. Store the original solver code
and message as well as the project classification.

For a minimization problem with valid finite L and U, report

$$\operatorname{gap}_{abs}=U-L,\qquad
\operatorname{gap}_{rel}=\frac{U-L}{\max(1,|U|)}.$$

Require U-L <= eps_abs+eps_rel max(1,|U|) for the claimed certificate. A materially
negative gap is a defect to investigate, not a value to clamp silently. Every
bound records model, graph, scenario set, time grid, and provenance. M3 local
stationarity must not populate a field named global optimality gap unless a
separate valid lower bound is also supplied.
