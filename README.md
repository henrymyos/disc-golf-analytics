# 🥏 Disc Golf Performance Analytics

A personal analytics dashboard built on data I collected from my own disc golf rounds. The goal was to use real data analysis techniques to find out what actually drives my scores — and what doesn't.

**Live demo:** [henry-disc-golf-analytics.streamlit.app](https://henry-disc-golf-analytics.streamlit.app/)

## What the data shows so far

After 48 rounds (940 holes) played April 29 – July 26, 2026 across 15 courses:

- **Average round: 5.2 strokes under par** (best round: −15). Hole mix: 41% under par (including 6 eagles and one ace — Bunker #7, 250 ft, July 7), 47% pars, 12% over par. The scoring profile is getting less low-variance — the last stretch of rounds added the first quintuple- and sextuple-bogey territory (a 9 on a 477-ft par 3, thanks to OB).
- **The "strongest predictor" flipped yet again.** After 6 rounds, C1X putting led (−0.45) and greens in regulation looked irrelevant (−0.10). By 39 rounds C1R % led (−0.71). Now C2R % is narrowly on top (−0.81) with C1R % right behind (−0.78), while C1X sits at −0.28. OB % has also emerged as a major correlate (+0.79).
- **Fairway % went from noise to signal** — +0.09 after 6 rounds, −0.66 now. A live lesson in how unstable small-sample correlations are.
- **Missing the green costs about a full stroke** — holes where I miss C1R average 1.03 strokes worse than holes where I hit it, consistent with green-hit rates being the strongest round-level predictors.
- **Distance still matters mostly through C1R, not directly** — longer par-3s correlate only mildly with score (+0.27); the damage runs through the drop in green-hit rate. Par-4 sample is now 233 holes, enough to start trusting its numbers.

## Tech stack

- **Python** — data manipulation
- **Pandas** — cleaning, joins, aggregations
- **Plotly** — interactive visualizations
- **Streamlit** — dashboard and deployment

## Repo structure

```
.
├── streamlit_app.py        # The dashboard
├── requirements.txt        # Dependencies for deployment
├── data/
│   ├── rounds_cleaned.csv  # One row per round
│   └── holes_cleaned.csv   # One row per hole
└── README.md
```

## Data model

Two related tables joined on `Date` + `Course_Name`:

**Rounds:** round-level aggregates (Fairway %, C1R %, C2R %, C1X %, OB %, score vs par).
**Holes:** hole-level detail (par, distance, fairway hit, C1R hit, OB, hole-level score vs par).

## Dashboard tabs

- **Overview** — score trend (inverted axis so better scores plot higher), score distribution, per-course summary.
- **What Drives My Score** — round-level correlations with dynamic interpretation, plus the per-hole swing from hitting vs missing C1R.
- **Distance Analysis** — par 3 / par 4 toggle, distance-vs-score scatter, binned performance tables, and a written interpretation of each correlation.
- **Shot Type** — tee-shot BH vs FH comparison across avg score, fairway hit rate, C1R rate, and OB rate, with par-class breakdown.
- **Score Model** — scikit-learn linear / ridge regression predicting round score from skill stats, with leave-one-out CV, coefficient inspection, and a what-if slider for simulating a round. Calls out the overfitting risk explicitly given the current sample size.
- **Raw Data** — the underlying rounds and holes tables.

## Running locally

```bash
git clone https://github.com/henrymyos/disc-golf-analytics.git
cd disc-golf-analytics
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Next steps

- ~~Log more rounds (target: 20+) to firm up correlations.~~ Done — 48 rounds and counting.
- Keep building the par-4 sample — 233 holes now vs 684 par-3 holes (par 5s are still rare at 23).
- Add drive-distance and approach-distance tracking per hole.
- Revisit the score model now that the sample is big enough to take the coefficients seriously.
