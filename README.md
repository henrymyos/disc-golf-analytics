# 🥏 Disc Golf Performance Analytics

A personal analytics dashboard built on data I collected from my own disc golf rounds. The goal was to use real data analysis techniques to find out what actually drives my scores — and what doesn't.

**Live demo:** [insert your Streamlit Cloud URL here]

## What I learned from the data

After analyzing 5 rounds (90 holes) of self-tracked play:

- **Hitting greens in regulation (C1R) is the single biggest score driver** — correlation of −0.69 with round score.
- **Putting %, surprisingly, has near-zero correlation with my score** once enough rounds are in the dataset (early correlation of −0.48 collapsed to −0.08 after a 5th round). A reminder that small samples lie.
- **Distance matters most through C1R, not directly** — longer par 3s drop my green-hit rate, which then drops my score.
- **I'm a low-variance player** — 47% of holes are birdies, 47% are pars, only 6% are bogeys. Improvement means converting pars to birdies, not fixing blow-up holes.

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

**Rounds:** round-level aggregates (Fairway %, C1R %, putting %, etc.)
**Holes:** hole-level detail (par, distance, fairway hit, C1R hit, OB)

## Running locally

```bash
git clone https://github.com/your-username/disc-golf-analytics.git
cd disc-golf-analytics
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Next steps

- Log more rounds (target: 20+) to firm up correlations
- Add drive-distance and approach-distance tracking per hole
- Build a model predicting score from skill stats
