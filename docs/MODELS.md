# Transit models

These models turn a published service timetable into a vehicle-blocking, charging, and grid capacity problem. Their outputs are
scenario results for the declared graph and inputs, not a reconstruction of agency dispatch or a capital approval. Passenger
trips and their stopping patterns are fixed; vehicles are reassigned between trips. The schedules are vehicle schedules, not
driver duties.

The routing models R1-R3 are in [Routing](ROUTING.md). All costs are minimized. Vector inequalities are componentwise. Time is
in hours, distance in km, energy in kWh, and power in kW. A result is exact only for its declared graph, input parameters,
temporal resolution, and solver tolerances.

**1. Instance and graph**

Let I be the mandatory passenger trips, K the finite set of candidate buses, S the candidate charging sites, and T the charging
intervals. Each bus k has capacity B_k, reserve fraction r_k, initial fraction s_k^0, and upper operating fraction s_k^max < 1.
Bus types and capacities are parameters, not continuous design variables.

Construct a directed acyclic time-space graph G=(V,A). Nodes identify a physical location and a time boundary. Arcs represent
passenger trips, empty travel, or waiting. Every arc advances time. Passenger trip i has one compulsory service arc a(i); its
full published stop sequence is retained for independent replay. Charging is possible only on a waiting arc at a candidate site.

The reference formulation uses a uniform interval length Delta. A trip beginning at h and ending at h' occupies
[floor(h/Delta)Delta, ceil(h'/Delta)Delta]. An empty movement of duration tau occupies ceil(tau/Delta) intervals. This is a
conservative scheduling convention: original passenger times do not move, but adjacent vehicle availability is restricted. Arcs
that cannot be reached from a depot or cannot reach a terminal depot by the horizon are removed.

Let b_k have +1 at bus k's initial depot node, -1 at its terminal depot node, and zero elsewhere; N is the node-arc incidence
matrix, outgoing arcs positive. w(s,t) is the waiting arc at site s during interval t; where it does not exist, every variable
indexed by that opportunity is omitted. No arc changes location instantaneously.

Let E_ak >= 0 be energy consumed by bus k on movement arc a. Define d_akt >= 0 so sum_t d_akt=E_ak. All consumption is placed in
the arc's first interval. Because the bus cannot charge while traversing the arc and energy consumption is nonnegative, this
enforces the reserve conservatively throughout the movement. It is not a measured within-trip energy trace.

The horizon is the complete selected service day; trips after midnight are not truncated. An isolated extended-horizon
experiment is not automatically a repeatable 24-hour operating schedule. Overnight recovery charging is outside the day as
implemented; the connection form prices it as an external term (§4).

**2. M0: battery-free fleet**

For homogeneous buses at one depot, construct the trip compatibility DAG: i precedes j when the end of i plus deadhead and
required turnaround is no later than the start of j. All trips must be individually reachable from and returnable to the depot
within the horizon.

Let x_ij indicate that j immediately follows i. A set of such pairs with at most one successor and one predecessor per trip is a
matching in the bipartite graph of the DAG arcs; because time prohibits cycles, it is a path cover, each path being one bus's
duty. The minimum fleet is

$$K_{\min}=|I|-\nu,$$

where nu is the size of a largest matching. It is found by augmenting paths (Kuhn, 1955), which returns actual duties, not a
fractional point.

Removing battery and charger restrictions makes M0 a lower bound on fleet count. It is a lower bound on total cost only when its
cost terms are aligned with the full objective and omitted terms are nonnegative. The matching argument does not extend
automatically to heterogeneous buses or prescribed multi-depot return constraints. Sources: Kuhn (1955); PS (bipartite
matching).

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

Let P_ks be the battery-side power limit, eta_ks in (0,1] the constant conversion efficiency, G_s^0 the existing grid capacity,
hbar_s the permitted upgrade, L_st the base load on site s's meter, and c_st >= 0 the energy price. Sites have nonnegative
opening, plug, and upgrade cost coefficients f_s, a_s, and b_s. Bus k has cost F_k; movement arc a has operating cost c_ak. Let
pi_s >= 0 price the modeled peak.

For an existing site, fix y_s=1 and represent existing plugs as a constant added to n_s, with n_s then denoting additions. The
equations below use the simpler all-candidate convention. Availability and upper bounds are finite input data.

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

Bus-incompatible arcs are removed before constructing (2). Integral flow on a DAG with one unit from source to sink cannot
contain an extra disconnected cycle, so no subtour big-M constraints are needed.

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
L_{st}y_s+\sum_kg_{kst}\le G_s^0+h_s,\qquad
D_s\ge L_{st}y_s+\sum_kg_{kst}. \tag{6}
$$

Both rows hold for every slot t of the horizon (the peak row for every slot of the billing window), whether or not a charging
variable exists there. L is load on the site's own meter, and that meter exists only when the site opens: its basic charge is
paid per open site. A closed candidate site therefore bills no demand and obliges no capacity, whatever L and G^0. Load at an
existing meter that is billed whether or not the site opens is the other reading; it would drop y_s from both rows and add its
demand charge as a constant. The two readings are not mixed.

The plug link in (5) is aggregated: in the LP relaxation it gives only y_s ≥ Σ_k u_kst / n̄_s. CMIP (Roni, Yi and Smart, 2019)
links each assignment to its site instead, x_a ≤ z_s, a tighter facility-location form; here u_kst ≤ y_s, valid because u_kst =
1 forces n_s ≥ 1 and hence y_s = 1. The rows are not adopted: in the Python implementation (revision 2533ebe) the root LP bound
was unchanged, because the LP optimum already opens both loops, and certified values agreed. They matter only when candidate
sites outnumber the sites the LP must open.

The initial case assumes a shared controllable charger bank at each site and identical plugs there. A connection may change at
an interval boundary. With zero connection time this is an explicit idealization. To model one full slot of setup, add binary
v_kst >= u_kst-u_ks,t-1 and impose p_kst <= P_ks(u_kst-v_kst), with u_ks,-1=0. The setup slot still occupies a plug. Any shorter
setup time requires its own finer timing convention, not an unexplained fraction of a binary connection.

Energy conservation is affine:

$$
e_{k,t+1}=e_{kt}+\Delta\sum_sp_{kst}-\sum_ad_{akt}x_{ak}. \tag{7}
$$

Battery bounds and boundary conditions are

$$
r_kB_kz_k\le e_{kt}\le s_k^{\max}B_kz_k,\qquad
e_{k0}=s_k^0B_kz_k,\qquad e_{kT}=e_{k0}. \tag{8}
$$

The final equality prevents free energy from depletion at the study boundary. Return to the home depot is enforced by (2). A
multi-day operational study must carry energy between days instead of resetting every day for free. If a fixed ready-energy
target replaces the equality, state it and reconcile both schedules to the same target before comparing costs. The equality is
the cyclic boundary, overnight recovery included: the only one under which a schedule repeats from one day to the next, and only
if the recovery charging inside the horizon (depot plugs and power, depot grid capacity, the time after each return, the tariff
window) is feasible.

All terms in (1)-(8) are linear. Binary variables encode scheduling and connections; integer n encodes plug count. Symmetry
breaking z_k >= z_k+1 is permitted only among fully identical candidate buses. No symmetry row may change which bus types or
initial conditions are available.

**4. M1 as implemented: connection form**

The per-bus form above indexes identical candidate buses, so every relabeling of an optimal schedule is again optimal; with 20
or more buses this symmetry weakens the branch-and-bound bound. `crates/efo/src/transit/fleet.rs` therefore writes M1 without a
bus index, in the connection form of M0. x_ij = 1 when trip j is the next trip after trip i on a bus; x_0j and x_i0 are
pull-outs and pull-ins, and the fleet is sum x_0j, as in M0. Rows (2) and (3) become in- and out-degree rows over these arcs.

Energy is carried per trip. a_j is the energy on arrival at j's first stop, and y_j the energy on departing it: a_j = y_i - E_i
- e_ij for the chosen predecessor, or s0 B - e_0j after a pull-out, both as two-sided big-M rows with M = smax B + e. Then y_j =
a_j + Delta sum_t p_jt. The bound rB <= a_j keeps the deadhead above reserve, and rB + E_j <= y_j takes the trip's energy at its
start, as in §1. Pull-in rows keep the last deadhead above reserve.

*Terminal boundary: external overnight recovery.* For each pull-in i the restoration variable r_i satisfies

$$r_i\ge s^0B-(y_i-E_i-e_{i0})\ \text{ if } x_{i0}=1,\qquad 0\le r_i\le(s^0-r)Bx_{i0},$$

and the objective prices rho c_dep r_i / eta: the depot restores each bus to s0 B overnight, outside the modeled day. A bus that
returns above s0 B is credited nothing, since the model has no export or vehicle-to-grid decision; under nonnegative prices no
schedule earns revenue from terminal energy. A signed restoration term s0 B - z_i with z_i up to smax B paid a depot credit and
is excluded ([Validation](VALIDATION.md) §2).

The recovery itself is not modeled: no depot plugs or charger power, no depot grid capacity, no time window after each return,
no 22:00-06:00 tariff window, no circulation of buses into the next day. The restoration term is a sensitivity calculation of
the energy bill, not a feasible recovery process, and no M1 schedule is claimed to repeat from one service day to the next. A
depot model would need, per bus, the return time, the energy on return and the energy to restore.

Charging is restricted in two stated ways. A bus charges only at the first stop of its next trip, when that stop is a candidate
site, in the slots of a window before the departure (`time.window` in the scenario). A slot counts only if it lies wholly after
the predecessor's arrival there, deadhead included: u_jt <= x_0j + sum_{i present} x_ij, and exactly one predecessor is chosen.
So a bus deadheads first and then charges, and never charges at a trip's end stop when its next trip starts elsewhere. These are
restrictions of the charging opportunities. The per-bus form of §3 admits every schedule of this one, and so has an optimum no
higher, only when both use the same depot, horizon and terminal-energy assumption. They do not as written: §3 imposes the cyclic
boundary inside a horizon that includes recovery charging, whereas this form ends at the last pull-in and prices recovery
externally. Containment, and the bound it would give, holds for a per-bus form with the same external restoration term. On Route
100 consecutive trips alternate terminals, and both terminals are sites.

Rows (5) and (6) are summed per site and slot over the windows present, with the base load L_s y_s in every capacity and peak
row; the rows L_s y_s <= G0_s + h_s and D_s >= L_s y_s are written once per site, so the meter's obligations do not depend on
which slots carry a charging variable. `crates/efo/src/transit/mod.rs` compiles the instance (compatibility arcs, deadhead
distances, energies, windows, input digests) once; M2's fixed-integer subproblems reuse the rows and change only bounds and
nonlinear terms. The replay (`transit/replay.rs`) simulates each bus slot by slot, checks energy, windows, presence, plugs and
grid, and recomputes the cost from the schedule alone. `transit/enumerate.rs` solves tiny one-site timetables by enumerating
every partition of the trips into chains, with a charging MILP written separately for each partition.

A utility tariff ([Data](DATA.md) §3) changes three terms. The peak row of (6) is written only for slots whose start lies in the
billing-demand window [`peak_from`, `peak_to`) of the day, so D_s is the peak inside the window: BC Hydro's Overnight Rate bills
demand between 06:00 and 22:00 only. A window with `peak_from` > `peak_to` wraps across midnight. In a one-day model the monthly
demand charge enters as a normalized daily weight (charge x 12/365), a sensitivity coefficient, not a bill. The factor 1 +
`rider` multiplies the energy, depot-energy, demand and basic prices, and the basic charge is paid per open site. Absent keys
give the whole day, 1 and 0, and the rows of before. The replay and the enumeration price the tariff separately.

**5. M2: convex nonlinear charging**

Replace constant conversion in (4) by

$$
g_{kst}\ge p_{kst}/\eta_{ks}+\alpha_{ks}p_{kst}^2,
\quad 0\le g_{kst}\le\bar g_{ks}u_{kst},\quad \alpha_{ks}\ge0, \tag{10}
$$

where gbar_ks=P_ks/eta_ks+alpha_ks P_ks^2. Here alpha has units 1/kW. Impose a conservative charging-taper envelope:

$$
p_{kst}\le P_{ks}\left(1-\frac{e_{k,t+1}}{B_k}\right). \tag{11}
$$

Together with (4)'s power bound, (11) is harmless at an unvisited site and forces charging to slow near the upper state of
charge. It is a linear taper law, not an asserted manufacturer's charging curve. (Equation number (9) is not used.)

The convexity proof is direct. Equations (2)-(8) and (11) are affine; (10) has convex left side p/eta+alpha p^2-g. Relaxing
integrality therefore gives a convex program. M2 is a convex MINLP and, more specifically, a mixed-integer convex quadratically
constrained program. Its fixed-integer subproblem is globally solvable in principle, subject to the numerical and
constraint-qualification provisions in [Algorithms](ALGORITHMS.md) §4.

With nonnegative prices and no lower bound on purchased grid power, every feasible solution can replace g by p/eta+alpha p^2,
and then reduce D to the actual maximum. This preserves feasibility and cannot increase cost. Thus the epigraph in (10) is exact
for the modeled objective. When prices or peak costs are zero, the solver may leave g or D slack; the validator tightens them
and reconstructs the objective. Negative prices, mandatory grid import, or grid services invalidate this argument and are
outside M2's contract.

The conic form follows from h=g-p/eta >= alpha p^2: after nondimensionalization, (h,1/2,sqrt(alpha)p) belongs to the rotated
second-order cone {(a,b,v): 2ab >= ||v||^2, a,b >= 0}.

Since M2 tightens M1's feasible set and adds a nonnegative loss cost, the M1 optimum is a lower bound on M2 only when all other
inputs, costs, connection rules, and the time graph are identical. A different tariff or grid is not a relaxation comparison.

*As implemented.* `crates/efo/src/transit/fleet.rs` solves M2 by outer approximation ([Algorithms](ALGORITHMS.md) §5). At the
integers of a master point every integer is fixed at its rounded value, p = g = 0 where u = 0, and r_i = 0 where trip i is not a
pull-in, so no barrier acts on a face without interior; the barrier method then solves the continuous problem. For a convex
charging subproblem, a grid-capacity multiplier is a local marginal value with all discrete decisions fixed; for the fleet
problem, finite capacity increments are evaluated by resolving the integer model. An LP dual is not a global investment price
for a discrete plug or an additional bus.
