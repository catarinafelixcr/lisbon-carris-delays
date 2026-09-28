# data dictionary

this file explains the data behind this project: where it comes from, what each variable means, and what i still haven't figured out.

all the data is open data published by [carris metropolitana](https://carrismetropolitana.pt/open-data), the bus network of the lisbon metropolitan area. **this project is independent and not affiliated with them.**

i built this from the [official api docs](https://github.com/carrismetropolitana/api), the [gtfs standard](https://gtfs.org/documentation/schedule/reference/), and by looking at the real data. the docs aren't always right, so anything i haven't confirmed is marked as an open question.

*last updated: 28 september 2026*

---

## the big picture

there are three kinds of data:

| | what it tells you | how far back it goes |
|---|---|---|
| **the plan** | what *should* happen: lines, stops, timetables | only the current plan. i save copies |
| **real time** | where every bus is right now | only right now. i collect the history myself |
| **metrics** | summaries of the past, like passengers per day | since january 2024 |

delays come from putting the plan and real time together: when a bus *should* have passed a stop versus when it *did*.

---

## words you need to know

these confused me at first, so here they are in plain terms, from biggest to smallest:

| word | what it is | example |
|---|---|---|
| **operator** | one of the 4 companies that run the buses | `LA77N` (also known as 41) |
| **plan** | a timetable version. each operator has its own, and they change | `ZN3JG` |
| **line** | what passengers see on the bus | `1604` |
| **route** | a variant of a line | `1604_0` |
| **pattern** | the exact list of stops, in order. usually one per direction | `1604_0_3` |
| **trip** | one bus doing one journey at one time | leaves at 06:30 on school weekdays |
| **service** | the set of days a trip runs on | school weekdays |

---

## reading the ids

ids carry prefixes in square brackets. once you know what they are, they're easy to read.

**the operator** – almost every id starts with it:

| code | number | where the number shows up |
|---|---|---|
| `LA77N` | 41 | metrics (`agency_id`) |
| `BNA17` | 42 | |
| `YA15B` | 43 | |
| `A2L1N` | 44 | |

**the plan** – trips, services and shapes also have the plan in front:

```
[ZN3JG][YA15B]3001_0_1_0630_0659_0_ESC_DU
  plan  operator  line_route_pattern ... service
```

**watch out when joining tables:** the same thing looks different depending on where it comes from.

| source | pattern looks like |
|---|---|
| gtfs and `/arrivals` | `[LA77N]1604_0_3` |
| `/vehicles` | `[VNWG3][LA77N]1604_0_3` |
| `/lines` and `/stops` | `1604_0_3` |

| source | bus id looks like |
|---|---|
| docs | `41\|1298` |
| `/arrivals` | `1298` |
| `/vehicles` | `[LA77N]1298` |

strip the prefixes (or add them) before joining, or nothing will match.

---

## 1. vehicles (real time) – the main source

**url:** `https://api.carrismetropolitana.pt/v2/vehicles`

**one row = one bus in service right now.** around 1000 at 4pm on a weekday. this is what i collect every 10 seconds.

| variable | what it means | example |
|---|---|---|
| `id` | operator + bus number | `[LA77N]1298` |
| `agency_id` | operator number | `41` |
| `line_id` | line | `1120` |
| `route_id` | route | `[LA77N]1120_0` |
| `pattern_id` | pattern | `[VNWG3][LA77N]1120_0_2` |
| `trip_id` | trip it's doing | `[VNWG3][LA77N]1120_0_2_1630_1659_0_1` |
| `direction_id` | 0 or 1, one per direction | `1` |
| `stop_id` | depends on the status (see below) | `120754` |
| `current_status` | where the bus is relative to the stop | `STOPPED_AT` |
| `timestamp` | when the bus was there, in **milliseconds** | `1790610054000` |
| `speed` | speed | `1` |
| `bearing` | direction it's facing, in degrees | `268` |
| `lat`, `lon` | position | `38.697754`, `-9.301336` |

the status follows the gtfs realtime standard:

| status | meaning | `stop_id` is... |
|---|---|---|
| `IN_TRANSIT_TO` | on the way | the next stop |
| `INCOMING_AT` | about to arrive | the stop it's arriving at |
| `STOPPED_AT` | at the stop | the stop it's at |

**things i noticed:**

- a bus can pass a stop without stopping if nobody's waiting, so it never shows as `STOPPED_AT` there. the safest sign that it passed a stop is when `stop_id` changes.
- `STOPPED_AT` doesn't always mean stopped. i saw it with speeds of 23 and 29. it probably means "inside the area around the stop".
- positions come in batches: at any moment, `timestamp` only has a few dozen different values for ~1000 buses.
- the api updates every 5-10 seconds, but sometimes a call returns *older* data than the one before (probably different servers).
- when collecting, i also save `collected_at`: when *i* saw the position. `timestamp` is for delays, `collected_at` is for checking the collection.

**watch out:** many columns look full but have the same value for every bus. missing data in disguise:

| column | value for every bus |
|---|---|
| `capacity_seated`, `capacity_standing`, `capacity_total` | `0` |
| `door_status` | `CLOSED` |
| `contactless` | `True` |
| `bikes_allowed` | `False` |
| `occupancy_status` | `NO_DATA_AVAILABLE` (so no occupancy data) |

and these are always empty: `block_id`, `shift_id`, `emission_class`, `license_plate`, `make`, `model`, `owner`, `propulsion`, `registration_date`, `wheelchair_accessible`, `occupancy_estimated`.

---

## 2. the timetable (gtfs)

**url:** `https://api.carrismetropolitana.pt/v2/gtfs` (downloads a zip)

gtfs is the worldwide standard for public transport timetables. the zip holds text files that work like tables in a database. the version i looked at is valid from 24 september 2026 to 30 june 2027.

**heads up:** unzipped it's almost 900 mb, and `stop_times.txt` alone has 9 million rows. don't open it in excel. use pandas.

### what's in the zip

| file | rows | one row = |
|---|---|---|
| `agency.txt` | 4 | an operator |
| `plans.txt` | 5 | a timetable version, with start and end dates |
| `feed_info.txt` | 1 | info about the file itself |
| `routes.txt` | 941 | a route (709 different lines) |
| `stops.txt` | 12,778 | a stop |
| `trips.txt` | ~276,000 | a trip |
| `stop_times.txt` | ~9,000,000 | a trip at a stop |
| `calendar_dates.txt` | 2,060 | a service on a day |
| `shapes.txt` | ~2,000,000 | a gps point along a path (for maps) |

### how they connect

```
routes ── route_id ──> trips ── trip_id ──> stop_times <── stop_id ── stops
                         │
                     service_id ──> calendar_dates
```

### the columns that matter most

**`stop_times.txt`** – the heart of it: when each trip should be at each stop.

| column | what it means |
|---|---|
| `trip_id` | the trip |
| `stop_id` | the stop |
| `stop_sequence` | order of the stop in the trip |
| `arrival_time` / `departure_time` | planned time |
| `shape_dist_traveled` | distance from the start (km) |
| `timepoint` | 1 = exact time, 0 = approximate |

**`trips.txt`**

| column | what it means |
|---|---|
| `trip_id` | the trip |
| `route_id`, `pattern_id` | which route and pattern |
| `service_id` | which days it runs (see `calendar_dates.txt`) |
| `direction_id` | 0 or 1, one for each direction |
| `trip_headsign` | destination |
| `block_id` | groups trips done by the same bus in a row |

**`stops.txt`** – unlike the api, this one has the place names filled in.

| column | what it means |
|---|---|
| `stop_id`, `stop_name` | id and name |
| `stop_lat`, `stop_lon` | coordinates |
| `municipality_name`, `parish_name`, `locality_name` | where it is |
| `lifecycle_status` | `active`, `inactive`, `draft`, `provisional` or `voided` |
| `wheelchair_boarding` | accessibility |

**`calendar_dates.txt`**

| column | what it means |
|---|---|
| `service_id` | the service |
| `date` | a day it runs (yyyymmdd) |
| `exception_type` | always 1 here, meaning "runs on this day" |

### things to keep in mind

- **times can go past midnight.** some are written as `25:10:00` or even `30:00:00`. that means 01:10 or 06:00 the *next* day, for trips that belong to the previous day's service. there are over 200,000 of these.
- **the plan changes.** each operator has its own timetable version with an end date. for example, `YA15B` switches to a new plan on 1 october 2026. the gtfs only keeps the current one, so **i save a copy every week** to compare delays with the right timetable.
- **service names are only readable for one operator.** `YA15B` uses names like `ESC_DU` (school term, weekday), `FER_DU` (holidays, weekday), `VER_DU` (summer, weekday), `F24DEZ` (24 december), and even one-off events like `EV_SUMOL`. the other three operators just use numbers like `7` or `1101`.

---

## 3. stops (api)

**url:** `https://api.carrismetropolitana.pt/v2/stops`

**one row = one stop.** 12,752 of them (the gtfs has 12,778).

| variable | what it means | example |
|---|---|---|
| `id` | stop id. text, with zeros at the start | `010001` |
| `long_name` | name | `ALCOCHETE (R LEITE CUNHA) BIBLIOTECA` |
| `lat`, `lon` | position | `38.753196`, `-8.963687` |
| `district_id`, `municipality_id`, `parish_id`, `locality_id` | where it is, as codes (see section 4) | `15`, `1502`, `150201` |
| `line_ids`, `route_ids`, `pattern_ids` | lists of what passes there | `[4001, 4002]` |

**watch out:**

- all the `*_name` columns (`district_name`, `municipality_name`...) and `short_name` are empty. names come from section 4 or from the gtfs.
- `facilities` is always an empty list, and `wheelchair_boarding` is false for every stop. not believable, so not usable.
- `tts_name` is the same as `long_name`, written for text-to-speech.
- there are 12,752 stops but only 9,169 names: stops on both sides of a road share a name. **always use `id`, never the name.**
- 376 stops have no lines at all.
- `locality_id` is empty for 12.6% of stops and `parish_id` for 5.9%.
- stops are in 3 districts: lisboa (`11`), setúbal (`15`) and 9 in évora (`07`).

---

## 4. places (api)

**urls:** `https://api.carrismetropolitana.pt/v2/locations/districts` and `.../locations/municipalities` (also `parishes` and `localities`)

lookup tables to turn codes into names. careful: these come wrapped in a `data` field, so in pandas it's `requests.get(url).json()["data"]`.

they cover **all of portugal** (29 districts, 308 municipalities), not just where the buses go.

the codes are the official portuguese ones, and they fit inside each other:

| code | level | means |
|---|---|---|
| `15` | district | setúbal |
| `1502` | municipality | district 15, municipality 02 = alcochete |
| `150201` | parish | municipality 1502, parish 01 |

so the first digits of any code already tell you the district and municipality.

there are 308 municipalities but only 307 names (calheta exists in both madeira and the azores), so join by `id`, not by name.

---

## 5. trips actually run (metrics)

**url:** `https://api.carrismetropolitana.pt/v2/metrics/service/all`

**one row = one line on one day, last 14 days only.** older days disappear, so i save it once a day.

| variable | type | what it means | example |
|---|---|---|---|
| `line_id` | **number** (text everywhere else!) | line | `3001` |
| `agency_id` | text | operator number | `43` |
| `operational_date` | text | day, as yyyymmdd | `20250621` |
| `total_trip_count` | integer | trips planned | `56` |
| `pass_trip_count` | integer | trips that passed the check | `56` |
| `pass_trip_percentage` | decimal | share that passed (0 to 1) | `1` |

---

## 6. passengers per line per day (metrics)

**url:** `https://api.carrismetropolitana.pt/v2/metrics/demand/by_line/{line_id}`
**try it:** [line 1604](https://api.carrismetropolitana.pt/v2/metrics/demand/by_line/1604)

**one entry = one line on one day, since 1 january 2024.** a ready-made time series.

| variable | type | what it means | example |
|---|---|---|---|
| the date | date | the day | `2024-01-01` |
| `qty` | integer | card validations that day | `14` |
| `holiday` | code | public holiday or not | `1` |
| `notes` | text | name of the holiday or event | `Dia de Ano Novo` |
| `day_type` | code | type of day (not documented) | `3` |
| `period` | code | period of the year (not documented) | `2` |

validations aren't exactly passengers: people who don't tap their card aren't counted.

---

## 7. arrivals at a stop (not used)

**url:** `https://api.carrismetropolitana.pt/v2/arrivals/by_stop/{stop_id}`
**try it:** [arrivals at oeiras train station](https://api.carrismetropolitana.pt/v2/arrivals/by_stop/121270)

**one row = one bus passing one stop, today.** this was supposed to be where delays came from, but it didn't work out (see below).

| variable | type | what it means | example |
|---|---|---|---|
| `line_id` | text | line | `1604` |
| `route_id` | text | route | `[LA77N]1604_0` |
| `pattern_id` | text | pattern | `[LA77N]1604_0_3` |
| `trip_id` | text | trip | `[VNWG3][LA77N]1523_0_1_1500_1529_0_1` |
| `headsign` | text | destination shown on the bus | `Carcavelos (Estação)` |
| `stop_sequence` | integer | position of the stop along the pattern | `14` |
| `vehicle_id` | text | bus number | `1205` |
| `scheduled_arrival` | time | when it should arrive | `06:11:00` |
| `estimated_arrival` | time | live prediction | `16:12:17` |
| `observed_arrival` | time | when it actually arrived | always empty |
| `related_trip_ids` | ? | not documented | always empty |

each time also comes as `_unix` (seconds since 1970).

the plan was `delay = observed_arrival - scheduled_arrival`, but **`observed_arrival` is always empty.** it works like a departures board: live info (`estimated_arrival`, `trip_id`, `vehicle_id`) only shows up for buses arriving in the next hour or so, and disappears once they pass, without saving when they did. estimates can also be 15+ minutes off when the bus is far away.

so i don't collect this. timetables come from the gtfs, and real times from `/vehicles`.

---

## other useful data

not the main focus, but could help explain patterns later:

- **schools:** `https://api.carrismetropolitana.pt/v2/facilities/schools`
- **train, metro, light rail and boat stations:** under `/v2/facilities/`, each with nearby bus stops
- **service alerts:** `https://api.carrismetropolitana.pt/v2/alerts`

---

## open questions

things i still need to work out from the data:

- [ ] what is `related_trip_ids`?
- [ ] what do `day_type` and `period` mean? *hint: probably the same idea as the `YA15B` service names (school term / holidays / summer + weekday / saturday / sunday). to check against the calendar.*
- [ ] what counts as a "passed" trip?
- [ ] what do the numeric service codes of the other three operators mean?
- [ ] what's the prefix `[VNWG3]`? probably the current plan of `LA77N`, to check in `plans.txt`.

solved:

- [x] ~~what is the `[LA77N]` prefix?~~ the operator. see [reading the ids](#reading-the-ids).
- [x] ~~why do so many arrivals have no observed time?~~ the api doesn't fill it in. using `/vehicles` instead.
- [x] ~~is there occupancy data?~~ no, always `NO_DATA_AVAILABLE`.

---

## sources

- [carris metropolitana open data](https://carrismetropolitana.pt/open-data)
- [api documentation](https://github.com/carrismetropolitana/api)
- [developer docs](https://docs.carrismetropolitana.pt)
- [extra datasets](https://github.com/carrismetropolitana/datasets)
- [gtfs reference](https://gtfs.org/documentation/schedule/reference/)