# 🥏 Disc Golf Performance Analytics

A personal analytics dashboard built on data I collected from my own disc golf rounds. The goal was to use real data analysis techniques to find out what actually drives my scores — and what doesn't.

**Live demo:** [henry-disc-golf-analytics.streamlit.app](https://henry-disc-golf-analytics.streamlit.app/)

## What the data shows so far

After 39 rounds (778 holes) played April 29 – July 15, 2026 across 14 courses:

- **Average round: 6.7 strokes under par** (best round: −15). Hole mix: 44% under par (including 6 eagles and one ace — Bunker #7, 250 ft, July 7), 46% pars, 10% over par — still a low-variance scoring profile where improvement means converting pars to birdies, not eliminating blow-ups.
- **The "strongest predictor" flipped again, as the early data warned it would.** After 6 rounds, C1X putting led (−0.45) and greens in regulation looked irrelevant (−0.10). With 39 rounds it's the reverse: C1R % is the strongest correlate of round score (−0.71), C2R % is right behind (−0.68), and C1X has faded to −0.23.
- **Fairway % went from noise to signal** — +0.09 after 6 rounds, −0.61 now. A live lesson in how unstable small-sample correlations are.
- **Missing the green costs about a full stroke** — holes where I miss C1R average 0.96 strokes worse than holes where I hit it, which is consistent with C1R being the strongest round-level predictor.
- **Distance still matters mostly through C1R, not directly** — longer par-3s correlate only mildly with score (+0.20); the damage runs through the drop in green-hit rate. Par-4 sample is now 175 holes, enough to start trusting its numbers.

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

- ~~Log more rounds (target: 20+) to firm up correlations.~~ Done — 39 rounds and counting.
- Keep building the par-4 sample — 175 holes now vs 590 par-3 holes (par 5s are still rare at 13).
- Add drive-distance and approach-distance tracking per hole.
- Revisit the score model now that the sample is big enough to take the coefficients seriously.
