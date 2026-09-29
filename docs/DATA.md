# Data

This register separates published fleet and benchmark inputs from declared planning
assumptions, so a reader can identify which quantity drives each modeled outcome.

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

Snapshot, pinned in `data/gtfs.py` and verified on every read:

| Field | Value |
| --- | --- |
| URL | https://gtfs-static.translink.ca/gtfs/google_transit.zip |
| Retrieved | 29 September 2026 (Last-Modified 25 September 2026) |
| `feed_version` | 26SEP_20260925, valid 7 September 2026 to 3 January 2027 |
| Size, SHA-256 | 16,146,377 bytes, `d587d4d91ce1cb23c27087c270c9b241adfd5668e19c39cdd823ccf7efdd986d` |
| Contents | 239 routes, 63,023 trips, 1,844,733 stop times; `block_id` present |

The feed is replaced weekly, so a later download will not match; the pinned copy
must be kept. TransLink's terms grant a licence to use, reproduce and redistribute
the data, with the legend "Route and arrival data used in this product or service
is provided by permission of TransLink. TransLink assumes no responsibility for the
accuracy or currency of the Data used in this product or service." The feed itself
is not committed. The derived corridor `tests/fixtures/route100.json` is, and
carries the legend and its source.

Corridor: Route 100 (Marine Drive), Marpole Loop to 22nd Street Station, TransLink's
battery-electric pilot route with overhead chargers at both loops
([Sources](SOURCES.md)). Service day: Wednesday 7 October 2026 (calendar service 1,
no exception). 30 September 2026 and 12 October 2026 run Sunday service. The day
has 219 trips on 23 agency blocks, using four terminal stops, and ends at 26:23.

Observed inputs: trips, stop times, stops, shapes, calendars, and `block_id`.
Every agency connection between consecutive Route 100 trips of a block is feasible
under the deadhead model of M0, so the blocks are a battery-free schedule for these
trips. They also encode driver and depot rules that M0 does not, and a block may
serve other routes; their count is a comparison, not a target.

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

*Route 100 on sourced parameters.* `data/scenarios/route100-rs1640.toml` and
`route100-rs1650.toml` replace every value a primary source supports; the rest stay
`illustrative`. `route100.toml` is unchanged, so every earlier result still reproduces.

| Value | Sourced | Source ([Sources](SOURCES.md) §4) |
| --- | --- | --- |
| Battery B | 594 kWh | Nova Bus, LFSe+ total capacity. Unresolved: other sources give 564 kWh, and TransLink quotes "over 150 km" per charge, which at 594 kWh would mean about 3.8 kWh/km |
| Battery B, `-range` files | 285.8 kWh | Derived: the smallest pack for which TransLink's "over 150 km" holds, 150 km x kappa / (smax - reserve). With 594 kWh a 300 s probe already found a replayed full-day schedule on 16 buses with no on-route charging, which TransLink does not run; the pair brackets the pack |
| Consumption kappa | 1.429 kWh/km | CARB 2018, Altoona Arterial cycle (27 mph). Route 100 averages about 19 mph, between the CBD cycle (1.118 kWh/km) and this one; the higher value is taken |
| Charging efficiency eta | 0.90 | CARB 2018, Foothill Transit's on-route charging over a year of utility bills; Altoona measured 0.76-0.91 |
| Plugs per loop nbar | 5 | TransLink's 10 on-route overhead chargers (June 2025); the even split is an inference |
| Energy, on route | 8.38 or 11.37 c/kWh | BC Hydro RS 1640 or RS 1650 |
| Energy, depot | 8.38 c/kWh | RS 1640 in both files: the depot charges 22:00-06:00, outside RS 1640's demand window, so it bears no demand charge |
| Demand | $13.83 or $2.31 per kW per billing period | RS 1640 (billing demand 06:00-22:00 only) or RS 1650 (whole period), spread over 365/12 days |
| Basic charge | 29.99 c/day per metered site | RS 1640, RS 1650 |
| Riders | -1.5% | RS 1901 "(1.5)%" read as a credit; RS 1904 0% |
| Charger power P, depot location, operating band (s0, reserve, smax), deadhead speed, capital and operating costs | - | Not found; `illustrative` |

Model terms the tariff adds, in `models/fleet.py`, `models/taper.py` and, written separately,
`checks/schedule.py` and `checks/enum_transit.py`: the peak is taken over the slots of
[`peak_from`, `peak_to`) hours of the day only; `rider` multiplies every electricity charge;
`basic` is charged per open site. A scenario without these keys prices as before. Not
modeled: the monthly minimum charge (50% of the highest winter demand charge), the discounts
for primary-voltage metering or customer transformation, and taxes.
