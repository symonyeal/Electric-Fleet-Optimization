# Sources

This is the provenance register for the benchmark rules, transit inputs, algorithms, and
charging assumptions used by the live models.

A formulation is validated by the source it implements, not by the solver that
ran it. Cite only what this file records, and add the entry in the change that
uses it. Status is **inspected** (read for this project, with what was read) or
**cited** (known reference, not yet read; read before the phase that relies on
it, then update the status).

**1. Textbooks**

| Source | Used for | Status |
| --- | --- | --- |
| R. J. Vanderbei, *Linear Programming: Foundations and Extensions*, 4th ed., Springer, 2014 | Ch. 5 duality; Ch. 12 regression; Ch. 14-15 network flows and integrality; Ch. 17-20 central path, path-following method, KKT system, implementation; Ch. 22 homogeneous self-dual method; Ch. 23 integer programming; Ch. 24 quadratic programming; Ch. 25 convex programming | Inspected from the local PDF. Chapter numbers re-checked against the PDF outline on 2026-09-28: all agree |
| A. Beck, *Introduction to Nonlinear Optimization: Theory, Algorithms, and Applications with MATLAB*, SIAM, 2014 | Ch. 3-4 least squares and gradient method; Ch. 5 Newton's method; Ch. 7-8 convex functions and convex optimization; Ch. 10-12 optimality conditions, KKT, duality | Inspected from the local PDF. Chapter numbers re-checked against its contents pages on 2026-09-28: all agree. §7.4 (operations preserving convexity) does not treat the perspective, hence the next entry |
| [BT] D. Bertsimas and J. N. Tsitsiklis, *Introduction to Linear Optimization*, Athena Scientific, 1997 | Ch. 6 §6.1 delayed column generation, §6.4 Dantzig-Wolfe (R2); Ch. 7 network flows and the assignment problem (M0); Ch. 9 primal-dual path following (methods/ipm.py); Ch. 10 integer formulations; Ch. 11 §11.2 branch and bound, §11.4 integer programming duality (R2.2); §12.3 the fleet assignment problem (industry precedent) | Inspected from the local PDF, 28 September 2026: contents pages; chapter titles of Ch. 6-12 and the section numbers cited here read from them |
| [PS] C. H. Papadimitriou and K. Steiglitz, *Combinatorial Optimization: Algorithms and Complexity*, Dover, 1998 | Bipartite matching and min-cost flow (M0); total unimodularity of network matrices; branch and bound | Cited. The local file supplied is empty (0 bytes); chapters are cited by topic until a readable copy is inspected |
| S. Boyd and L. Vandenberghe, *Convex Optimization*, Cambridge, 2004 | §3.2.6 perspective of a convex function, for (R3.3) | Cited |

**2. EVRP benchmark and baseline**

| Source | Used for | Status |
| --- | --- | --- |
| [TR] M. Mavrovouniotis et al., benchmark report for the IEEE WCCI-2020 competition on the electric vehicle routing problem, [TR-EVRP-Competition.pdf](https://mavrovouniotis.github.io/EVRPcompetition2020/TR-EVRP-Competition.pdf) | Problem rules (§2), formulation (1)-(10), instance table (§3), evaluation budget (§4) | Inspected, 28 September 2026: §2-§4 |
| M. Mavrovouniotis, C. Menelaou, S. Timotheou, G. Ellinas, C. Panayiotou, M. Polycarpou, "A Benchmark Test Suite for the Electric Capacitated Vehicle Routing Problem," IEEE CEC 2020, pp. 1-8, doi:10.1109/CEC48606.2020.9185753 | Citation requested by the set's README | Cited |
| [evrp-python](https://github.com/NeiH4207/evrp-python), commit `16d3499` | Instance files; GSGA baseline | Inspected: README, `objects/problem.py`, `objects/solution.py`, `evrp.py`, `algorithms/GSGA.py` signatures, `requirements.txt`, LICENSE, E-n22-k4, E-n29-k4-s7, `benchmarks/evrp-2022/README.txt` |
| "A greedy search based evolutionary algorithm for electric vehicle routing problem," Applied Intelligence, doi:10.1007/s10489-022-03555-8 | GSGA as published | Cited |

**3. Formulations and methods**

| Source | Used for | Status |
| --- | --- | --- |
| C. E. Miller, A. W. Tucker, R. A. Zemlin, "Integer programming formulation of traveling salesman problems," J. ACM 7(4), 1960 | Load row (R1.3) | Cited |
| R. W. Floyd, "Algorithm 97: Shortest path," Comm. ACM 5(6), 1962 | Station graph, §4 of Routing | Cited |
| S. Erdoğan and E. Miller-Hooks, "A green vehicle routing problem," Transportation Research Part E 48(1), 2012 | Station copies in the report's formulation | Cited |
| J. Andelmin and E. Bartolini, "An exact algorithm for the green vehicle routing problem," Transportation Science 51(4), 2017 | Non-dominated refueling paths, set partitioning | Cited |
| A. Froger, J. E. Mendoza, O. Jabali, G. Laporte, "Improved formulations and algorithmic components for the electric vehicle routing problem with nonlinear charging functions," Computers & Operations Research 104, 2019 | Recharging-path multigraph; the report's reference [5] | Cited |
| J.-A. Montoya, C. Guéret, J. E. Mendoza, J. G. Villegas, "The electric vehicle routing problem with nonlinear charging function," Transportation Research Part B 103, 2017; instances [VRP-REP 2016-0020](https://www.vrp-rep.org/datasets/item/2016-0020.html) | R4 (deferred) | Cited |
| R. Baldacci, A. Mingozzi, R. Roberti, "New route relaxation and pricing strategies for the vehicle routing problem," Operations Research 59(5), 2011 | ng-route relaxation in R2 | Cited |
| M. S. Roni, Z. Yi, J. G. Smart, "Optimal charging management and infrastructure planning for free-floating shared electric vehicles," Transportation Research Part D 76, 2019; code [idaholab/CMIP](https://github.com/idaholab/CMIP) `348516d` | Precedent for joint charger siting and charging assignment; its disaggregated link x_a <= z_s against M1's aggregated (5), measured in [Models](MODELS.md) §3 | Code inspected 20 October 2026: `Optimization Model.h` (assignment, site link, plug and parking capacity, site-count sweep). Paper cited; it needs licensed CPLEX to run |
| G. Laporte, Y. Nobert and M. Desrochers, "Optimal routing under capacity and distance restrictions," Operations Research 33(5), 1985 | Rounded capacity inequality (R2.3) | Cited |
| R. Fukasawa, H. Longo, J. Lysgaard, M. Poggi de Aragão, M. Reis, E. Uchoa, R. F. Werneck, "Robust branch-and-cut-and-price for the capacitated vehicle routing problem," Mathematical Programming 106(3), 2006 | Cuts in the master that change arc costs only (robust); the entry form of (R2.3) | Cited |
| J. Lysgaard, A. N. Letchford, R. W. Eglese, "A new branch-and-cut algorithm for the capacitated vehicle routing problem," Mathematical Programming 100(2), 2004 | Greedy separation of (R2.3), Routing §5a | Cited |
| Gurobi, [modeling-examples](https://github.com/Gurobi/modeling-examples) `traveling_salesman` and `milk_collection` (local copy of the master branch) | Lazy subtour cuts by callback: the precedent for separating cuts the LP violates rather than writing them all; R2-RCC separates at column-generation convergence instead, since SciPy's HiGHS exposes no callback | Inspected 20 October 2026: notebook prose and the use of lazy constraints |
| M. E. Lübbecke and J. Desrosiers, "Selected topics in column generation," Operations Research 53(6), 2005 | Lagrangian bound (R2.2) during column generation | Cited |
| J. Gondzio, P. González-Brevis, P. Munari, "New developments in the primal-dual column generation technique," European Journal of Operational Research 224(1), 2013 | Early-terminated interior duals; the delta_k rule | Cited |
| P. Munari and J. Gondzio, "Using the primal-dual interior point algorithm within the branch-price-and-cut method," Computers & Operations Research 40(8), 2013 | Interior duals in VRP column generation | Cited |
| M. A. Duran and I. E. Grossmann, "An outer-approximation algorithm for a class of mixed-integer nonlinear programs," Mathematical Programming 36, 1986, [link](https://link.springer.com/article/10.1007/BF02592064) | Outer approximation, Algorithms §6 | Cited |
| P. Bonami, M. Kılınç, J. Linderoth, "Algorithms and software for convex mixed integer nonlinear programs," [preprint](https://optimization-online.org/2009/10/2429/) | Convex MINLP survey | Cited |

**4. Data and software**

| Source | Used for | Status |
| --- | --- | --- |
| [HiGHS v1.12.0](https://github.com/ERGO-Code/HiGHS/tree/v1.12.0), commit `755a8e027a99a8d4ecf153a8dde4b2a767cdf384` | Native solver for the initial Rust libraries | Source pinned as a submodule; C API and MIT licence inspected 23 October 2026; full Python/Rust solver parity pending |
| TransLink static GTFS, snapshot 26SEP_20260925 ([Data](DATA.md) §2) | Transit timetable | Inspected 29 September 2026: all files; counts and checksum recorded |
| [TransLink GTFS Static Data terms](https://www.translink.ca/about-us/doing-business-with-translink/app-developer-resources/gtfs/gtfs-data) | Licence and attribution legend | Inspected 29 September 2026 (search summary of the page) |
| [The Buzzer, May 2019](https://buzzer.translink.ca/2019/05/translinks-four-battery-electric-buses-are-here/); [Daily Hive](https://dailyhive.com/vancouver/translink-electric-battery-bus-route-100) | Route 100 as TransLink's battery-electric pilot, chargers at Marpole Loop and 22nd Street Station, 4-7 minute charges | Inspected 29 September 2026 (search summary) |
| [TransLink bus projects](https://www.translink.ca/plans-and-projects/projects/maintenance-and-upgrade-program/bus-projects) | Industry context | Inspected by the first design session |
| BC Hydro, [Electric Tariff](https://www.bchydro.com/content/dam/BCHydro/customer-portal/documents/corporate/tariff-filings/electric-tariff/bchydro-electric-tariff.pdf), accepted 16 March 2026 (BCUC G-76-25): RS 1640-1643 Overnight Rate, Revision 13, pp. 108-111; RS 1650-1653 Demand Transition Rate, Revision 12, pp. 112-117; RS 1901 Revision 13 and RS 1904 Revision 2, pp. 232-233; all effective 1 April 2026 | Route 100 tariff: energy, demand, the 06:00-22:00 billing window of RS 1640, basic charge, riders ([Data](DATA.md) §3) | Read directly, 29 September 2026. RS 1901 prints "(1.5)%", read as a 1.5% credit |
| BC Hydro, [Fleet electrification rates](https://app.bchydro.com/accounts-billing/rates-energy-use/electricity-rates/fleet-electrification-rates.html) | Eligibility: transit fleets, 150 kW and over | Inspected 29 September 2026 (page summary); the tariff is the value source |
| TransLink, [news release, 27 June 2025](https://www.translink.ca/news/2025/june/translink%20to%20expand%20battery-electric%20bus%20fleet): "TransLink currently has 19 battery-electric buses ... as well as 10 on-route overhead chargers" | Context only: system-wide counts, not placed at Route 100's loops and not tied to this corridor; never used to validate or calibrate M1 (the plug bound of 5 per loop is `illustrative`) | Inspected 29 September 2026 (page summary, sentence quoted verbatim) |
| [The Buzzer, 2 February 2023](https://buzzer.translink.ca/2023/02/translink-begins-new-era-of-bus-electrification/) | Nova LFSe+ on Route 100, 19 buses in early 2024, "over 150 kilometres on a single charge", Route 100 the only route with overhead charging; the 150 km figure enters only the derived 285.8 kWh stress case | Inspected 29 September 2026 (page summary) |
| Nova Bus, LFSe+ Altoona test release (Volvo Group, [September 2022](https://www.volvogroup.com/en/news-and-media/news/2022/sep/nova-bus-successfully-completes-the-altoona-test-for-its-long-range-battery-electric-bus-the-LFSe.html)) | Battery 594 kWh total; 340-470 km | Inspected 29 September 2026 (search summary). Other sources give 564 kWh; TransLink's 150 km is unexplained ([Data](DATA.md) §3) |
| California Air Resources Board, [Battery Electric Truck and Bus Energy Efficiency Compared to Conventional Diesel Vehicles](https://ww2.arb.ca.gov/sites/default/files/2018-11/180124hdbevefficiency.pdf) (2018) | Consumption: Table 2, Altoona 40-ft battery-electric buses, 1.8 kWh/mi (CBD, 12.7 mph), 2.3 kWh/mi (Arterial, 27 mph); charging efficiency: Appendix 1, Foothill Transit 90% | Read directly, 29 September 2026 (pp. 6-7, 18, 24-25). Buses of 2013-2014 |
| [GTFS Schedule reference](https://gtfs.org/documentation/schedule/reference/) | Feed schema, `block_id`, times after midnight | Cited |
| SciPy [`milp`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html), [`highs-ipm`](https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs-ipm.html), [`trust-constr`](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-trustconstr.html) | Reference solvers | Inspected by the first design session; behavior on Python 3.14 checked in Phase 1 |
| [VROOM](https://github.com/VROOM-Project/vroom), [PyVRP](https://github.com/PyVRP/PyVRP) | Interface references only | Inspected by the first design session |
