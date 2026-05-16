# 🥏 Disc Golf Performance Analytics

A personal analytics dashboard built on data I collected from my own disc golf rounds. The goal was to use real data analysis techniques to find out what actually drives my scores — and what doesn't.

**Live demo:** [insert your Streamlit Cloud URL here]

## What the data shows so far

After 6 rounds (108 holes) played April 29 – May 15, 2026 across 6 courses (Bassett Creek, Bunker, Little America, McPherson, RM South, Sweetwater):

- **Average round: 7.7 strokes under par.** Hole mix: 48% birdies, 46% pars, 6% bogeys — a low-variance scoring profile where improvement means converting pars to birdies, not eliminating blow-ups.
- **Putting from Circle 1 (C1X) is currently the strongest predictor of score** — correlation of −0.45 with round score. The early read that "greens in regulation drive everything" has not survived more data: C1R % now sits at −0.10.
- **Fairway % barely moves the needle** (correlation +0.09). I hit fairways consistently regardless of how I score.
- **The "strongest predictor" has already flipped once.** With this few rounds, every correlation is unstable — the dashboard frames them as working hypotheses, not conclusions.
- **Distance still matters mostly through C1R, not directly** — longer par-3s drop my green-hit rate, which is where score loss compounds. Par-4 data is just starting to accumulate (16 holes).

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

- Log more rounds (target: 20+) to firm up correlations.
- Build out par-4 sample size — currently only 16 holes vs 89 par-3 holes.
- Add drive-distance and approach-distance tracking per hole.
- Build a model predicting score from skill stats once the sample is big enough to trust it.
