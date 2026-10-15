"""
Pure-pandas helpers behind the dashboard, kept out of streamlit_app.py so the
README summary script and the tests can use exactly the same numbers.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ROUNDS_PATH = "data/rounds_cleaned.csv"
HOLES_PATH = "data/holes_cleaned.csv"

# Score_vs_Par is derived from Score_Label + Par. ACE is absolute (1 stroke),
# the rest are offsets from par. Labels cap at SEXTUPLE BOGEY; a worse hole
# needs a new entry here.
LABEL_OFFSETS = {
    "EAGLE": -2, "BIRDIE": -1, "PAR": 0,
    "BOGEY": 1, "DOUBLE BOGEY": 2, "TRIPLE BOGEY": 3, "QUADRUPLE BOGEY": 4,
    "QUINTUPLE BOGEY": 5, "SEXTUPLE BOGEY": 6,
}

# Rounds run from 9 to 30 holes, so a raw score vs par isn't comparable across
# rounds: a 9-hole -6 and a 30-hole -6 are very different rounds. Scaling to 18
# holes puts them on one footing.
PER_18 = "Score_per_18"
RAW = "Score_vs_Par"


class DataError(ValueError):
    """The CSVs are inconsistent in a way that would make numbers silently wrong."""


def add_per_18(rounds: pd.DataFrame) -> pd.DataFrame:
    rounds = rounds.copy()
    rounds[PER_18] = rounds[RAW] * 18 / rounds["Holes"]
    if "Round_ID" in rounds.columns:
        rounds["Round_Label"] = round_labels(rounds)
    return rounds


def load_tables(rounds_path: str = ROUNDS_PATH, holes_path: str = HOLES_PATH):
    rounds = pd.read_csv(rounds_path, parse_dates=["Date"])
    holes = pd.read_csv(holes_path, parse_dates=["Date"], dtype={"Hole": str})
    unknown = set(holes["Score_Label"].unique()) - set(LABEL_OFFSETS) - {"ACE"}
    if unknown:
        raise DataError(f"Unknown Score_Label values in {holes_path}: {sorted(unknown)}")
    # The course filter is built from the rounds table, so a hole row naming a course
    # that isn't there would be dropped from every hole-level stat without a trace.
    # That has happened before (a spreadsheet autofill incremented the course name),
    # and the only symptom was a hole count quietly 8 short.
    orphans = sorted(set(holes["Course_Name"]) - set(rounds["Course_Name"]))
    if orphans:
        raise DataError(
            f"{holes_path} has hole rows for courses missing from {rounds_path}: "
            f"{orphans}. These would be silently excluded from every hole-level "
            f"stat — fix the course names before trusting any number here."
        )
    holes["Score_vs_Par"] = holes["Score_Label"].map(LABEL_OFFSETS)
    is_ace = holes["Score_Label"] == "ACE"
    holes.loc[is_ace, "Score_vs_Par"] = 1 - holes.loc[is_ace, "Par"]
    holes["Score_vs_Par"] = holes["Score_vs_Par"].astype(int)
    holes["Strokes"] = holes["Par"] + holes["Score_vs_Par"]
    holes["C1R_bin"] = (holes["C1R"] == "YES").astype(int)
    holes["C2R_bin"] = (holes["C2R"] == "YES").astype(int)
    holes["Fairway_bin"] = (holes["Fairway"] == "YES").astype(int)
    holes["OB_bin"] = (holes["OB"] == "YES").astype(int)
    problems = check_round_totals(rounds, holes)
    if problems:
        shown = "\n".join(f"- {p}" for p in problems[:15])
        more = f"\n- …and {len(problems) - 15} more" if len(problems) > 15 else ""
        raise DataError(
            f"The hole rows don't add up to the round rows, so per-round numbers would be "
            f"wrong. Fix these in {holes_path} / {rounds_path}:\n{shown}{more}"
        )
    holes = holes.sort_values(["Date", "Round_ID", "Hole_Pos"], kind="stable").reset_index(drop=True)
    return add_per_18(rounds), holes


def check_round_totals(rounds: pd.DataFrame, holes: pd.DataFrame) -> list[str]:
    """Every hole belongs to a round, and every round's holes match its hole count and score."""
    for name, df, cols in (("rounds", rounds, ["Round_ID"]), ("holes", holes, ["Round_ID", "Hole_Pos"])):
        missing = [c for c in cols if c not in df.columns]
        if missing:
            return [f"the {name} table has no {', '.join(missing)} column (run tools/backfill_round_ids.py)"]
    problems = []
    if rounds["Round_ID"].isna().any():
        problems.append(f"{int(rounds['Round_ID'].isna().sum())} round rows have no Round_ID")
    dupes = sorted(rounds.loc[rounds["Round_ID"].duplicated(), "Round_ID"].dropna())
    if dupes:
        problems.append(f"Round_ID used by more than one round: {dupes}")
    orphan = sorted(set(holes["Round_ID"].dropna()) - set(rounds["Round_ID"]))
    if orphan:
        problems.append(f"hole rows point at Round_IDs that aren't in the rounds table: {orphan}")
    if holes["Round_ID"].isna().any():
        problems.append(f"{int(holes['Round_ID'].isna().sum())} hole rows have no Round_ID")
    per_round = holes.groupby("Round_ID").agg(n=("Score_vs_Par", "size"), score=("Score_vs_Par", "sum"),
                                              pos_ok=("Hole_Pos", lambda p: sorted(p) == list(range(1, len(p) + 1))))
    for _, r in rounds.dropna(subset=["Round_ID"]).iterrows():
        got = per_round.loc[r["Round_ID"]] if r["Round_ID"] in per_round.index else None
        if got is None:
            problems.append(f"{r['Round_ID']}: no hole rows")
            continue
        if int(got["n"]) != int(r["Holes"]):
            problems.append(f"{r['Round_ID']}: {int(got['n'])} hole rows, round says {int(r['Holes'])} holes")
        if int(got["score"]) != int(r["Score_vs_Par"]):
            problems.append(f"{r['Round_ID']}: holes add up to {int(got['score']):+d}, round says {int(r['Score_vs_Par']):+d}")
        if not got["pos_ok"]:
            problems.append(f"{r['Round_ID']}: Hole_Pos isn't 1..{int(got['n'])}")
    return problems


def round_labels(rounds: pd.DataFrame) -> pd.Series:
    """'Oct 3, 2026 · Fort Tuthill (Breeze 2026) · R2' labels; the R-number only when a course was played twice that day."""
    doubles = rounds.groupby(["Date", "Course_Name"])["Round_ID"].transform("size") > 1
    n = rounds["Round_ID"].astype(str).str.rsplit("_", n=1).str[-1]
    base = (rounds["Date"].dt.strftime("%b ") + rounds["Date"].dt.day.astype(str) + rounds["Date"].dt.strftime(", %Y")
            + " · " + rounds["Course_Name"] + " (" + rounds["Layout"] + ")")
    return base + n.where(doubles).map(lambda x: f" · R{x}" if isinstance(x, str) else "")


# ─── Where my strokes go ──────────────────────────────────────────────────────
# Each event is a hole-level flag. "Missed" events are the absence of a hit.
STROKE_EVENTS = [
    ("OB", "Going OB", "OB_bin", 1),
    ("C1R", "Missing C1R", "C1R_bin", 0),
    ("C2R", "Missing C2R", "C2R_bin", 0),
    ("Fairway", "Missing the fairway", "Fairway_bin", 0),
]


def stroke_costs(holes: pd.DataFrame) -> pd.DataFrame:
    """
    Per event: how much worse holes go when it happens, and how often it happens.
    cost per 18 = (avg hole score when it happened - avg when it didn't) x (rate x 18).
    The events overlap (an OB hole usually misses C1R too), so the costs don't add up.
    """
    rows = []
    total = len(holes)
    for key, name, col, value in STROKE_EVENTS:
        hit = holes[col] == value
        n_yes, n_no = int(hit.sum()), int((~hit).sum())
        avg_yes = holes.loc[hit, "Score_vs_Par"].mean() if n_yes else float("nan")
        avg_no = holes.loc[~hit, "Score_vs_Par"].mean() if n_no else float("nan")
        swing = avg_yes - avg_no
        rate = n_yes / total if total else float("nan")
        rows.append({"Key": key, "Event": name, "Holes_when": n_yes, "Holes_otherwise": n_no,
                     "Avg_when": avg_yes, "Avg_otherwise": avg_no, "Swing": swing,
                     "Rate": rate, "Per_18": rate * 18, "Cost_per_18": swing * rate * 18})
    return pd.DataFrame(rows)


# ─── Course and hole explorer ─────────────────────────────────────────────────
def hole_grid(holes: pd.DataFrame, rounds: pd.DataFrame):
    """
    Holes (rows, by Hole_Pos) x rounds (columns, in date order) of score vs par,
    plus a per-hole summary. Row labels use the Hole label; a label that shows up
    at more than one position gets a dagger so the two rows can't be mistaken
    for one.
    """
    order = rounds.sort_values(["Date", "Round_ID"], kind="stable")["Round_ID"].tolist()
    h = holes[holes["Round_ID"].isin(order)]
    z = h.pivot(index="Hole_Pos", columns="Round_ID", values="Score_vs_Par").reindex(columns=order)
    labels = (h.groupby("Hole_Pos")["Hole"].agg(lambda s: "/".join(dict.fromkeys(s.astype(str))))
              .reindex(z.index))
    dup = labels.duplicated(keep=False)
    labels = labels.where(~dup, labels + "†")
    summary = (
        h.groupby("Hole_Pos")
        .agg(Par=("Par", lambda s: "/".join(str(p) for p in sorted(set(s)))),
             Distance=("Distance", "mean"),
             Rounds=("Score_vs_Par", "size"),
             Avg=("Score_vs_Par", "mean"),
             Birdie_rate=("Score_vs_Par", lambda s: (s < 0).mean()),
             Bogey_rate=("Score_vs_Par", lambda s: (s > 0).mean()),
             OB_rate=("OB_bin", "mean"))
        .reindex(z.index)
    )
    summary.insert(0, "Hole", labels)
    return z, labels, summary.reset_index()


# ─── How sure are we? ─────────────────────────────────────────────────────────
SKILL_STATS = ["Fairway_Pct", "C1R_Pct", "C2R_Pct", "C1X_Pct", "OB_Pct"]


def play_order(rounds: pd.DataFrame) -> pd.DataFrame:
    """Rounds in the order played: by date, then by Round_ID (R1 before R2 on the same day)."""
    return rounds.sort_values(["Date", "Round_ID"], kind="stable").reset_index(drop=True)


def correlation_history(rounds: pd.DataFrame, score: str, stats=SKILL_STATS, min_rounds: int = 8) -> pd.DataFrame:
    """Each stat's correlation with score over the first k rounds, for k = min_rounds..N."""
    r = play_order(rounds)
    rows = []
    for k in range(min_rounds, len(r) + 1):
        head = r.iloc[:k]
        c = head[stats + [score]].corr()[score]
        last = head.iloc[-1]
        for s in stats:
            rows.append({"Round_number": k, "Date": last["Date"], "Round_Label": last.get("Round_Label", ""),
                         "Stat": s, "Correlation": c[s]})
    return pd.DataFrame(rows)


def bootstrap_band(rounds: pd.DataFrame, score: str, stats=SKILL_STATS, n_boot: int = 2000,
                   level: float = 0.80, seed: int = 0) -> pd.DataFrame:
    """Percentile bootstrap interval for each stat's current correlation (resampling whole rounds)."""
    rng = np.random.default_rng(seed)
    y_all = rounds[score].to_numpy(float)
    idx = rng.integers(0, len(rounds), size=(n_boot, len(rounds)))
    lo_q, hi_q = (1 - level) / 2 * 100, (1 + level) / 2 * 100
    rows = []
    for s in stats:
        x = rounds[s].to_numpy(float)[idx]
        y = y_all[idx]
        xc = x - x.mean(axis=1, keepdims=True)
        yc = y - y.mean(axis=1, keepdims=True)
        denom = np.sqrt((xc ** 2).sum(axis=1) * (yc ** 2).sum(axis=1))
        with np.errstate(invalid="ignore", divide="ignore"):
            r = (xc * yc).sum(axis=1) / denom
        r = r[np.isfinite(r)]
        rows.append({"Stat": s, "Correlation": rounds[s].corr(rounds[score]),
                     "Low": np.percentile(r, lo_q) if len(r) else np.nan,
                     "High": np.percentile(r, hi_q) if len(r) else np.nan})
    return pd.DataFrame(rows)
