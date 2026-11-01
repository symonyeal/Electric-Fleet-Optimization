# Sources

This is the provenance register for the benchmark rules, transit inputs, algorithms, and
charging assumptions used by the live models.

A formulation is validated by the source it implements, not by the solver that
ran it. Cite only what this file records, and add the entry in the change that
uses it. Status is **inspected** (read for this project, with what was read) or
**cited** (known reference, not yet read; read before the work that relies on
it, then update the status).

**1. Textbooks**

| Source | Used for | Status |
| --- | --- | --- |
| R. J. Vanderbei, *Linear Programming: Foundations and Extensions*, 4th ed., Springer, 2014 | Ch. 17-20 central path, path-following method, KKT system, implementation; Ch. 25 convex programming | Inspected from the local PDF. Chapter numbers re-checked against the PDF outline on 2026-09-28: all agree |
| A. Beck, *Introduction to Nonlinear Optimization: Theory, Algorithms, and Applications with MATLAB*, SIAM, 2014 | Ch. 5 Newton's method; Ch. 10-12 optimality conditions, KKT, duality | Inspected from the local PDF. Chapter numbers re-checked against its contents pages on 2026-09-28: all agree. §7.4 (operations preserving convexity) does not treat the perspective, hence the Boyd and Vandenberghe entry |
| [BT] D. Bertsimas and J. N. Tsitsiklis, *Introduction to Linear Optimization*, Athena Scientific, 1997 | Ch. 6 §6.1 delayed column generation (R2); Ch. 9 primal-dual path following; Ch. 11 §11.4 integer programming duality (R2.2) | Inspected from the local PDF, 28 September 2026: contents pages; chapter titles of Ch. 6-12 and the section numbers cited here read from them |
| [PS] C. H. Papadimitriou and K. Steiglitz, *Combinatorial Optimization: Algorithms and Complexity*, Dover, 1998 | Bipartite matching (M0) | Cited. The local file supplied is empty (0 bytes); chapters are cited by topic until a readable copy is inspected |
| H. W. Kuhn, "The Hungarian method for the assignment problem," Naval Research Logistics Quarterly 2(1-2), 1955 | Augmenting paths for the maximum bipartite matching of M0 | Cited |
| S. Boyd and L. Vandenberghe, *Convex Optimization*, Cambridge, 2004 | §3.2.6 perspective of a convex function, for (R3.3) | Cited |

**2. EVRP benchmark and baseline**

| Source | Used for | Status |
| --- | --- | --- |
| [TR] M. Mavrovouniotis et al., benchmark report for the IEEE WCCI-2020 competition on the electric vehicle routing problem, [TR-EVRP-Competition.pdf](https://mavrovouniotis.github.io/EVRPcompetition2020/TR-EVRP-Competition.pdf) | Problem rules (§2), formulation (1)-(10), instance table (§3), evaluation budget (§4) | Inspected, 28 September 2026: §2-§4 |
| M. Mavrovouniotis, C. Menelaou, S. Timotheou, G. Ellinas, C. Panayiotou, M. Polycarpou, "A Benchmark Test Suite for the Electric Capacitated Vehicle Routing Problem," IEEE CEC 2020, pp. 1-8, doi:10.1109/CEC48606.2020.9185753 | Citation requested by the set's README | Cited |
| [evrp-python](https://github.com/NeiH4207/evrp-python), commit `16d3499` | Instance files; GSGA routes (`data/seeds`) | Inspected: README, `objects/problem.py`, `objects/solution.py`, `evrp.py`, `algorithms/GSGA.py` signatures, LICENSE, E-n22-k4, E-n29-k4-s7, `benchmarks/evrp-2022/README.txt` |
| "A greedy search based evolutionary algorithm for electric vehicle routing problem," Applied Intelligence, doi:10.1007/s10489-022-03555-8 | GSGA as published | Cited |

**3. Formulations and methods**

| Source | Used for | Status |
| --- | --- | --- |
| C. E. Miller, A. W. Tucker, R. A. Zemlin, "Integer programming formulation of traveling salesman problems," J. ACM 7(4), 1960 | Load row (R1.3) | Cited |
| R. W. Floyd, "Algorithm 97: Shortest path," Comm. ACM 5(6), 1962 | Station graph, Routing §2 | Cited |
| S. Erdoğan and E. Miller-Hooks, "A green vehicle routing problem," Transportation Research Part E 48(1), 2012 | Station copies in the report's formulation | Cited |
| J. Andelmin and E. Bartolini, "An exact algorithm for the green vehicle routing problem," Transportation Science 51(4), 2017 | Non-dominated refueling paths, set partitioning | Cited |
| A. Froger, J. E. Mendoza, O. Jabali, G. Laporte, "Improved formulations and algorithmic components for the electric vehicle routing problem with nonlinear charging functions," Computers & Operations Research 104, 2019 | Recharging-path multigraph; the report's reference [5] | Cited |
| J.-A. Montoya, C. Guéret, J. E. Mendoza, J. G. Villegas, "The electric vehicle routing problem with nonlinear charging function," Transportation Research Part B 103, 2017; instances [VRP-REP 2016-0020](https://www.vrp-rep.org/datasets/item/2016-0020.html) | Nonlinear charging functions, not modeled (Routing §5) | Cited |
| R. Baldacci, A. Mingozzi, R. Roberti, "New route relaxation and pricing strategies for the vehicle routing problem," Operations Research 59(5), 2011 | ng-route relaxation in R2 | Cited |
| M. S. Roni, Z. Yi, J. G. Smart, "Optimal charging management and infrastructure planning for free-floating shared electric vehicles," Transportation Research Part D 76, 2019; code [idaholab/CMIP](https://github.com/idaholab/CMIP) `348516d` | Precedent for joint charger siting and charging assignment; its disaggregated link x_a <= z_s against M1's aggregated (5), [Models](MODELS.md) §3 | Code inspected 20 October 2026: `Optimization Model.h` (assignment, site link, plug and parking capacity, site-count sweep). Paper cited; it needs licensed CPLEX to run |
| G. Laporte, Y. Nobert and M. Desrochers, "Optimal routing under capacity and distance restrictions," Operations Research 33(5), 1985 | Rounded capacity inequality (R2.3) | Cited |
| R. Fukasawa, H. Longo, J. Lysgaard, M. Poggi de Aragão, M. Reis, E. Uchoa, R. F. Werneck, "Robust branch-and-cut-and-price for the capacitated vehicle routing problem," Mathematical Programming 106(3), 2006 | Cuts in the master that change arc costs only (robust); the entry form of (R2.3) | Cited |
| J. Lysgaard, A. N. Letchford, R. W. Eglese, "A new branch-and-cut algorithm for the capacitated vehicle routing problem," Mathematical Programming 100(2), 2004 | Greedy separation of (R2.3), Routing §4 | Cited |
| M. E. Lübbecke and J. Desrosiers, "Selected topics in column generation," Operations Research 53(6), 2005 | Lagrangian bound (R2.2) during column generation | Cited |
| J. Gondzio, P. González-Brevis, P. Munari, "New developments in the primal-dual column generation technique," European Journal of Operational Research 224(1), 2013 | Early-terminated interior duals, tried and removed (Routing §3) | Cited |
| R. J. Vanderbei, "Symmetric quasidefinite matrices," SIAM Journal on Optimization 5(1), 1995 | An LDL' of a quasi-definite matrix exists for every symmetric permutation, so the order is chosen for fill alone | Cited |
| P. E. Gill, M. A. Saunders, J. R. Shinnerl, "On the stability of Cholesky factorization for symmetric quasidefinite systems," SIAM Journal on Matrix Analysis and Applications 17(1), 1996 | Why the normal equations are preferred for LPs: the error of a quasi-definite LDL' grows as the regularization is approached | Cited |
| S. J. Wright, "Modified Cholesky factorizations in interior-point algorithms for linear programming," SIAM Journal on Optimization 9(4), 1999 | A pivot lost in the normal matrix replaced by a huge value, which drops its component | Cited |
| M. A. Duran and I. E. Grossmann, "An outer-approximation algorithm for a class of mixed-integer nonlinear programs," Mathematical Programming 36, 1986, [link](https://link.springer.com/article/10.1007/BF02592064) | Outer approximation, Algorithms §5 | Cited |
| P. Bonami, M. Kılınç, J. Linderoth, "Algorithms and software for convex mixed integer nonlinear programs," [preprint](https://optimization-online.org/2009/10/2429/) | Convex MINLP survey | Cited |

**4. Data and software**

| Source | Used for | Status |
| --- | --- | --- |
| [faer 0.24.4](https://crates.io/crates/faer) | Sparse LDL' with approximate minimum degree ordering and sign-based dynamic regularization, `crates/efo-kernels/src/ldl.rs` | Source inspected 24 October 2026: `sparse/linalg/cholesky.rs` (symbolic and numeric LDL', `LdltRegularization`, solve) and its tests |
| [HiGHS](https://highs.dev) through the `highs` crate | MILP and LP solves, `crates/efo/src/lp.rs`; the bound is HiGHS's MIP dual bound | Used through its documented interface |
| TransLink static GTFS, snapshot 26SEP_20260925 ([Data](DATA.md) §2) | Transit timetable | Inspected 29 September 2026: all files; counts and checksum recorded |
| [TransLink GTFS Static Data terms](https://www.translink.ca/about-us/doing-business-with-translink/app-developer-resources/gtfs/gtfs-data) | Licence and attribution legend | Inspected 29 September 2026 (search summary of the page) |
| [The Buzzer, May 2019](https://buzzer.translink.ca/2019/05/translinks-four-battery-electric-buses-are-here/); [Daily Hive](https://dailyhive.com/vancouver/translink-electric-battery-bus-route-100) | Route 100 as TransLink's battery-electric pilot, chargers at Marpole Loop and 22nd Street Station, 4-7 minute charges | Inspected 29 September 2026 (search summary) |
| BC Hydro, [Electric Tariff](https://www.bchydro.com/content/dam/BCHydro/customer-portal/documents/corporate/tariff-filings/electric-tariff/bchydro-electric-tariff.pdf), accepted 16 March 2026 (BCUC G-76-25): RS 1640-1643 Overnight Rate, Revision 13, pp. 108-111; RS 1650-1653 Demand Transition Rate, Revision 12, pp. 112-117; RS 1901 Revision 13 and RS 1904 Revision 2, pp. 232-233; all effective 1 April 2026 | Route 100 tariff: energy, demand, the 06:00-22:00 billing window of RS 1640, basic charge, riders ([Data](DATA.md) §3) | Read directly, 29 September 2026. RS 1901 prints "(1.5)%", read as a 1.5% credit |
| TransLink, [news release, 27 June 2025](https://www.translink.ca/news/2025/june/translink%20to%20expand%20battery-electric%20bus%20fleet): "TransLink currently has 19 battery-electric buses ... as well as 10 on-route overhead chargers" | Context only: system-wide counts, not placed at Route 100's loops and not tied to this corridor; never used to validate or calibrate M1 (the plug bound of 5 per loop is `illustrative`) | Inspected 29 September 2026 (page summary, sentence quoted verbatim) |
| [The Buzzer, 2 February 2023](https://buzzer.translink.ca/2023/02/translink-begins-new-era-of-bus-electrification/) | Nova LFSe+ on Route 100, 19 buses in early 2024, "over 150 kilometres on a single charge", Route 100 the only route with overhead charging; the 150 km figure enters only the derived 285.8 kWh stress case | Inspected 29 September 2026 (page summary) |
| Nova Bus, LFSe+ Altoona test release (Volvo Group, [September 2022](https://www.volvogroup.com/en/news-and-media/news/2022/sep/nova-bus-successfully-completes-the-altoona-test-for-its-long-range-battery-electric-bus-the-LFSe.html)) | Battery 594 kWh total; 340-470 km | Inspected 29 September 2026 (search summary). Other sources give 564 kWh; TransLink's 150 km is unexplained ([Data](DATA.md) §3) |
| California Air Resources Board, [Battery Electric Truck and Bus Energy Efficiency Compared to Conventional Diesel Vehicles](https://ww2.arb.ca.gov/sites/default/files/2018-11/180124hdbevefficiency.pdf) (2018) | Consumption: Table 2, Altoona 40-ft battery-electric buses, 1.8 kWh/mi (CBD, 12.7 mph), 2.3 kWh/mi (Arterial, 27 mph); charging efficiency: Appendix 1, Foothill Transit 90% | Read directly, 29 September 2026 (pp. 6-7, 18, 24-25). Buses of 2013-2014 |
| [GTFS Schedule reference](https://gtfs.org/documentation/schedule/reference/) | Feed schema, `block_id`, times after midnight | Cited |
