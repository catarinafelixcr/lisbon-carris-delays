# Project log

A record of what I did, why I did it, and what I learned along the way. Newest entries at the top.

I'm keeping this because the reasoning behind a decision is easy to forget, and it's often more interesting than the decision itself.

### known limitations
- the data is collected on my own pc, so there will be gaps when it's off or offline. if gaps happen at the same hours often, the data will be biased towards the hours i did collect
- the collection only covers a few weeks or months, so the model won't see things like a full summer or christmas holidays. results only hold for the period collected
- gaps are tracked in `poll_log.csv`, so they can be measured and taken into account

---

## 28 september 2026 - deciding how to collect

### what i measured
- the api has new positions every 5-10 seconds
- sometimes a call returns *older* data than the call before (probably different servers). so i can't assume each call is newer
- a single bus takes 20-40 seconds between stops in town, so calling every 30s would miss stops

### what i found in the columns
used a small `summary()` function on every dataset.
- lots of columns are always empty (make, model, plate...)
- some look full but aren't: capacity is 0 for every bus, wheelchair access is false for every stop. missing data doesn't always look missing
- occupancy is `NO_DATA_AVAILABLE` for every bus, so no occupancy analysis
- the arrivals endpoint isn't needed anymore: timetables come from the gtfs, real times from `/vehicles`

### decisions
- call `/vehicles` every 10 seconds
- only save a position if that bus + timestamp hasn't been saved yet
- save `collected_at` too, to know when the collection wasn't running
- keep all columns in the raw data, pick the useful ones later
- run it on my pc for now. gaps will be checked later with the poll log
- also save the gtfs once a week and the trips run once a day
- work in layers: raw -> clean (one row per bus passing a stop) -> star schema

### next steps
- [ ] run the collection and check the first files
- [ ] write the notebook that turns positions into stop arrivals

## 28 september 2026 - the api doesn't record real arrival times

### what happened
called the arrivals endpoint for oeiras station twice, two minutes apart.

- `observed_arrival` was empty for every single row (202 of 202)
- only buses coming in the next hour or so had live info
- buses that passed between the two calls just disappeared. no observed time was saved
- some estimates were 15+ min off when the bus was far away, and got better as it got closer

so the arrivals endpoint works like a departures board: it shows what's coming, but nobody writes down when the bus actually passed.

### what this means
the original plan (delay = observed - scheduled) doesn't work. i need to record the real times myself.

### new plan
use the `/vehicles` endpoint. it gives every bus in service, its current stop and its status (in transit, incoming, stopped), in one call. checking it every 20-30 seconds and noting when each bus changes stop should give the real arrival times.

this also means github actions won't work for collecting (it can't run that often). i'll need a machine that's always on.

### next steps
- [ ] follow one bus for a few minutes to check the idea works
- [ ] decide where to run the collection

## 26 September 2026 - getting started

### Choosing the topic

**What:** Picked bus delays in the Lisbon Metropolitan Area as the topic.

**Why:** I wanted a time series project with real data that could be very useful for companies and, above all, for people! As a public transport user outside Lisbon, I can track some buses using the Coimbra SMTUC app, but having arrival predictions would be very useful and could help understand delays patterns!

### Exploring before collecting

**What:** Looked at the raw API responses in the browser before writing any collection code.

**Why:** I didn't want to build a data pipeline around assumptions. Better to see what the data actually looks like first.

**What I found:**

- There's an endpoint that gives, for each stop, both the planned and the actual arrival time of every bus. That means delays can be calculated directly.
- Many arrivals have no actual arrival time. Still don't know why.
- IDs have a strange prefix like `[LA77N]` that doesn't appear everywhere.
- The metrics include daily passenger numbers per line since January 2024. An unexpected bonus: a ready-made time series.

### Writing a data dictionary

**What:** Created [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md) with every variable, what it means, and what's still unclear.

**Why:** To understand the structure before using the data, and to have one place to check when I forget what something means. It also made clear that the official docs aren't always accurate.

### Downloading the timetable (GTFS)

**What:** Downloaded the full timetable file and looked at its structure.

**What I found:**

- It's big: almost 900 MB unzipped, with 9 million rows in `stop_times.txt`.
- **The `[LA77N]` mystery is solved:** it's the operator code. The four operators are also known by numbers (41 to 44), which show up in the metrics and bus IDs.
- **Timetables change.** Each operator has its own plan with an end date, and one of them switches on 1 October. Since the GTFS only keeps the current plan, I'll need to save copies over time.
- One operator names its services in a readable way (`ESC_DU` = school term weekday). The other three just use numbers.

### Defining the questions

**What:** Wrote [`QUESTIONS.md`](QUESTIONS.md) with the main question and the smaller ones behind it.

**Why:** I was about to jump into a notebook and started thinking about a star schema. But the schema depends on what I want to answer, so the questions had to come first.

**Main question:** How reliable are Carris Metropolitana buses, and can delays be predicted?

### Next steps

- [ ] Investigate the missing arrival times in a notebook
- [ ] Adjust and start the data collection (arrivals, weekly GTFS copy, trips run)
- [ ] Explore the passenger data while the delay data builds up

---

<!--
Template for new entries:

## DD Month YYYY – Short title

### What I did
**What:**
**Why:**
**What I found:**

### Next steps
- [ ]
-->