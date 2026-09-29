# Sources

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
| M. E. Lübbecke and J. Desrosiers, "Selected topics in column generation," Operations Research 53(6), 2005 | Lagrangian bound (R2.2) during column generation | Cited |
| J. Gondzio, P. González-Brevis, P. Munari, "New developments in the primal-dual column generation technique," European Journal of Operational Research 224(1), 2013 | Early-terminated interior duals; the delta_k rule | Cited |
| P. Munari and J. Gondzio, "Using the primal-dual interior point algorithm within the branch-price-and-cut method," Computers & Operations Research 40(8), 2013 | Interior duals in VRP column generation | Cited |
| M. A. Duran and I. E. Grossmann, "An outer-approximation algorithm for a class of mixed-integer nonlinear programs," Mathematical Programming 36, 1986, [link](https://link.springer.com/article/10.1007/BF02592064) | Outer approximation, Algorithms §6 | Cited |
| P. Bonami, M. Kılınç, J. Linderoth, "Algorithms and software for convex mixed integer nonlinear programs," [preprint](https://optimization-online.org/2009/10/2429/) | Convex MINLP survey | Cited |

**4. Data and software**

| Source | Used for | Status |
| --- | --- | --- |
| TransLink static GTFS feed; URL pinned in Phase 6 | Transit timetable | Downloaded and counted by the first design session; URL and checksum not recorded ([Data](DATA.md) §2) |
| [TransLink bus projects](https://www.translink.ca/plans-and-projects/projects/maintenance-and-upgrade-program/bus-projects) | Industry context | Inspected by the first design session |
| [GTFS Schedule reference](https://gtfs.org/documentation/schedule/reference/) | Feed schema, `block_id`, times after midnight | Cited |
| SciPy [`milp`](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html), [`highs-ipm`](https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs-ipm.html), [`trust-constr`](https://docs.scipy.org/doc/scipy/reference/optimize.minimize-trustconstr.html) | Reference solvers | Inspected by the first design session; behavior on Python 3.14 checked in Phase 1 |
| [VROOM](https://github.com/VROOM-Project/vroom), [PyVRP](https://github.com/PyVRP/PyVRP) | Interface references only | Inspected by the first design session |
