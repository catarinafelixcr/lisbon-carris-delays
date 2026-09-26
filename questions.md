# Questions

These are the questions this project is trying to answer. They guide everything else: what data I collect, how I model it, and what I build at the end.

This is a living list. As I learn more from the data, some questions will change, get dropped, or turn out to be more interesting than I expected.

---

## The main question

> **How reliable are Carris Metropolitana buses, and can delays be predicted?**

---

## 1. Describe: what happens?

The basics. Before explaining or predicting anything, I need to know what the data actually looks like.

- Which lines and stops have the biggest delays?
- How do delays change through the day and across the week?
- Do delays build up along the route, or do buses catch up?
- How often do buses arrive *early*? (Arguably worse than late: you miss the bus.)
- How many planned trips never happen?

## 2. Explain: why does it happen?

Looking for patterns that could explain the delays.

- Are there differences between the four operators?
- Do school days, holidays or summer change things?
- Does rain make buses later?
- Are busier lines (more passengers) also later?

## 3. Predict: what will happen?

The machine learning part.

- **What will the delay be at a given stop**, knowing the line, the time and the day?
- **If a bus is 5 minutes late at stop 3, how late will it be at stop 15?**

The second one is the most interesting to me. It's a sequence problem, which is where deep learning actually makes sense, and it's the kind of answer that would help someone waiting at a bus stop.

---

## What these questions mean for the data

Almost every question above is about the same thing: **one bus passing one stop**. That's the basic unit of the project, with the delay as the main number to measure.

Around it, I need context to slice the data by:

| To answer questions about... | I need to know the... |
|---|---|
| time of day, day of week | date and time |
| school days, holidays, summer | type of day |
| lines and routes | line and pattern |
| stops and places | stop, with its location |
| operators | operator |
| delays building up | position of the stop along the route |
| rain | weather *(new data source)* |
| busy lines | passengers per day *(from the metrics)* |

This will shape how I model the data later (probably as a star schema).