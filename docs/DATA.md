# Data

Observed inputs and declared assumptions are kept apart. Every instance carries a
manifest: source URL, retrieval date, revision or version, SHA-256, and the
transformations applied. No checksum is recorded in this design; Phase 1 records
the EVRP files and Phase 6 the GTFS feed.

**1. EVRP benchmark**

Source: the competition set of Mavrovouniotis, Menelaou, Timotheou, Ellinas,
Panayiotou and Polycarpou (CEC 2020), in the copy distributed by evrp-python.
Files are fetched from the pinned commit
`16d3499799ab7aa7bc3f11a5eaf8604947389462` (8 August 2024), never from a branch.

| Set | Directory | Instances | Published values |
| --- | --- | --- | --- |
| 2019 | `benchmarks/evrp-2019` | 17: seven E (21-100 customers), ten X (142-1000) | Report Table 1 upper bounds for the E set; evrp-python's VNS/SA/GSGA table for all |
| 2022 | `benchmarks/evrp-2022` | 24, station count in the name (e.g. E-n29-k4-s7) | OPTIMAL_VALUE as integers; convention unknown |

The E set of the 2019 benchmark, from the report's Table 1 and evrp-python's
README (best over its three heuristics). Neither column is verified here.

| Instance | n | stations | min routes | C | Q | h | Report UB | evrp-python best |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| E-n22-k4 | 21 | 8 | 4 | 6000 | 94 | 1.2 | 384.67 | 384.67 |
| E-n23-k3 | 22 | 9 | 3 | 4500 | 190 | 1.2 | 573.13 | 571.94 |
| E-n30-k3 | 29 | 6 | 4 | 4500 | 178 | 1.2 | 511.25 | 509.47 |
| E-n33-k4 | 32 | 6 | 4 | 8000 | 209 | 1.2 | 869.89 | 840.14 |
| E-n51-k5 | 50 | 5 | 5 | 160 | 105 | 1.2 | 570.17 | 529.90 |
| E-n76-k7 | 75 | 7 | 7 | 220 | 98 | 1.2 | 723.36 | 692.64 |
| E-n101-k8 | 100 | 9 | 8 | 200 | 103 | 1.2 | 899.88 | 839.29 |

If evrp-python's solutions replay as feasible for the report's rules, six of the
seven report values are not optimal. The two rule sets admit the same routes
([Routing](ROUTING.md) §1), so the conclusion does not depend on the fleet
convention. It does depend on the replay.

File format, as read in E-n22-k4 and E-n29-k4-s7:

- DIMENSION counts all nodes: 30 for E-n22-k4, which has 1 depot, 21 customers,
  and 8 stations. The report's §3 describes it as "the number of customers
  including the central depot"; the files govern.
- NODE_COORD_SECTION lists every node, stations included. DEMAND_SECTION lists
  the depot, with demand 0, and the customers. STATIONS_COORD_SECTION lists
  station identifiers only. DEPOT_SECTION ends with -1.
- The 2019 header uses `Name:` and `EDGE_WEIGHT_FORMAT`; the 2022 header uses
  `NAME:` and `EDGE_WEIGHT_TYPE`.

The reader parses by keyword, checks every count against the sections it read,
and rejects any other edge-weight type. evrp-python's reader uses fixed line
offsets; the project does not copy it.

Terms: the set's README asks for a citation of the CEC 2020 paper and states no
license; evrp-python's MIT license covers its code. Until redistribution terms
are confirmed, the files are fetched by pinned URL and checked against recorded
SHA-256 values rather than committed. Unit tests use self-made fixtures;
benchmark tests skip with a stated reason when the files are absent.

**2. TransLink GTFS**

A prior design session downloaded TransLink's public static GTFS feed and
reported a 16.1 MB archive with 239 routes and 63,023 trip records across its
service calendars. That session recorded neither URL nor checksum, and this
session has not re-verified the counts. Phase 6 pins the URL, retrieval date,
`feed_info.txt` version if present, SHA-256, and TransLink's terms of use. The
feed is not committed; a small derived corridor fixture is, if the terms permit.

Observed inputs: trips, stop times, stops, shapes, calendars, and `block_id` if
present. Where the feed assigns blocks, the agency's own blocks are a feasible
battery-free schedule for the same trips, hence an upper bound on the M0 fleet.
Their absence is recorded, not imputed.

Horizon selection keeps every trip of the chosen service day, including trips
after midnight, as [Models](MODELS.md) §1 requires.

**3. Declared engineering scenarios**

Neither dataset contains battery, charger, grid, tariff, or cost data. These are
scenario files: one TOML table per scenario, every value with its unit and a
source field that is either a citation recorded in [Sources](SOURCES.md) or the
word `illustrative`.

| Parameter | Used by | Unit |
| --- | --- | --- |
| Battery capacity B, reserve r, operating ceiling s_max | M1-M4 | kWh; fraction |
| Energy per km and per hour | M1-M4 | kWh/km; kWh/h |
| Charger power P, efficiency eta, loss alpha, stress gamma | M1-M3, R3 | kW; 1; 1/kW; currency/(kW^2 h) |
| Grid capacity, upgrade limits, base load | M1-M2 | kW |
| Energy price, peak price, capital costs | M1-M4, R3 | currency per unit and horizon |
| Speed v, service times sigma, duration limit T | R3 | distance unit/h; h; h |

Results computed from `illustrative` values are reported as sensitivity, never as
a recommendation ([Design](DESIGN.md) §7).
