# Transit models

The routing models R0-R4 are in [Routing](ROUTING.md). All costs are minimized. Vector inequalities are componentwise. Time is in hours,
distance in km, energy in kWh, and power in kW. A result is exact only for its
declared graph, input parameters, temporal resolution, and solver tolerances.

**1. Instance and graph**

Let I be the mandatory passenger trips, K the finite set of candidate buses,
S the candidate charging sites, and T the charging intervals. Each bus k has
capacity B_k, reserve fraction r_k, initial fraction s_k^0, and upper operating
fraction s_k^max < 1. Bus types and capacities are parameters, not continuous
design variables. Enumerating candidate types avoids products of capacity and
state of charge.

Construct a directed acyclic time-space graph G=(V,A). Nodes identify a physical
location and a time boundary. Arcs represent passenger trips, empty travel, or
waiting. Every arc advances time. Passenger trip i has one compulsory service
arc a(i); its full published stop sequence is retained for independent replay.
Charging is possible only on a waiting arc at a candidate site.

The reference formulation uses a uniform interval length Delta. A trip beginning
at h and ending at h' occupies [floor(h/Delta)Delta, ceil(h'/Delta)Delta]. An
empty movement of duration tau occupies ceil(tau/Delta) intervals. This is a
conservative scheduling convention: original passenger times do not move, but
adjacent vehicle availability is restricted. Remove arcs that cannot be reached
from a depot or cannot reach a terminal depot by the horizon.

Let b_k have +1 at bus k's initial depot node, -1 at its terminal depot node,
and zero elsewhere. Let N be the node-arc incidence matrix with outgoing arcs
positive. Let w(s,t) denote the waiting arc at site s during interval t. If it
does not exist, every variable indexed by that waiting opportunity is fixed to
zero or omitted. There are no arcs representing arbitrary instantaneous changes
of location.

Let E_ak >= 0 be energy consumed by bus k on movement arc a. Define d_akt >= 0
so sum_t d_akt=E_ak. Initially, place all consumption in the arc's first interval.
Because the bus cannot charge while traversing the arc and energy consumption is
nonnegative, this enforces the reserve conservatively throughout the movement.
It is not a measured within-trip energy trace. A later profile must preserve the
same total and be independently checked.

Horizon selection includes the complete selected service day and recovery
charging. Do not truncate trips after midnight. An isolated extended-horizon
experiment is not automatically a repeatable 24-hour operating schedule.

**2. M0: battery-free scheduling**

For homogeneous buses at one depot, construct the trip compatibility DAG:
i precedes j when the end of i plus deadhead and required turnaround is no later
than the start of j. All trips must be individually reachable from and returnable
to the depot within the horizon.

Let x_ij indicate that j immediately follows i. The maximum-cardinality matching
formulation is

$$
\max\ \sum_{(i,j)\in A_I}x_{ij},\qquad
\sum_j x_{ij}\le1,\quad \sum_i x_{ij}\le1,\quad x\ge0.
$$

Its extreme points are integral. The minimum fleet is

$$K_{\min}=|I|-\max\sum_{(i,j)\in A_I}x_{ij}.$$

The matching produces a path cover because time prohibits cycles. Compare it
with a separate minimum-cost flow formulation, including deployment and deadhead
costs when those are the objective. An IPM can return a fractional point on an
optimal face even though an integral optimum exists; use crossover or a matching
algorithm to obtain actual duties. Never round a central-path point and invoke
the integrality theorem as justification.

Removing battery and charger restrictions makes M0 a lower bound on fleet count.
It is a lower bound on total cost only when its cost terms are aligned with the
full objective and omitted terms are nonnegative. The elementary matching claim
does not extend automatically to heterogeneous buses or prescribed multi-depot
return constraints. Sources: Vanderbei Chapters 14-15; BT Ch. 7 (the assignment
problem); PS (bipartite matching, total unimodularity).

**3. M1: joint scheduling and charging MILP**

Decision variables:

| Symbol | Domain | Meaning |
| --- | --- | --- |
| x_ak | binary | Bus k uses arc a |
| z_k | binary | Bus k is deployed |
| u_kst | binary | Bus k occupies a charging plug at s in t |
| p_kst | nonnegative | Average power entering the battery |
| g_kst | nonnegative | Average grid power consumed by that charging opportunity |
| e_kt | nonnegative | Battery energy at interval boundary t |
| y_s | binary | Candidate site s opens |
| n_s | integer in [0,nbar_s] | Number of installed plugs |
| h_s | nonnegative, bounded | Additional grid capacity |
| D_s | nonnegative, bounded | Peak total site power in the modeled horizon |

Let P_ks be the battery-side power limit, eta_ks in (0,1] the constant conversion
efficiency, G_s^0 the existing grid capacity, hbar_s the permitted upgrade, L_st
the exogenous site load, and c_st >= 0 the energy price. Sites have nonnegative
opening, plug, and upgrade cost coefficients f_s, a_s, and b_s. Bus k has cost
F_k; movement arc a has operating cost c_ak. Let pi_s >= 0 price the modeled peak.

For an existing site, fix y_s=1 and represent existing plugs as a constant added
to n_s, with n_s then denoting additions. The equations below use the simpler
all-candidate convention. Availability and upper bounds are finite input data.

The objective is

$$
\min C_1=
\sum_k F_kz_k+\sum_{a,k}c_{ak}x_{ak}
+\sum_s(f_sy_s+a_sn_s+b_sh_s+\pi_sD_s)
+\Delta\sum_{k,s,t}c_{st}g_{kst}. \tag{1}
$$

For each bus, impose a single source-to-sink path or no path:

$$Nx_k=b_kz_k,\qquad 0\le x_{ak}\le z_k. \tag{2}$$

Each passenger trip is served exactly once:

$$\sum_k x_{a(i),k}=1,\qquad i\in I. \tag{3}$$

Remove bus-incompatible arcs before constructing (2). Integral flow on a DAG
with one unit from source to sink cannot contain an extra disconnected cycle.
This avoids subtour big-M constraints entirely. Artificial source/sink links,
if used, must still enforce the stated depot and horizon rules.

Connection and power constraints are

$$
u_{kst}\le x_{w(s,t),k},\quad
\sum_su_{kst}\le z_k,\quad
0\le p_{kst}\le P_{ks}u_{kst},\quad
g_{kst}=p_{kst}/\eta_{ks}. \tag{4}
$$

Shared plugs and grid capacity satisfy

$$
\sum_ku_{kst}\le n_s,\quad
n_s\le\bar n_sy_s,\quad 0\le h_s\le\bar h_sy_s, \tag{5}
$$

$$
L_{st}+\sum_kg_{kst}\le G_s^0+h_s,\qquad
D_s\ge L_{st}+\sum_kg_{kst}. \tag{6}
$$

The initial case assumes a shared controllable charger bank at each site and
identical plugs there. A connection may change at an interval boundary. With
zero connection time this is an explicit idealization. To model one full slot of
setup, add binary v_kst >= u_kst-u_ks,t-1 and impose
p_kst <= P_ks(u_kst-v_kst), with u_ks,-1=0. The setup slot still occupies a plug.
Any shorter setup time requires its own finer timing convention, not an unexplained
fraction of a binary connection.

Energy conservation is affine:

$$
e_{k,t+1}=e_{kt}+\Delta\sum_sp_{kst}-\sum_ad_{akt}x_{ak}. \tag{7}
$$

Battery bounds and boundary conditions are

$$
r_kB_kz_k\le e_{kt}\le s_k^{\max}B_kz_k,\qquad
e_{k0}=s_k^0B_kz_k,\qquad e_{kT}=e_{k0}. \tag{8}
$$

The final equality prevents free energy from depletion at the study boundary.
Return to the home depot is enforced by (2). A multi-day operational study must
carry energy between days instead of resetting every day for free. If a fixed
ready-energy target replaces the equality, state it and reconcile both schedules
to the same target before comparing costs.

All terms in (1)-(8) are linear. Binary variables encode scheduling and
connections; integer n encodes plug count. Symmetry breaking z_k >= z_k+1 is
permitted only among fully identical candidate buses. No symmetry row may change
which bus types or initial conditions are available.

**3a. M1 as implemented: connection form**

The per-bus form above indexes identical candidate buses, so every relabeling of an
optimal schedule is again optimal; with 20 or more buses this symmetry weakens the
branch-and-bound bound. `models/fleet.py` therefore writes M1 without a bus index, in
the connection form of M0. x_ij = 1 when trip j is the next trip after trip i on a
bus; x_0j and x_i0 are pull-outs and pull-ins, and the fleet is sum x_0j, as in M0.
Rows (2) and (3) become in- and out-degree rows over these arcs.

Energy is carried per trip. a_j is the energy on arrival at j's first stop, and y_j
the energy on departing it: a_j = y_i - E_i - e_ij for the chosen predecessor, or
s0 B - e_0j after a pull-out, both as two-sided big-M rows with M = smax B + e. Then
y_j = a_j + Delta sum_t p_jt. The bound rB <= a_j keeps the deadhead above reserve,
and rB + E_j <= y_j takes the trip's energy at its start, as in §1. Pull-in rows keep
the last deadhead above reserve and define the end-of-day energy z_i. The objective
charges the overnight restore to s0 B at the depot price.

Charging is restricted in two stated ways. A bus charges only at the first stop of its
next trip, when that stop is a candidate site, in the slots of a window before the
departure (`time.window` in the scenario). A slot counts only if it lies wholly after
the predecessor's arrival there, deadhead included: u_jt <= x_0j + sum_{i present} x_ij,
and exactly one predecessor is chosen. So a bus deadheads first and then charges, and
never charges at a trip's end stop when its next trip starts elsewhere. These are
restrictions: the per-bus form admits every schedule of this one, so its optimum is
no higher. On Route 100 consecutive trips alternate terminals, and both terminals are
sites.

Rows (5) and (6) are unchanged, summed per site and slot over the windows present.
The replay in `checks/schedule.py` simulates each bus slot by slot. It checks energy,
windows, presence, plugs and grid, and recomputes the cost from the schedule alone.
`checks/enum_transit.py` solves tiny one-site timetables by enumerating every partition
of the trips into chains, with a charging MILP written separately for each partition.

**4. M1-Q and M2: convex nonlinear charging**

For M1-Q, add

$$\Phi(p)=\Delta\sum_{k,s,t}\gamma_{ks}p_{kst}^2,\qquad \gamma_{ks}\ge0 \tag{9}$$

to the objective, retaining M1 constraints. With integers fixed this is a convex
QP. It is a convenient textbook QP benchmark and a penalty against concentrated
charging power. Its units are currency/(kW squared hour). It is not a fitted
electrochemical aging law.

For M2, replace constant conversion in (4) by

$$
g_{kst}\ge p_{kst}/\eta_{ks}+\alpha_{ks}p_{kst}^2,
\quad 0\le g_{kst}\le\bar g_{ks}u_{kst},\quad \alpha_{ks}\ge0, \tag{10}
$$

where gbar_ks=P_ks/eta_ks+alpha_ks P_ks^2. Here alpha has units 1/kW.
Impose a conservative charging-taper envelope:

$$
p_{kst}\le P_{ks}\left(1-\frac{e_{k,t+1}}{B_k}\right). \tag{11}
$$

Together with (4)'s power bound, (11) is harmless at an unvisited site and forces
charging to slow near the upper state of charge. It represents the linear taper
law introduced below, not an asserted manufacturer's charging curve. Retain (9),
with gamma=0 when studying charging loss alone.

The convexity proof is direct. Equations (2)-(8) and (11) are affine; (10) has
convex left side p/eta+alpha p^2-g; the Hessian of (9) is diagonal and
nonnegative. Relaxing integrality therefore gives a convex program. M2 is a
convex MINLP and, more specifically, a mixed-integer convex quadratically
constrained program. Its fixed-integer subproblem is globally solvable in
principle, subject to the numerical and constraint-qualification provisions in
[Algorithms](ALGORITHMS.md).

With nonnegative prices and no lower bound on purchased grid power, every
feasible solution can replace g by p/eta+alpha p^2, and then reduce D to the
actual maximum. This preserves feasibility and cannot increase cost. Thus the
epigraph in (10) is exact for the modeled objective. When prices or peak costs
are zero, the solver may leave g or D slack; the validator tightens them and
reconstructs the objective. Negative prices, mandatory grid import, or grid
services invalidate this argument and are outside M2's contract.

The conic form follows from h=g-p/eta >= alpha p^2: after nondimensionalization,
(h,1/2,sqrt(alpha)p) belongs to the rotated second-order cone
{(a,b,v): 2ab >= ||v||^2, a,b >= 0}. The objective term has the same epigraph
construction. This supplies an optional independent SOCP check at fixed integers.
No mixed-integer conic solver is required by the design.

For an optional stronger relaxation, replace p^2 by its closed perspective p^2/u
in the on/off epigraph, with p=0 at u=0. This agrees at binary u and strengthens
fractional u. Use its conic form; do not differentiate p^2/u at u=0. Implement
the ordinary convex form first and measure whether the perspective is useful.

Since M2 tightens M1's feasible set and adds nonnegative loss/stress costs,
the M1 optimum is a lower bound on M2 only when all other inputs, costs,
connection rules, and the time graph are identical. A different tariff or grid
is not a relaxation comparison.

**5. M2-P: two MILP approximations**

Let q(p)=alpha p^2 on [0,P], with breakpoints 0=b_0<...<b_J=P. Tangents give
the underestimator

$$q^-(p)=\max_j\{q(b_j)+q'(b_j)(p-b_j)\}\le q(p). \tag{12}$$

Secant interpolation between adjacent breakpoints gives q^+(p) >= q(p).
For a convex univariate quadratic, the continuous convex piecewise-linear
interpolant is the maximum of its segment affine extensions on [0,P]. Its
epigraph can therefore be written with linear rows, without SOS2 or segment
binaries. Apply the same construction to (9).

The lower model substitutes q^- for losses and stress. Its MILP dual bound is
a lower bound on M2. The upper model substitutes q^+; its feasible schedules
are feasible for M2, and their exact reconstructed M2 objective is an upper bound.
For interval width delta, the loss interpolation error is at most
alpha delta^2/4. This is a pointwise function error, not a bound on fleet-count
changes or objective sensitivity near a feasibility threshold. Refine nested
breakpoints and report the actual bracket, not a presumed approximation quality.

The upper MILP is also a reliable source of M2 incumbents when a nonlinear solve
has difficulty finding feasible points. Sources: Beck Chapter 7 and the
outer-approximation references in [Sources](SOURCES.md).

**6. M3: nonconvex charging with an integrated taper law**

M3 asks what the conservative endpoint envelope omits. To isolate this issue,
set alpha=gamma=0 in the first M3 experiment. Within a connected interval,
stipulate the battery charging law

$$\dot e=q(1-e/B),\qquad 0\le q\le P, \tag{13}$$

with constant command q during the interval. It integrates to

$$e^+=B-(B-e)\exp(-\Delta q/B). \tag{14}$$

This is exact for (13). The law itself is an assumed taper model and requires
measured curves before it can represent particular equipment.

Introduce command q_kst in [0,P_ks u_kst], set p_kt=sum_s p_kst and
q_kt=sum_s q_kst, and retain energy balance (7). Charge and movement are mutually
exclusive through the path/connection constraints. Replace (11) by

$$
-\log\left(1-\frac{e_{kt}+\Delta p_{kt}}{B_k}\right)
+\log\left(1-\frac{e_{kt}}{B_k}\right)
=\frac{\Delta q_{kt}}{B_k}. \tag{15}
$$

Require 0 <= e_kt+Delta p_kt <= s_k^max B_k. When driving, p=q=0 and (15) is
an identity; when charging, it enforces (14). For inactive buses e=p=q=0, so
the logarithms are well-defined. Fixed zero directions should be eliminated
before sending a subproblem to an NLP solver.

The two nonlinear terms in (15) are a difference of convex functions. Their
equality is generally nonconvex even when integer variables are fixed. M2's
constant battery-power schedule satisfies (13) under a variable command no
larger than P if its endpoint envelope holds. M3 instead fixes command within
each interval and allows battery power to decrease. These are different
within-slot control policies; do not compare their objectives as a bound pair
without an explicit common-control relaxation.

Grid energy in an interval is Delta p/eta. The maximum grid power occurs at
the interval start:

$$\widehat g_{kst}=q_{kst}(1-e_{kt}/B_k)/\eta_{ks}. \tag{16}$$

Use sum_k ghat_kst+L_st in site-capacity and peak rows. Since every connection
starts at a shared slot boundary and each charge trace decreases within that
slot, these rows bound the entire interval for piecewise-constant base load.
Using average grid power alone would conceal within-slot peak violations.

Report local solutions from multiple feasible starts and validate (14) with
independent numerical integration. KKT residuals refer only to the fixed-integer
NLP. Enumeration of binary schedules with local NLP solves is not a global MINLP
certificate. An aligned M1 with constant efficiency, no stress/loss cost, no
taper, and the same graph gives a valid optimistic bound: its grid power is the
interval average, which cannot exceed M3's initial charging peak. A strong global
M3 solver using spatial branching is a separate later project, not promised here.

**7. M4: specified energy scenarios**

Let Omega be a finite scenario set with weights w_omega >= 0 summing to one.
Keep vehicle paths x, deployed buses z, sites y, plug counts n, and upgrades h
common to every scenario. Let energy consumption d^omega vary. Initially keep
travel times fixed so the same graph represents every scenario. Charging,
connection, and energy states may be scenario recourse only after the scenario
is assumed revealed. Impose M1 or M2 rows separately in each scenario.

Minimize common investment plus expected operating cost, subject to feasibility
in every scenario. An alternative worst-case model introduces theta >= C_omega
and minimizes investment+theta. Both retain convex continuous relaxations for M2.

If the complete scenario is revealed only gradually, scenario-specific decisions
with the same observation history must be equal. A two-stage model with complete
revelation before service is an information assumption, not a deployment policy.
Unobserved future energy cannot drive present charging in replay.

Worst-case independent bounds on nonnegative movement energy can instead be
handled by substituting their upper values into (7). This is robust only for
those bounds and the stated ability to adjust charging; it may be conservative.
Travel-delay uncertainty requires rebuilding compatibility or using a common
graph valid for all included delays. Never hold a nominal graph fixed while
claiming robust travel-time feasibility.

No CVaR, distributionally robust formulation, or predictive ML is required for
the first release. Add these only when a concrete data and decision question
justifies the additional probability model.

**8. Calibration and sensitivity**

If measured energy traces later become available, fit nonnegative energy
coefficients by constrained least squares or compare L1 regression for outlier
sensitivity. A possible model is E_i=theta_1 distance_i+theta_2 duration_i,
theta >= 0; its coefficients and error units must be stated. Split by service
day and vehicle before fitting, rather than splitting adjacent samples of one
trip across train and test. Beck Chapters 3-4 and Vanderbei Chapter 12 motivate
these alternatives. GTFS alone cannot identify them.

For a convex charging subproblem, a grid-capacity multiplier is a local marginal
value with all discrete decisions fixed. For the fleet problem, evaluate finite
capacity increments by resolving the integer model. An LP dual is not a global
investment price for a discrete plug or an additional bus.
