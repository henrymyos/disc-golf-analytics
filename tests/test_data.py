"""Run from the repo root: uv run --with-requirements requirements.txt --with pytest pytest -q"""
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
