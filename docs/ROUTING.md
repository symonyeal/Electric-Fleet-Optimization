# Routing

All costs are minimized. The routing track uses the electric capacitated
vehicle-routing benchmark of the IEEE WCCI-2020 competition (Mavrovouniotis et
al., CEC 2020), in the copy distributed by
[evrp-python](https://github.com/NeiH4207/evrp-python) at commit `16d3499`.
It gives the project published values to be held against. The competition
report lists them as upper bounds that "could be optimal in some cases but
[are] not verified yet" ([TR](SOURCES.md), §3). The transit models in
[Models](MODELS.md) have no external values of this kind.

**1. Problem**

Let 0 be the depot, I the customers with n=|I|, and F the charging stations.
Customer i has demand b_i>0. Every electric vehicle (EV) has load capacity C and
battery capacity Q. Traversing (i,j) consumes e_ij=h d_ij, where d_ij is the
unrounded Euclidean distance. The report (§2) requires:

- every customer is visited exactly once, by one route;
- every route starts and ends at the depot, fully loaded and fully charged;
- the demand served by a route is at most C, and the battery never falls below 0;
- an EV leaves every station, and the depot, fully charged; charging takes no
  time and costs nothing;
- stations and the depot may be visited any number of times by any EV.

The objective is total distance. The number of routes is free: the file field
VEHICLES is "the minimum number of EVs (or routes) a solution can have" (§3).
For E-n22-k4 it equals the capacity bound ceil(sum_i b_i/C)=ceil(22500/6000)=4.

Two conventions in circulation need a statement.

1. evrp-python rejects a solution with more than VEHICLES tours
   (`Problem.check_valid_solution`), but a tour may return to the depot and
   continue: its `Solution` docstring says so, and its checker resets load and
   battery at the depot. A tour is therefore a vehicle, not a route. With no time
   dimension, any set of routes can be chained onto one vehicle, so the cap
   restricts nothing: its rule and the report's define the same feasible routes.
   Every solution reports its route count; a vehicle count is not a model quantity.
2. The 2019 files give OPTIMAL_VALUE to six decimals (384.678035 for E-n22-k4),
   consistent with unrounded distances. The 2022 files give integers (383 for
   E-n29-k4-s7). Their distance convention is unknown until a published solution
   is replayed; until then they are not comparison targets.

**2. The report's formulation, and the depot**

The report states a MILP (its (1)-(10)) with binary arcs on V={0} ∪ I ∪ F',
where F' holds beta_f=2n copies of each station, and with load u and battery y
on arrival, initialized to u_0=C and y_0=Q (its footnote 3). Its load row (5)
also applies to arcs entering the depot. For the last customer i of a route it
reads u_0 <= u_i-b_i, which contradicts u_0=C, u_i <= C, and b_i>0. Battery rows
(7) and (8) fail the same way. Read literally, the program has no feasible route.

The transcription R1-TR therefore splits the depot into a source 0 with u=C,
y=Q and a sink 0' with free u and y >= 0. With that change it is the report's
model. It has 2n|F| station nodes (336 for E-n22-k4) and O(|V|^2) arcs, so it
serves only as an independent formulation on sub-instances with few customers.

**3. R0: remove the battery**

Deleting the station visits from an EVRP solution leaves a solution of the
capacitated VRP (CVRP) on {0} ∪ I. Euclidean distance satisfies the triangle
inequality, so the deletion does not lengthen any route. Hence

$$z(\mathrm{R0})\le z(\mathrm{R1}),$$

where R0 is the free-fleet CVRP with the same distances. Every lower bound for R0
is a lower bound for R1. The difference z(R1)-z(R0) is the distance the battery
costs on that instance: the routing counterpart of the M1-M0 comparison in
[Models](MODELS.md). R0 is R1 with the battery rows (R1.4)-(R1.6) deleted and
only direct arcs.

**4. R1: station-path multigraph MILP**

A route is a sequence of customers joined by segments. A segment from i to j is a
station path p=(i,f_1,...,f_k,j), with k >= 0 and f_t in F. Record its length
l_p, the energy a_p=e_{i f_1} needed on leaving i, and the energy
omega_p=e_{f_k j} spent after the last charge. For k=0, a_p=omega_p=e_ij.
The path is admissible if a_p <= Q, omega_p <= Q, and every station-to-station
leg consumes at most Q.

For k >= 1 the EV reaches j with Q-omega_p, whatever its charge at i, provided
that charge is at least a_p. Among such paths, p dominates p' when
l_p <= l_p', a_p <= a_p' and omega_p <= omega_p'. Replacing a segment by a
dominating path keeps every battery row satisfied and does not lengthen the
route. For fixed first and last stations f and g, the best interior is a shortest
path from f to g in the station graph whose edges consume at most Q. Hence

$$
P_{ij}=\{(i,j)\}\ \cup\ \operatorname{Pareto}\{(i,f,\mathrm{SP}(f,g),g,j):f,g\in F\},
$$

where the direct arc is omitted when e_ij > Q, and Pareto keeps the elements
minimal in (l, a, omega). Floyd-Warshall on the station graph costs O(|F|^3).
There are at most (n+1)^2|F|^2 candidates before filtering, about 31,000 for
E-n22-k4. The filtered count has not been measured.

Let x_p be binary for p in P = union of the P_ij, with sources in {0} ∪ I and
sinks in I ∪ {0'}. Let u_i in [b_i, C] be the load delivered on the route up to
and including i, and y_i in [0, Q] the battery on arrival at customer i.
Let delta^+(i) and delta^-(i) be the paths leaving and entering i, and D the
direct arcs between customers.

$$\min\ \sum_{p\in P}l_px_p \tag{R1.1}$$

$$\sum_{p\in\delta^+(i)}x_p=\sum_{p\in\delta^-(i)}x_p=1,\qquad i\in I \tag{R1.2}$$

$$u_j\ge u_i+b_j-C\Big(1-\sum_{p\in P_{ij}}x_p\Big),\qquad i,j\in I,\ i\ne j \tag{R1.3}$$

$$y_i\ge\sum_{p\in\delta^+(i)}a_px_p,\qquad i\in I \tag{R1.4}$$

$$y_j\le Q-\sum_{p\in\delta^-(j)\setminus D}\omega_px_p,\qquad j\in I \tag{R1.5}$$

$$y_j\le y_i-e_{ij}x_{ij}+Q(1-x_{ij}),\qquad (i,j)\in D \tag{R1.6}$$

By (R1.2) exactly one path leaves and one enters each customer. Hence (R1.4)
states exactly that the charge on leaving i covers the first leg of the path
used, and (R1.5) states exactly the arrival charge after a station or the depot.
Neither needs a big-M. Only the load row (R1.3) and the direct battery row
(R1.6) do. Since every b_j>0, (R1.3) forbids cycles among customers by the
Miller-Tucker-Zemlin argument: u strictly increases around a cycle.

The number of routes, sum_{p in delta^+(0)} x_p, is free in R1. The capacity
bound sum_{p in delta^+(0)} x_p >= ceil(sum_i b_i/C) is valid and is added.
There is no path from 0 to 0', so no route is empty. A mid-route return to the
depot needs no path of its own: it resets load and battery, so it is the end of
one route and the start of the next, at the same length.

*Claim.* R1 and R1-TR have the same optimal value.

*Justification.* Given a feasible route of R1-TR, cut it at customers into
station paths and replace each by a dominating element of P_ij, which exists
because shortest interiors and Pareto filtering discard only dominated paths.
The rows (R1.2)-(R1.6) hold and no length increases. Conversely, expand each
chosen path of R1 into its stations. A shortest path with positive lengths visits
each station at most once, and a solution has at most n+(number of routes) <= 2n
segments. Hence each station is used at most 2n times, which the report's
beta_f=2n copies accommodate. [Validation](VALIDATION.md) tests the claim on
sub-instances by solving both formulations and a brute-force enumeration.

**5. R2: set-partitioning bound by column generation with interior duals**

Let Omega be the set of feasible routes, c_r the length of route r, and a_ir the
number of visits of r to customer i. The master LP is

$$
\min\ \sum_{r}c_r\lambda_r\quad\text{s.t.}\quad\sum_ra_{ir}\lambda_r=1\ (i\in I),\quad\lambda\ge0. \tag{R2.1}
$$

Its value is at most z(R1). Pricing over a relaxed route set Omega' containing
Omega keeps the bound valid and makes pricing cheaper. The first relaxation is
the ng-route set with neighborhoods of size 8 (Baldacci, Mingozzi and Roberti,
2011): a route may revisit a customer only after leaving that customer's
neighborhood memory.

For duals pi of any restricted master, let c̄_r=c_r-sum_i a_ir pi_i and let
c̄* be the exact minimum of c̄_r over Omega'. Every route visits at least one
customer, so every feasible lambda satisfies sum_r lambda_r <= n, and adding this
redundant row leaves (R2.1) unchanged. Lagrangian relaxation of the covering rows
then gives, for every pi,

$$
z_{LP}(\Omega')\ \ge\ \sum_{i\in I}\pi_i+n\min\{0,\bar c^*\}. \tag{R2.2}
$$

The bound needs an exact pricing minimum, not an exact master. It is the
route-space analogue of (A3) in [Algorithms](ALGORITHMS.md). Heuristic pricing
may add columns but cannot evaluate (R2.2). The final pricing call must be
exact, or no bound is reported.

    Input:          instance; route relaxation Omega'; master tolerances delta_k;
                    pricing and time limits
    Initialization: Omega_0 = routes of a replayed feasible solution plus
                    one out-and-back route per customer, using station paths
    General step:   (a) solve the restricted master over Omega_k by the
                        primal-dual method of Algorithms §2, stopped at
                        relative gap delta_k; read pi
                    (b) price exactly; evaluate the bound (R2.2) and keep the best
                    (c) add columns with c̄_r < 0
                    (d) decrease delta_k as the master value approaches the bound
                    (e) stop when master value - bound <= eps, or at a limit

Step (a) is where the interior-point method matters. Stopped early, it returns
duals near the central path rather than at an extreme point of the dual set.
Gondzio, González-Brevis and Munari (2013) report fewer outer iterations with
such duals, and Munari and Gondzio (2013) use them inside branch-price-and-cut
for the VRP with time windows. This project measures that effect against simplex
duals from HiGHS; it does not assume it. Whether SciPy's `highs-ipm` exposes
duals before crossover is a Phase 1 check. If it does not, only the project's own
primal-dual method supplies the interior variant. The rule for delta_k is taken
from the source when implemented.

Pricing is a shortest path with resource constraints on the multigraph of §4.
A label at node i holds (c̄, q, y, M): reduced cost, load, charge on departure,
and ng-memory. Extending along p in P_ij requires y >= a_p and q+b_j <= C. The
new charge is Q-omega_p for k >= 1 and y-e_ij for k=0, and the reduced cost
grows by l_p-pi_j. Label L1 dominates L2 at the same node when c̄1 <= c̄2,
q1 <= q2, y1 >= y2 and M1 ⊆ M2. The worst case is exponential; the cost is
measured per instance. Pricing is the first candidate for a Rust/PyO3 kernel,
and only after profiling ([Design](DESIGN.md) §8).

The phase delivers bounds, not branch-and-price. Upper bounds come from R1
incumbents, from the restricted master solved as a MILP over the generated
elementary columns, and from replayed evrp-python solutions. When a replayed
upper bound meets (R2.2) within tolerance, that solution is certified optimal up
to floating-point tolerances. [Algorithms](ALGORITHMS.md) §7 advises against
starting the transit model with branch-and-price. That advice stands: transit
duty pricing with charging timing is a hard independent problem, whereas R2 prices
the standard resource-constrained path with a battery reset at stations.

**6. R3: partial recharging with resistive loss (convex MINLP)**

In the report, charging is instantaneous, free and full, so energy has no price
and full charging is optimal. R3 asks what changes when charging takes time and
loses energy. Its parameters are declared scenario inputs in
[Data](DATA.md). The benchmark carries no time or price data, and its units are
abstract.

R3 allows at most one station between consecutive customers. This restricts the
feasible set, so the R3 optimum is an upper bound on the unrestricted model.
Phase 9 reports whether any R1 optimum uses a segment with k >= 2.

Arcs are direct arcs (i,j) and station arcs s=(i,f,j). In addition to R1's
variables, let q_s >= 0 be the energy charged, tau_s >= 0 the dwell time, g_s the
grid energy purchased, and t_i the arrival time at customer i. Let v be the
speed, sigma_i the service time, T the route duration limit, P the charger power,
eta in (0,1] the efficiency, and alpha >= 0 the loss coefficient. For s=(i,f,j):

$$
y_i-e_{if}\ge0,\qquad y_i-e_{if}+q_s\le Q,\qquad
y_j\le y_i+q_s-(e_{if}+e_{fj})x_s+Q(1-x_s), \tag{R3.1}
$$

$$
0\le q_s\le Qx_s,\qquad q_s\le P\tau_s,\qquad 0\le\tau_s\le Tx_s, \tag{R3.2}
$$

$$
g_s\ \ge\ q_s/\eta+\alpha\,q_s^2/\tau_s, \tag{R3.3}
$$

with the closed perspective: (q_s, tau_s)=(0,0) requires only g_s >= 0. The first
row of (R3.1) is imposed only when x_s=1, through (R1.4) with a_s=e_if. The
second needs no big-M, since q_s=0 when x_s=0; the third is inactive then
because y_i >= 0 and y_j <= Q. At
constant power p=q/tau, resistive loss is proportional to p^2 tau=q^2/tau. Thus
alpha has units 1/kW, as in M2, and M2's slot loss alpha p^2 Delta is (R3.3)
with tau=Delta. Time rows follow (R1.3):
t_j >= t_i+sigma_i+(d_if+d_fj)/v+tau_s-M_s(1-x_s) for station arcs, with
M_s=T+sigma_i+(d_if+d_fj)/v, the least constant that deactivates the row when
x_s=0. Direct arcs take the same row without tau, and each route returns within T.

The objective is c_d sum_p l_p x_p+c_e sum_s g_s+c_tau sum_s tau_s. Depot energy
is outside the objective, as in the report. With c_e>0 the model therefore
prefers depot energy, which is the intended behavior for a fleet that charges
overnight.

*Convexity.* Rows other than (R3.3) are affine. The function q^2/tau is the
perspective of q^2, hence convex on tau>0, and its closure is convex on tau >= 0
(Boyd and Vandenberghe, §3.2.6). The continuous relaxation is therefore convex
and R3 is a convex MINLP. Row (R3.3) is a rotated second-order cone:
(tau_s/2, (g_s-q_s/eta)/alpha, q_s) satisfies 2ab >= c^2. A conic solver
therefore gives an independent check at fixed routes.

*Cuts.* The function q^2/tau is positively homogeneous of degree 1, so its
tangent planes pass through the origin. At a point with power r=q/tau,

$$q^2/\tau\ \ge\ 2rq-r^2\tau, \tag{R3.4}$$

valid for all tau >= 0. Outer approximation ([Algorithms](ALGORITHMS.md) §6)
uses (R3.4) at the powers of each subproblem solution. With breakpoints
0=r_0<...<r_J=P, the perspective of the secant of p^2 gives, for
q/tau in [r_j, r_{j+1}],

$$q^2/\tau\ \le\ (r_j+r_{j+1})q-r_jr_{j+1}\tau. \tag{R3.5}$$

The tangent family gives the lower MILP and the secant family, as a maximum of
affine functions, the upper MILP. This pair, R3-P, brackets R3 exactly as M2-P
brackets M2 ([Models](MODELS.md) §5). At fixed routes the continuous problem is
solved by a barrier method with analytic derivatives and bounded by (A5).

**7. R4 (deferred): nonlinear charging functions**

Montoya et al. (2017) model charging time as a concave piecewise-linear function
fitted to measured charging curves for three charger types, with public instances
on VRP-REP (2016-0020). The fixed-route problem is then nonconvex, as in M3.
R4 is deferred to v2 and is stated here only so that it is not mistaken for R3.

**8. What each model certifies**

| Model | Class | Lower bound | Claim |
| --- | --- | --- | --- |
| R0 | MILP (CVRP) | HiGHS dual bound | Lower bound on R1 |
| R1 | MILP | HiGHS dual bound; replayed incumbent | Optimal value of the report's EVRP, free fleet, within tolerance |
| R1-TR | MILP | As R1 | Formulation check on sub-instances only |
| R2 | LP by column generation | (R2.2) with exact pricing | Lower bound on R1 at every iteration |
| R3 | Convex MINLP (MISOCP) | OA master dual bound | Global optimum under k <= 1 and declared parameters |
| R3-P | MILP pair | Lower MILP dual bound | Bracket on R3 |

**9. The evrp-python baseline**

evrp-python supplies an independent heuristic upper bound: a greedy search and a
greedy genetic algorithm (GSGA). The README reports that the C++ version ranked in
the top three of the competition. Reading its source at `16d3499` shows
differences that make its outputs inputs to replay, not results:

1. It counts vehicles that may make several trips, not routes (§1).
2. `check_valid_solution` rejects repeated customers but does not check that every
   customer is visited.
3. The checker walks tours as stored, while `calculate_tour_length` adds the
   depot legs. Whether depot legs are energy-checked depends on the stored
   representation; this is tested, not assumed.
4. `calculate_tour_length` returns twice the length of an invalid solution, so a
   fitness value is not a length until validated.
5. Its README table reports, for X-n573-k30 under VNS, a minimum of 52181.51
   above a maximum of 51929.24. Published summaries are therefore re-measured by
   replay, never copied.
6. Its `requirements.txt` pins numpy 1.24.3, matplotlib 3.7.1 and pandas 2.2.2.
   These cannot install into the single Python 3.14 environment, and a second
   environment is excluded. It is run from a checkout outside this repository,
   against the installed packages. If it does not run, comparisons use its
   published values, labeled as unreplayed.

Solutions are exchanged in one format: one line per route, as 1-based node
identifiers of the instance file, with the depot at both ends. The independent
validator reads only this format and the instance file.
