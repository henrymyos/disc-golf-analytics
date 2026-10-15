"""
Pure-pandas helpers behind the dashboard, kept out of streamlit_app.py so the
README summary script and the tests can use exactly the same numbers.
"""
from __future__ import annotations

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
    return add_per_18(rounds), holes
