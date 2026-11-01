# Routing

This track benchmarks electric-vehicle routing under range and charging constraints, then distinguishes a published route value
from a value that has been replayed and bounded.

All costs are minimized. The track uses the electric capacitated vehicle-routing benchmark of the IEEE WCCI-2020 competition
(Mavrovouniotis et al., CEC 2020), in the copy distributed by [evrp-python](https://github.com/NeiH4207/evrp-python) at commit
`16d3499` ([Data](DATA.md) §1). The competition report lists its values as upper bounds that "could be optimal in some cases but
[are] not verified yet" ([TR](SOURCES.md), §3). The transit models in [Models](MODELS.md) have no external values of this kind.

**1. Problem**

Let 0 be the depot, I the customers with n=|I|, and F the charging stations. Customer i has demand b_i>0. Every electric vehicle
(EV) has load capacity C and battery capacity Q. Traversing (i,j) consumes e_ij=h d_ij, where d_ij is the unrounded Euclidean
distance. The report (§2) requires:

- every customer is visited exactly once, by one route;
- every route starts and ends at the depot, fully loaded and fully charged;
- the demand served by a route is at most C, and the battery never falls below 0;
- an EV leaves every station, and the depot, fully charged; charging takes no time and costs nothing;
- stations and the depot may be visited any number of times by any EV.

The objective is total distance. The number of routes is free: the file field VEHICLES is "the minimum number of EVs (or routes)
a solution can have" (§3). For E-n22-k4 it equals the capacity bound ceil(sum_i b_i/C)=ceil(22500/6000)=4.

Two conventions in circulation need a statement.

1. evrp-python rejects a solution with more than VEHICLES tours (`Problem.check_valid_solution`), but a tour may return to the
   depot and continue: its `Solution` docstring says so, and its checker resets load and battery at the depot. A tour is
   therefore a vehicle, not a route. With no time dimension, any set of routes can be chained onto one vehicle, so the cap
   restricts nothing: its rule and the report's define the same feasible routes. Every solution reports its route count; a
   vehicle count is not a model quantity.
2. The 2019 files give OPTIMAL_VALUE to six decimals (384.678035 for E-n22-k4), consistent with unrounded distances. The 2022
   files give integers (383 for E-n29-k4-s7). Their distance convention is unknown until a published solution is replayed; until
   then they are not comparison targets.

The report states a MILP (its (1)-(10)) with binary arcs on V={0} ∪ I ∪ F', where F' holds beta_f=2n copies of each station, and
load u and battery y on arrival initialized to u_0=C and y_0=Q (its footnote 3). Its load row (5) also applies to arcs entering
the depot. For the last customer i of a route it reads u_0 <= u_i-b_i, which contradicts u_0=C, u_i <= C and b_i>0; battery rows
(7) and (8) fail the same way. Read literally, it has no feasible route. Splitting the depot into a source 0 with u=C, y=Q and a
sink 0' with free u and y >= 0 repairs it. R1 below is built on that split.

**2. R1: station-path multigraph MILP**

A route is a sequence of customers joined by segments. A segment from i to j is a station path p=(i,f_1,...,f_k,j), with k >= 0
and f_t in F, as in the recharging-path multigraph of Froger et al. (2019) with non-dominated paths as in Andelmin and Bartolini
(2017). Record its length l_p, the energy a_p=e_{i f_1} needed on leaving i, and the energy omega_p=e_{f_k j} spent after the
last charge. For k=0, a_p=omega_p=e_ij. The path is admissible if a_p <= Q, omega_p <= Q, and every station-to-station leg
consumes at most Q.

For k >= 1 the EV reaches j with Q-omega_p, whatever its charge at i, provided that charge is at least a_p. Among such paths, p
dominates p' when l_p <= l_p', a_p <= a_p' and omega_p <= omega_p'. Replacing a segment by a dominating path keeps every battery
row satisfied and does not lengthen the route. For fixed first and last stations f and g, the best interior is a shortest path
from f to g in the station graph whose edges consume at most Q. Hence

$$
P_{ij}=\{(i,j)\}\ \cup\ \operatorname{Pareto}\{(i,f,\mathrm{SP}(f,g),g,j):f,g\in F\},
$$

where the direct arc is omitted when e_ij > Q, and Pareto keeps the elements minimal in (l, a, omega). Floyd-Warshall on the
station graph costs O(|F|^3). There are at most (n+1)^2|F|^2 candidates before filtering.

Let x_p be binary for p in P = union of the P_ij, with sources in {0} ∪ I and sinks in I ∪ {0'}. Let u_i in [b_i, C] be the load
delivered on the route up to and including i, and y_i in [0, Q] the battery on arrival at customer i. Let delta^+(i) and
delta^-(i) be the paths leaving and entering i, and D the direct arcs between customers.

$$\min\ \sum_{p\in P}l_px_p \tag{R1.1}$$

$$\sum_{p\in\delta^+(i)}x_p=\sum_{p\in\delta^-(i)}x_p=1,\qquad i\in I \tag{R1.2}$$

$$u_j\ge u_i+b_j-C\Big(1-\sum_{p\in P_{ij}}x_p\Big),\qquad i,j\in I,\ i\ne j \tag{R1.3}$$

$$y_i\ge\sum_{p\in\delta^+(i)}a_px_p,\qquad i\in I \tag{R1.4}$$

$$y_j\le Q-\sum_{p\in\delta^-(j)\setminus D}\omega_px_p,\qquad j\in I \tag{R1.5}$$

$$y_j\le y_i-e_{ij}x_{ij}+Q(1-x_{ij}),\qquad (i,j)\in D \tag{R1.6}$$

By (R1.2) exactly one path leaves and one enters each customer. Hence (R1.4) states exactly that the charge on leaving i covers
the first leg of the path used, and (R1.5) states exactly the arrival charge after a station or the depot. Neither needs a
big-M. Only the load row (R1.3) and the direct battery row (R1.6) do. Since every b_j>0, (R1.3) forbids cycles among customers
by the Miller-Tucker-Zemlin argument: u strictly increases around a cycle.

The number of routes, sum_{p in delta^+(0)} x_p, is free in R1. The capacity bound sum_{p in delta^+(0)} x_p >= ceil(sum_i
b_i/C) is valid and is added. There is no path from 0 to 0', so no route is empty. A mid-route return to the depot needs no path
of its own: it resets load and battery, so it is the end of one route and the start of the next, at the same length.

*Equivalence with the report's model (depot split).* Given a feasible route of that model, cut it at customers into station
paths and replace each by a dominating element of P_ij, which exists because shortest interiors and Pareto filtering discard
only dominated paths. The rows (R1.2)-(R1.6) hold and no length increases. Conversely, expand each chosen path of R1 into its
stations. A shortest path with positive lengths visits each station at most once, and a solution has at most n+(number of
routes) <= 2n segments. Hence each station is used at most 2n times, which the report's beta_f=2n copies accommodate.

**3. R2: set-partitioning bound by column generation**

Let Omega be the set of feasible routes, c_r the length of route r, and a_ir the number of visits of r to customer i. The master
LP is

$$
\min\ \sum_{r}c_r\lambda_r\quad\text{s.t.}\quad\sum_ra_{ir}\lambda_r=1\ (i\in I),\quad\lambda\ge0. \tag{R2.1}
$$

Its value is at most z(R1). Pricing over a relaxed route set Omega' containing Omega keeps the bound valid and makes pricing
cheaper. The relaxation is the ng-route set with neighborhoods of size 8 (Baldacci, Mingozzi and Roberti, 2011): a route may
revisit a customer only after leaving that customer's neighborhood memory.

For duals pi of any restricted master, let c̄_r=c_r-sum_i a_ir pi_i and let c̄* be the exact minimum of c̄_r over Omega'. Every
route visits at least one customer, so every feasible lambda satisfies sum_r lambda_r <= n, and adding this redundant row leaves
(R2.1) unchanged. Lagrangian relaxation of the covering rows then gives, for every pi,

$$
z_{LP}(\Omega')\ \ge\ \sum_{i\in I}\pi_i+n\min\{0,\bar c^*\}. \tag{R2.2}
$$

The bound needs an exact pricing minimum, not an exact master. It is the Lagrangian bound of column generation (Lübbecke and
Desrosiers, 2005; BT §11.4 for the duality); the column generation itself is BT §6.1. Heuristic pricing may add columns but
cannot evaluate (R2.2); the final pricing call must be exact, or no bound is reported. Duals come only from the simplex LP of
HiGHS. An interior-point master stopped early, for well-centered duals (Gondzio, González-Brevis and Munari, 2013), was tried in
the Python implementation (revision 89e967d) and was not uniformly faster; it was removed.

Pricing is a shortest path with resource constraints on the multigraph of §2. A label at node i holds (c̄, q, y, M): reduced
cost, load, charge on departure, and ng-memory. Extending along p in P_ij requires y >= a_p and q+b_j <= C. The new charge is
Q-omega_p for k >= 1 and y-e_ij for k=0, and the reduced cost grows by l_p-pi_j. Label L1 dominates L2 at the same node when c̄1
<= c̄2, q1 <= q2, y1 >= y2 and M1 ⊆ M2. The worst case is exponential.

*As implemented* (`crates/efo-kernels/src/price.rs`, called from `crates/efo/src/evrp/r2.rs`). Labels are kept in an arena with
their parent arc, the ng-memory is a 128-bit mask, and labels are extended in order of load. A label at j with load q is
discarded when c̄ + f(j, C − q) > 0. Here f(j, r) is the least reduced cost of a walk from j back to the depot carrying at most
r, computed by a backward recursion over loads that ignores the battery and elementarity. It is therefore a lower bound on every
completion, so no route of negative reduced cost is lost and c̄* is exact whenever it is negative, which is all (R2.2) and
(R2.4) use. The recursion needs integral demands, which every benchmark file has, and costs O(n² C/g) per call, g the gcd of the
demands and C.

The method delivers bounds, not branch-and-price. Upper bounds come from R1 incumbents, from the restricted master solved as a
MILP over the generated elementary columns, and from replayed evrp-python solutions ([Data](DATA.md) §4). A replayed upper bound
that meets the bound within tolerance is certified optimal up to floating-point tolerances.

**4. R2: rounded capacity cuts in the master**

The lifted MTZ row (R1.3) and the covering rows of (R2.1) both ignore that a set S of customers with demand b(S) needs at least
⌈b(S)/C⌉ vehicles. Let β_S(r) be the number of arcs (u, v) of route r's customer sequence 0, i_1, …, i_k, 0 with u ∉ S and v ∈
S. Each route that serves S enters it, so every partition of I into feasible elementary routes satisfies the rounded capacity
inequality (Laporte, Nobert and Desrochers, 1985), in the entry form of Fukasawa et al. (2006):

$$
\sum_r\beta_S(r)\lambda_r\ \ge\ \kappa(S)=\lceil b(S)/C\rceil\qquad(S\subseteq I). \tag{R2.3}
$$

Hence z(R2.1, R2.3) ≤ z*, although an ng-route need not satisfy (R2.3). Stations are not in S, so a station path P_ij enters S
exactly when the arc (i, j) does. With multipliers σ_S ≥ 0 the reduced cost is c̄_r = c_r − Σ_i a_ir π_i − Σ_S σ_S β_S(r), which
is the reduced cost of §3 with the cost w_uv = Σ_{S: u∉S, v∈S} σ_S taken off each arc. The cut is robust: it changes arc costs
only, so the labels and their dominance are unchanged. The argument for (R2.2) then gives, for every π and every σ ≥ 0,

$$
z_{LP}(\Omega';\ \text{R2.3})\ \ge\ \sum_{i\in I}\pi_i+\sum_S\sigma_S\kappa(S)+n\min\{0,\bar c^*\}. \tag{R2.4}
$$

Separation is greedy (Lysgaard, Letchford and Eglese, 2004, §4). Let x_uv = Σ_r λ_r [(u, v) ∈ r]. From each seed customer, S
grows by the customer with the largest flow to and from S, and each S met is tested: y(S) = Σ_{u∉S, v∈S} x_uv < κ(S). R2 always
separates; its formulation is `R2-RCC/1`.

    Input:          instance; route relaxation Omega'; master tolerance; pricing and
                    time limits
    Initialization: Omega_0 = routes of a replayed feasible solution plus
                    one out-and-back route per customer, using station paths
    General step:   (a) solve the restricted master over Omega_k with cuts by the
                        simplex method of HiGHS; read pi and sigma
                    (b) price exactly; evaluate the bound (R2.4) and keep the best
                    (c) add columns with c̄_r < 0
                    (d) if master value - bound <= eps, separate the master's point
                        (R2.3); if a cut is violated, add up to ten and return to (a),
                        else stop
                    (e) stop at a limit

(R2.2) is (R2.4) with no cuts. The bound is valid at every iteration, and at convergence it is at least the LP value without
cuts.

**5. R3: partial recharging with resistive loss (convex MINLP)**

In the report, charging is instantaneous, free and full, so energy has no price and full charging is optimal. R3 asks what
changes when charging takes time and loses energy. Its parameters are declared scenario inputs ([Data](DATA.md) §3). The
benchmark carries no time or price data, and its units are abstract.

R3 allows at most one station between consecutive customers. This restricts the feasible set, so the R3 optimum is an upper
bound on the unrestricted model.

Arcs are direct arcs (i,j) and station arcs s=(i,f,j). In addition to R1's variables, let q_s >= 0 be the energy charged, tau_s
>= 0 the dwell time, g_s the grid energy purchased, and t_i the arrival time at customer i. Let v be the speed, sigma_i the
service time, T the route duration limit, P the charger power, eta in (0,1] the efficiency, and alpha >= 0 the loss coefficient.
For s=(i,f,j):

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

with the closed perspective: (q_s, tau_s)=(0,0) requires only g_s >= 0. The first row of (R3.1) is imposed only when x_s=1,
through (R1.4) with a_s=e_if. The second needs no big-M, since q_s=0 when x_s=0; the third is inactive then because y_i >= 0 and
y_j <= Q. At constant power p=q/tau, resistive loss is proportional to p^2 tau=q^2/tau. Thus alpha has units 1/kW, as in M2, and
M2's slot loss alpha p^2 Delta is (R3.3) with tau=Delta. Time rows follow (R1.3): t_j >=
t_i+sigma_i+(d_if+d_fj)/v+tau_s-M_s(1-x_s) for station arcs, with M_s=T+sigma_i+(d_if+d_fj)/v, the least constant that
deactivates the row when x_s=0. Direct arcs take the same row without tau, and each route returns within T.

The objective is c_d sum_p l_p x_p+c_e sum_s g_s+c_tau sum_s tau_s. Depot energy is outside the objective, as in the report.
With c_e>0 the model therefore prefers depot energy, which is the intended behavior for a fleet that charges overnight.

*Convexity.* Rows other than (R3.3) are affine. The function q^2/tau is the perspective of q^2, hence convex on tau>0, and its
closure is convex on tau >= 0 (Boyd and Vandenberghe, §3.2.6). The continuous relaxation is therefore convex and R3 is a convex
MINLP; (R3.3) is a rotated second-order cone, (tau_s/2, (g_s-q_s/eta)/alpha, q_s) satisfying 2ab >= c^2.

*Cuts.* The function q^2/tau is positively homogeneous of degree 1, so its tangent planes pass through the origin. At a point
with power r=q/tau,

$$q^2/\tau\ \ge\ 2rq-r^2\tau, \tag{R3.4}$$

valid for all tau >= 0. Outer approximation ([Algorithms](ALGORITHMS.md) §5) uses (R3.4) at the powers of each subproblem
solution; the fixed-route problem is solved by the barrier method of [Algorithms](ALGORITHMS.md) §4.

*As implemented* (`crates/efo/src/evrp/r3.rs`). The charge rows are equalities on used arcs, two big-M rows each. With partial
charging, y must be the true charge, or the capacity row y_i - e_if + q <= Q is under-stated; the replay caught exactly that, a
battery filled past Q, while the rows were one-sided. Each used station holds the vehicle at least tau_min, so (R3.3) is smooth
for the barrier method. The cuts (R3.4) remain valid down to tau = 0. With free, near-instantaneous charging, R3's optimum
equals R1's restricted to one station per segment. Nonlinear charging functions (Montoya et al., 2017) make the fixed-route
problem nonconvex and are not modeled.

**6. What each model certifies**

| Model | Class | Lower bound | Claim |
| --- | --- | --- | --- |
| R1 | MILP | HiGHS MIP dual bound; replayed incumbent | Optimal value of the report's EVRP, free fleet, within tolerance |
| R2 (`R2-RCC/1`) | LP by column generation with cuts | (R2.4) with exact pricing | Lower bound on R1 at every iteration |
| R3 | Convex MINLP (MISOCP) | OA master dual bound | Global optimum under k <= 1 and declared parameters |

**7. Published values and replay**

evrp-python supplies an independent heuristic upper bound: a greedy search and a greedy genetic algorithm (GSGA). The README
reports that the C++ version ranked in the top three of the competition. Reading its source at `16d3499` shows differences that
make its outputs inputs to replay, not results:

1. It counts vehicles that may make several trips, not routes (§1).
2. `check_valid_solution` rejects repeated customers but does not check that every customer is visited.
3. The checker walks tours as stored, while `calculate_tour_length` adds the depot legs. Whether depot legs are energy-checked
   depends on the stored representation; this is tested, not assumed.
4. `calculate_tour_length` returns twice the length of an invalid solution, so a fitness value is not a length until validated.
5. Its README table reports, for X-n573-k30 under VNS, a minimum of 52181.51 above a maximum of 51929.24. Published summaries
   are therefore re-measured by replay, never copied.

The project keeps GSGA routes from that commit as data ([Data](DATA.md) §4) and replays them with its own validator (`efo replay
<instance> <routes>`), which reads only the instance file and the routes. Solutions are exchanged in one format: one line per
route, as 1-based node identifiers of the instance file, with the depot at both ends. A replayed route set certifies its own
cost as an upper bound; it enters R2 as seed columns.
