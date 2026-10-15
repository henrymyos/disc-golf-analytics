# 🥏 Disc Golf Performance Analytics

A personal analytics dashboard built on data I collected from my own disc golf rounds. The goal was to use real data analysis techniques to find out what actually drives my scores — and what doesn't.

**Live demo:** [henry-disc-golf-analytics.streamlit.app](https://henry-disc-golf-analytics.streamlit.app/)

## What the data shows so far

These numbers come from `python3 tools/summary.py --write` (the same code as the dashboard, no filters), not typed by hand.

<!-- summary:start -->
63 rounds (1,205 holes) played April 29 – October 11, 2026 across 20 courses. Rounds run from 9 to 30 holes (48 are 18 holes; the rest are 9, 20, 21, 27, 30), so **round scores here are per 18 holes** (score vs par × 18 ÷ holes) unless marked raw.

- **Average round: 5.4 strokes under par per 18** (−5.5 raw). Best round: −17.0 per 18 (−17 over 18 holes at Quailwood, September 26).
- **Hole mix:** 43% under par (including 13 eagles and 2 aces: Bunker #7, 250 ft, July 7; Bunker #6, 320 ft, August 17), 45% pars, 12% over par. Worst hole on record: a sextuple bogey, 9 on a 477-ft par 3 (Champions Landing, July 26).
- **Round-level correlations with score per 18,** strongest first: C2R % −0.86, C1R % −0.84, OB rate +0.80, fairway % −0.73, C1X putting % −0.30. Small samples, so these move as rounds are added.
- **Where the strokes go** (cost per 18 versus never making that mistake; these overlap): missed C1R 10.0, missed C2R 5.8, missed fairway 4.9, OB 1.7 strokes.
- **Missing the green costs about a full stroke:** holes where I miss C1R average 1.04 strokes worse than holes where I hit it.
- **Distance works mostly through C1R:** on par 3s, distance correlates +0.23 with score but −0.30 with hitting C1R. Holes by par: 871 par 3s, 307 par 4s, 27 par 5s.
<!-- summary:end -->

## Data questions for Henry

Things that look off in the data. Nothing here has been changed; scores, labels and stats are exactly as entered.

- **Fort Tuthill, 2026-10-03 (both rounds):** hole "18" appears twice. In play order the round goes 1–17, 18 (par 3, 315 ft), 19 (par 3, 205 ft), then 18 again (par 4, 660 ft). Both are kept as separate holes (`Hole_Pos` 18 and 20) and marked with † in the app. What is the second one (18A/18B)?
- **Kaposia, 2026-07-13:** `Course_Par` is 58 but the hole pars add up to 59. The score (−5) matches the holes.
- **Fairway % doesn't match the hole rows** on 2026-07-24 and 07-26 Champions Landing (0.75 / 0.50 vs 0.72 / 0.44 from the holes), 08-02 and 08-03 Pickard Park (0.556 / 0.421 vs 0.500 / 0.389; 0.421 is 8 of 19) and 08-11 Bunker (0.611 vs 0.667).
- **C2R % on 2026-06-14 Blue Ribbon Pines** is 0.519 (14 of 27) but the hole rows give 0.481 (13 of 27).
- **Conditions** has both "Slight wind" and "Slight Wind", which show up as two options in the Conditions filter.
- Should rounds get a **Round type** column (tournament / casual)? It would make a good filter, but it can't be inferred reliably from Notes.

## Tech stack

- **Python** — data manipulation
- **Pandas** — cleaning, joins, aggregations
- **Plotly** — interactive visualizations
- **Streamlit** — dashboard and deployment

## Repo structure

```
.
├── streamlit_app.py        # The dashboard
├── analysis.py             # Loading, checks and the numbers behind each view (shared with tools/)
├── scorecard.py            # Hole-by-hole scorecard HTML
├── requirements.txt        # Dependencies for deployment
├── data/
│   ├── rounds_cleaned.csv  # One row per round
│   └── holes_cleaned.csv   # One row per hole
├── tools/
│   ├── add_rounds.py       # Local page for pulling rounds from PDGA Live
│   ├── round_import.py     # PDGA Live import + CSV writing
│   ├── summary.py          # Regenerates the README numbers
│   └── backfill_round_ids.py  # One-off that added Round_ID / Hole_Pos
├── tests/test_data.py
└── README.md
```

## Data model

Two tables joined on **`Round_ID`** (`YYYY-MM-DD_<course-slug>_<n>`, where `n` counts rounds at that course that day). Date + course isn't enough: four dates have two rounds at the same course.

**Rounds:** round-level aggregates (holes, par, score vs par, Fairway %, C1R %, C2R %, C1X %, C2 %, scramble %, OB rate, conditions).
**Holes:** hole-level detail (hole label, `Hole_Pos` = order played, par, distance, score label, tee shot, fairway / C1R / C2R / OB).

The app checks on load that every hole belongs to a round and that each round's holes match its hole count and score vs par; if not, it stops with the list of rounds to fix.

## Dashboard sections

Filters (course, layout, conditions, 18-hole rounds only, dates, per-18 / raw score) and the open section live in the URL, so a copied link reopens the same view, e.g. `?course=Quailwood&conditions=Hot&view=strokes`.

- **Overview** — KPIs, score trend (click a point to open that round), score distribution, per-course table and a **scorecard** for any round.
- **Where My Strokes Go** — strokes per 18 lost to OB and missed C1R / C2R / fairway, with hole counts and a "cut X by N%" what-if.
- **What Drives My Score** — round-level correlations with dynamic interpretation, how each correlation moved as rounds were added (with an 80% bootstrap band on today's value), and the per-hole C1R swing.
- **Courses & Holes** — per course and layout: a holes × rounds heatmap, per-hole averages and the three toughest holes.
- **Distance** — par 3 / par 4 toggle, distance-vs-score scatter, binned performance tables, and a written interpretation of each correlation.
- **Shot Type** — tee-shot BH vs FH comparison across avg score, fairway hit rate, C1R rate, and OB rate, with par-class breakdown.
- **Score Model** — scikit-learn linear / ridge regression predicting round score per 18 from skill stats, with leave-one-out CV, coefficient inspection, and a what-if slider for simulating a round.
- **Raw Data** — the underlying rounds and holes tables.

## Adding rounds

Tournament rounds come straight from PDGA Live, which records every hole's score and where each drive and approach finished:

```bash
python3 -m streamlit run tools/add_rounds.py   # or double-click add_rounds.command
```

Paste a PDGA event link and the page pulls each round you played: hole scores, pars and distances, fairway / C1R / C2R / OB per hole, and the round's C1X, C2 and scramble numbers. Conditions are suggested by matching the weather during the round (Open-Meteo) to the past rounds with the most similar weather and copying their label (`data/conditions_weather.csv`). Tap BH or FH for each tee shot (or copy them from the last time you played that layout), save, then **Push to the live dashboard**. Saved rounds get their `Round_ID` and `Hole_Pos` automatically.

A par-3 drive only counts as a fairway hit if it finishes inside C2.

## Running locally

```bash
git clone https://github.com/henrymyos/disc-golf-analytics.git
cd disc-golf-analytics
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Or without installing anything globally: `uv run --with-requirements requirements.txt streamlit run streamlit_app.py`.

Tests: `uv run --with-requirements requirements.txt --with pytest pytest -q`. After adding rounds, refresh the numbers above with `python3 tools/summary.py --write`.

## Next steps

- Keep building the par-4 and par-5 samples (counts are in the summary above).
- Add drive-distance and approach-distance tracking per hole.
- Let students upload their own rounds (CSV template, session-only) for a stats audit.
