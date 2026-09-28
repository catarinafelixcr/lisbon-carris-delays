# Data dictionary

This file explains the data behind this project: where it comes from, what each variable means, and what I still haven't figured out.

All the data is open data published by [Carris Metropolitana](https://carrismetropolitana.pt/open-data), the bus network of the Lisbon Metropolitan Area. **This project is independent and not affiliated with them**.

I built this from the [official API docs](https://github.com/carrismetropolitana/api), the [GTFS standard](https://gtfs.org/documentation/schedule/reference/), and by looking at the real data. The docs aren't always up to date, so anything I haven't confirmed is marked as an open question.

*Last updated: 26 September 2026*

---

## The big picture

There are three kinds of data:

| | What it tells you | How far back it goes |
|---|---|---|
| **The plan** | What *should* happen: lines, stops, timetables | Only the current plan |
| **Real time** | What *actually* happened today | Only today. I collect the history myself |
| **Metrics** | Summaries of the past, like passengers per day | Since January 2024 |

The plan and real time together give you delays: when a bus *should* have arrived versus when it *did*.

---

## Words you need to know

These confused me at first, so here they are in plain terms, from biggest to smallest:

| Word | What it is | Example |
|---|---|---|
| **Operator** | One of the 4 companies that run the buses | `LA77N` (also known as 41) |
| **Plan** | A timetable version. Each operator has its own, and they change | `ZN3JG` |
| **Line** | What passengers see on the bus | `1604` |
| **Route** | A variant of a line | `1604_0` |
| **Pattern** | The exact list of stops, in order. Usually one per direction | `1604_0_3` |
| **Trip** | One bus doing one journey at one time | leaves at 06:30 on school weekdays |
| **Service** | The set of days a trip runs on | school weekdays |

---

## Reading the IDs

IDs carry prefixes in square brackets. Once you know what they are, they're easy to read.

**The operator** – every ID starts with it:

| Code | Number | Where the number shows up |
|---|---|---|
| `LA77N` | 41 | metrics (`agency_id`) and buses (`vehicle_id: "41\|1217"`) |
| `BNA17` | 42 | |
| `YA15B` | 43 | |
| `A2L1N` | 44 | |

So bus `41|1217` is bus number 1217 of operator `LA77N`.

**The plan** – trips, services and shapes also have the plan in front. For example:

```
[ZN3JG][YA15B]3001_0_1_0630_0659_0_ESC_DU
  plan  operator  line_route_pattern ... service
```

**Watch out when joining tables:** the same thing can look different depending on where it comes from.

| Source | Pattern looks like |
|---|---|
| GTFS and `/arrivals` | `[LA77N]1604_0_3` |
| `/lines` | `1604_0_3` |

Strip the prefixes (or add them) before joining, or nothing will match.


**the same bus has three different ids depending on where you look:**

| source | bus id |
|---|---|
| docs | `41\|1298` |
| arrivals | `1298` |
| vehicles | `[LA77N]1298` |

---

## 1. Arrivals at a stop (real time)

**URL:** `https://api.carrismetropolitana.pt/v2/arrivals/by_stop/{stop_id}`
**Try it:** [arrivals at Oeiras train station](https://api.carrismetropolitana.pt/v2/arrivals/by_stop/121270)

**One row = one bus passing one stop, today.** This is where delays come from.

| Variable | Type | What it means | Example |
|---|---|---|---|
| `line_id` | text | Line | `1604` |
| `route_id` | text | Route | `[LA77N]1604_0` |
| `pattern_id` | text | Pattern | `[LA77N]1604_0_3` |
| `trip_id` | text | Trip | `1604_0_3_0600_...` |
| `headsign` | text | Destination shown on the bus | `Carcavelos (Estação)` |
| `stop_sequence` | integer | Position of the stop along the pattern | `14` |
| `vehicle_id` | text | Operator number + bus number | `41\|1217` |
| `scheduled_arrival` | time | When it should arrive | `06:11:00` |
| `estimated_arrival` | time | Live prediction | `06:10:50` |
| `observed_arrival` | time | When it actually arrived | `06:10:55` |
| `related_trip_ids` | ? | Not documented | `null` |

Each time also comes as `_unix` (seconds since 1970), which is easier to do maths with.

**There's no delay column.** I work it out:

```
delay = observed_arrival_unix - scheduled_arrival_unix
```

Positive = late. Negative = early.

**update (28 sep):** `observed_arrival` is always empty in practice, so the formula above can't be used. live info (`estimated_arrival`, `trip_id`, `vehicle_id`) only shows up for buses arriving in the next hour or so, and disappears once they pass.

---

## 2. Passengers per line per day (metrics)

**URL:** `https://api.carrismetropolitana.pt/v2/metrics/demand/by_line/{line_id}`
**Try it:** [line 1604](https://api.carrismetropolitana.pt/v2/metrics/demand/by_line/1604)

**One entry = one line on one day, since 1 January 2024.** A ready-made time series.

| Variable | Type | What it means | Example |
|---|---|---|---|
| the date | date | The day | `2024-01-01` |
| `qty` | integer | Card validations that day | `14` |
| `holiday` | code | Public holiday or not | `1` |
| `notes` | text | Name of the holiday or event | `Dia de Ano Novo` |
| `day_type` | code | Type of day (not documented) | `3` |
| `period` | code | Period of the year (not documented) | `2` |

Validations aren't exactly passengers: people who don't tap their card aren't counted.

---

## 3. Trips actually run (metrics)

**URL:** `https://api.carrismetropolitana.pt/v2/metrics/service/all`

**One row = one line on one day, last 14 days only.** Older days disappear, so this needs saving regularly.

| Variable | Type | What it means | Example |
|---|---|---|---|
| `line_id` | **number** (text everywhere else!) | Line | `3001` |
| `agency_id` | text | Operator number | `43` |
| `operational_date` | text | Day, as YYYYMMDD | `20250621` |
| `total_trip_count` | integer | Trips planned | `56` |
| `pass_trip_count` | integer | Trips that passed the check | `56` |
| `pass_trip_percentage` | decimal | Share that passed (0 to 1) | `1` |

---

## 4. The timetable (GTFS)

**URL:** `https://api.carrismetropolitana.pt/v2/gtfs` (downloads a zip)

GTFS is the worldwide standard for public transport timetables. The zip holds text files that work like tables in a database. The version I looked at is valid from 24 September 2026 to 30 June 2027.

**Heads up:** unzipped it's almost 900 MB, and `stop_times.txt` alone has 9 million rows. Don't open it in Excel. Use pandas.

## 5. vehicles (real time)

**url:** `https://api.carrismetropolitana.pt/v2/vehicles`

**one row = one bus in service right now.** around 1000 at 4pm on a weekday.

| variable | what it means | example |
|---|---|---|
| `id` | operator + bus number | `[LA77N]1298` |
| `line_id` | line | `1120` |
| `trip_id` | trip it's doing | `[VNWG3][LA77N]1120_0_2_1630_1659_0_1` |
| `stop_id` | depends on the status (see below) | `120754` |
| `current_status` | where the bus is relative to the stop | `STOPPED_AT` |
| `timestamp` | last position, in **milliseconds** | `1790610054000` |
| `speed` | speed | `1` |
| `lat`, `lon` | position | `38.697754` |
| `occupancy_status`, `occupancy_estimated` | how full the bus is (not in the docs) | |

the status follows the gtfs realtime standard:

| status | meaning | `stop_id` is... |
|---|---|---|
| `IN_TRANSIT_TO` | on the way | the next stop |
| `INCOMING_AT` | about to arrive | the stop it's arriving at |
| `STOPPED_AT` | at the stop | the stop it's at |

a bus might pass a stop without stopping if nobody's waiting, so the safest sign that it passed a stop is when `stop_id` changes.

### What's in the zip

| File | Rows | One row = |
|---|---|---|
| `agency.txt` | 4 | an operator |
| `plans.txt` | 5 | a timetable version, with start and end dates |
| `feed_info.txt` | 1 | info about the file itself |
| `routes.txt` | 941 | a route (709 different lines) |
| `stops.txt` | 12,778 | a stop |
| `trips.txt` | ~276,000 | a trip |
| `stop_times.txt` | ~9,000,000 | a trip at a stop |
| `calendar_dates.txt` | 2,060 | a service on a day |
| `shapes.txt` | ~2,000,000 | a GPS point along a path (for maps) |

### How they connect

```
routes ── route_id ──> trips ── trip_id ──> stop_times <── stop_id ── stops
                         │
                     service_id ──> calendar_dates
```

### The columns that matter most

**`stop_times.txt`** – the heart of it: when each trip should be at each stop.

| Column | What it means |
|---|---|
| `trip_id` | The trip |
| `stop_id` | The stop |
| `stop_sequence` | Order of the stop in the trip |
| `arrival_time` / `departure_time` | Planned time |
| `shape_dist_traveled` | Distance from the start (km) |
| `timepoint` | 1 = exact time, 0 = approximate |

**`trips.txt`**

| Column | What it means |
|---|---|
| `trip_id` | The trip |
| `route_id`, `pattern_id` | Which route and pattern |
| `service_id` | Which days it runs (see `calendar_dates.txt`) |
| `direction_id` | 0 or 1, one for each direction |
| `trip_headsign` | Destination |
| `block_id` | Groups trips done by the same bus in a row |

**`stops.txt`** – conveniently, this already includes the location details.

| Column | What it means |
|---|---|
| `stop_id`, `stop_name` | ID and name |
| `stop_lat`, `stop_lon` | Coordinates |
| `municipality_name`, `parish_name`, `locality_name` | Where it is |
| `lifecycle_status` | `active`, `inactive`, `draft`, `provisional` or `voided` |
| `wheelchair_boarding` | Accessibility |

**`calendar_dates.txt`**

| Column | What it means |
|---|---|
| `service_id` | The service |
| `date` | A day it runs (YYYYMMDD) |
| `exception_type` | Always 1 here, meaning "runs on this day" |

### Things to keep in mind

- **Times can go past midnight.** Some are written as `25:10:00` or even `30:00:00`. That means 01:10 or 06:00 the *next* day, for trips that belong to the previous day's service. There are over 200,000 of these.
- **The plan changes.** Each operator has its own timetable version with an end date. For example, `YA15B` switches to a new plan on 1 October 2026. The GTFS only keeps the current one, so to compare old delays with the right timetable, **I save a copy of the GTFS regularly**.
- **Service names are only readable for one operator.** `YA15B` uses names like `ESC_DU` (school term, weekday), `FER_DU` (holidays, weekday), `VER_DU` (summer, weekday), `F24DEZ` (24 December), and even one-off events like `EV_SUMOL`. The other three operators just use numbers like `7` or `1101`.

---

## Other useful data

Not the main focus, but could help explain patterns later:

- **Schools:** `https://api.carrismetropolitana.pt/v2/facilities/schools`
- **Train, metro, light rail and boat stations:** under `/v2/facilities/`, each with nearby bus stops
- **Service alerts:** `https://api.carrismetropolitana.pt/v2/alerts`
- **Where every bus is right now:** `https://api.carrismetropolitana.pt/v2/vehicles`

---

## Open questions

Things I still need to work out from the data:

- [ ] Why do so many arrivals have no observed time?
- [ ] What is `related_trip_ids`?
- [ ] What do `day_type` and `period` mean? *Hint: probably the same idea as the `YA15B` service names (school term / holidays / summer + weekday / Saturday / Sunday). To check against the calendar.*
- [ ] What counts as a "passed" trip?
- [ ] What do the numeric service codes of the other three operators mean?

---

## Sources

- [Carris Metropolitana open data](https://carrismetropolitana.pt/open-data)
- [API documentation](https://github.com/carrismetropolitana/api)
- [Developer docs](https://docs.carrismetropolitana.pt)
- [Extra datasets](https://github.com/carrismetropolitana/datasets)
- [GTFS reference](https://gtfs.org/documentation/schedule/reference/)