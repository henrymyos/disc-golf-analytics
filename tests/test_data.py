"""Run from the repo root: uv run --with-requirements requirements.txt --with pytest pytest -q"""
import io
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
os.chdir(ROOT)

import analysis as a  # noqa: E402
import round_import as ri  # noqa: E402


@pytest.fixture(scope="module")
def tables():
    return a.load_tables()


def test_per_18(tables):
    rounds, _ = tables
    drift = rounds[(rounds["Course_Name"] == "Driftless 9") & (rounds["Date"] == "2026-08-09")].iloc[0]
    assert drift["Score_vs_Par"] == -3 and drift["Score_per_18"] == -6.0
    assert round(rounds["Score_vs_Par"].mean(), 1) == -5.5
    assert rounds["Score_vs_Par"].min() == -17


def test_round_ids(tables):
    rounds, holes = tables
    assert rounds["Round_ID"].is_unique
    assert set(holes["Round_ID"]) <= set(rounds["Round_ID"])
    assert a.check_round_totals(rounds, holes) == []
    ft = rounds[rounds["Round_ID"].str.startswith("2026-10-03_fort-tuthill")].set_index("Round_ID")
    assert ft["Score_vs_Par"].to_dict() == {"2026-10-03_fort-tuthill_1": -9, "2026-10-03_fort-tuthill_2": -8}
    for rid in ft.index:
        h = holes[holes["Round_ID"] == rid]
        assert list(h["Hole"]).count("18") == 2 and len(h) == 20


def test_load_check_catches_mismatch(tables):
    rounds, holes = tables
    bad = holes.copy()
    bad.loc[bad.index[0], "Score_vs_Par"] += 1
    assert any("add up" in p for p in a.check_round_totals(rounds, bad))
    assert any("hole rows" in p for p in a.check_round_totals(rounds, holes.iloc[1:]))


def test_import_writes_ids():
    assert ri.make_round_id("2026-10-03", "Fort Tuthill", 2) == "2026-10-03_fort-tuthill_2"
    assert ri.next_round_id("2026-10-03", "Fort Tuthill") == "2026-10-03_fort-tuthill_3"
    assert ri.next_round_id("2030-01-01", "Fort Tuthill") == "2030-01-01_fort-tuthill_1"
    r = {"started": None, "start_date": "2030-01-01", "end_date": "2030-01-01", "par": 6, "stats": {},
         "holes": [{"hole": 1, "par": 3, "length": 300, "score": 2, "driving": "c1", "green": "c1", "ob": 0},
                   {"hole": 2, "par": 3, "length": 300, "score": 4, "driving": "hit", "green": None, "ob": 1}]}
    rnd, holes = ri.build_rows(r, "Fort Tuthill", "Test", ["BH", "FH"], "Perfect", "")
    assert rnd["Round_ID"] == "2030-01-01_fort-tuthill_1"
    assert [h["Hole_Pos"] for h in holes] == [1, 2] and {h["Round_ID"] for h in holes} == {rnd["Round_ID"]}
    assert sum(ri.hole_score_vs_par(h) for h in holes) == rnd["Score_vs_Par"]


def test_stroke_costs_match_info_box(tables):
    _, holes = tables
    c = a.stroke_costs(holes).set_index("Key")
    swing = (holes.loc[holes["C1R"] == "NO", "Score_vs_Par"].mean()
             - holes.loc[holes["C1R"] == "YES", "Score_vs_Par"].mean())
    assert abs(c.loc["C1R", "Swing"] - swing) < 1e-12 and round(swing, 2) == 1.04
    assert (c["Holes_when"] + c["Holes_otherwise"] == len(holes)).all()
    ob = c.loc["OB"]
    assert abs(ob["Cost_per_18"] - ob["Swing"] * ob["Holes_when"] / len(holes) * 18) < 1e-12


def test_hole_grid_keeps_both_fort_tuthill_18s(tables):
    rounds, holes = tables
    z, labels, per_hole = a.hole_grid(holes, rounds[rounds["Course_Name"] == "Fort Tuthill"])
    assert z.shape == (20, 2)
    assert list(labels).count("18†") == 2
    q = rounds[rounds["Course_Name"] == "Quailwood"]
    assert a.hole_grid(holes, q)[0].shape[1] == 3


def test_readme_summary_is_current():
    import subprocess
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "summary.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_correlation_history_ends_at_current(tables):
    rounds, _ = tables
    hist = a.correlation_history(rounds, a.PER_18)
    assert hist["Round_number"].min() == 8 and hist["Round_number"].max() == len(rounds)
    last = hist[hist["Round_number"] == len(rounds)].set_index("Stat")["Correlation"]
    now = rounds[a.SKILL_STATS + [a.PER_18]].corr()[a.PER_18].drop(a.PER_18)
    assert (last - now).abs().max() < 1e-12
    band = a.bootstrap_band(rounds, a.PER_18).set_index("Stat")
    assert ((band["Low"] <= band["Correlation"]) & (band["Correlation"] <= band["High"])).all()


def test_conditions_merge_case_variants(tables):
    rounds, _ = tables
    conds = rounds["Conditions"].dropna()
    assert conds.str.lower().nunique() == conds.nunique()
    assert "Slight Wind" not in set(conds) and (conds == "Slight wind").sum() == 13


def _template_files(drop_col=None, label=None, blank_conditions=False):
    """My first round as in-memory uploads, like the dashboard's 'Use your own rounds' templates."""
    r = pd.read_csv(a.ROUNDS_PATH).head(1)
    h = pd.read_csv(a.HOLES_PATH, dtype={"Hole": str})
    h = h[h["Round_ID"].isin(r["Round_ID"])]
    if blank_conditions:
        r[["Conditions", "Layout"]] = None
    if drop_col:
        h = h.drop(columns=drop_col)
    if label:
        h.loc[h.index[0], "Score_Label"] = label
    files = []
    for df, name in ((r, "my_rounds.csv"), (h, "my_holes.csv")):
        f = io.BytesIO(df.to_csv(index=False).encode())
        f.name = name
        files.append(f)
    return files


def test_load_tables_from_uploaded_files():
    rounds, holes = a.load_tables(*_template_files())
    assert len(rounds) == 1 and len(holes) == int(rounds["Holes"].iloc[0])
    assert holes["Strokes"].sum() == rounds["Course_Par"].iloc[0] + rounds["Score_vs_Par"].iloc[0]


def test_uploaded_files_with_problems_name_the_file():
    with pytest.raises(a.DataError, match="my_holes.csv is missing column.*C1R"):
        a.load_tables(*_template_files(drop_col="C1R"))
    with pytest.raises(a.DataError, match="Unknown Score_Label values in my_holes.csv"):
        a.load_tables(*_template_files(label="ALBATROSS"))


def test_uploaded_rounds_with_blank_conditions_load():
    # An all-blank Conditions column reads as float NaN; it used to crash on .str.lower().
    rounds, _ = a.load_tables(*_template_files(blank_conditions=True))
    assert rounds["Conditions"].isna().all() and (rounds["Layout"] == "Default").all()


def test_uploaded_flags_and_labels_are_case_insensitive():
    clean = a.load_tables(*_template_files())[1]
    r, h = _template_files()
    df = pd.read_csv(h, dtype={"Hole": str})
    for c in ("Score_Label", "Fairway", "C1R", "C2R", "OB"):
        df[c] = df[c].str.title() + " "
    h = io.BytesIO(df.to_csv(index=False).encode())
    h.name = "my_holes.csv"
    messy = a.load_tables(r, h)[1]
    pd.testing.assert_frame_equal(messy, clean)
    assert clean["C1R_bin"].sum() > 0  # the round has made putts, so a lowercase "yes" can't hide as 0


def test_uploaded_headers_with_stray_spaces_load():
    clean = a.load_tables(*_template_files())
    r, h = _template_files()
    r = io.BytesIO(r.getvalue().replace(b"Date,", b"Date ,", 1)); r.name = "my_rounds.csv"
    h = io.BytesIO(h.getvalue().replace(b",C1R,", b", C1R,", 1)); h.name = "my_holes.csv"
    messy = a.load_tables(r, h)
    pd.testing.assert_frame_equal(messy[0], clean[0])
    pd.testing.assert_frame_equal(messy[1], clean[1])


def test_uploaded_course_names_and_round_ids_ignore_stray_spaces():
    clean = a.load_tables(*_template_files())
    r, h = _template_files()
    dr, dh = pd.read_csv(r), pd.read_csv(h, dtype={"Hole": str})
    dh["Course_Name"] = dh["Course_Name"] + " "
    dr["Round_ID"] = " " + dr["Round_ID"]
    r = io.BytesIO(dr.to_csv(index=False).encode()); r.name = "my_rounds.csv"
    h = io.BytesIO(dh.to_csv(index=False).encode()); h.name = "my_holes.csv"
    messy = a.load_tables(r, h)
    pd.testing.assert_frame_equal(messy[0], clean[0])
    pd.testing.assert_frame_equal(messy[1], clean[1])
