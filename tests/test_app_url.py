"""Shared-link behaviour of the Streamlit app (AppTest runs the script headless, no browser)."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "streamlit_app.py")
FT2 = "2026-10-03_fort-tuthill_2"  # Breeze 2026 has two rounds, so the explorer shows a heatmap


def run(**params):
    at = AppTest.from_file(APP, default_timeout=60)
    for k, v in params.items():
        at.query_params[k] = v
    return at.run()


def test_courses_link_with_round_opens_its_scorecard():
    at = run(view="courses", round=FT2)
    assert not at.exception
    assert at.selectbox(key="explore_course").value == "Fort Tuthill"
    assert at.selectbox(key="explore_layout").value == "Breeze 2026"
    assert any("Fort Tuthill" in m.value and "R2" in m.value for m in at.markdown)
    assert at.query_params["round"] == FT2
    # A rerun from another widget keeps the round open.
    at.run()
    assert at.query_params["round"] == FT2


def test_courses_link_drops_round_after_course_change():
    at = run(view="courses", round=FT2)
    other = next(o for o in at.selectbox(key="explore_course").options if not o.startswith("Fort Tuthill"))
    at.selectbox(key="explore_course").select(other).run()
    assert not at.exception
    assert at.query_params.get("round") != FT2


def test_unknown_round_is_ignored():
    at = run(view="courses", round="nope")
    assert not at.exception
    # The default explorer course has one round, so its own scorecard (not "nope") is what the link holds.
    assert at.query_params.get("round") != "nope"


def _first_round_csvs():
    import pandas as pd
    root = Path(APP).parent
    r = pd.read_csv(root / "data/rounds_cleaned.csv").head(1)
    h = pd.read_csv(root / "data/holes_cleaned.csv", dtype={"Hole": str})
    return r.to_csv(index=False).encode(), h[h["Round_ID"].isin(r["Round_ID"])].to_csv(index=False).encode()


def test_own_rounds_upload_runs_dashboard_on_them_and_bad_files_fall_back():
    rb, hb = _first_round_csvs()
    at = run(view="overview")
    full = at.sidebar.markdown
    at.file_uploader(key="up_rounds").upload("mine.csv", rb, "text/csv")
    at.file_uploader(key="up_holes").upload("mine_holes.csv", hb, "text/csv")
    at.run()
    assert not at.exception
    assert any("Showing your uploaded rounds (1 rounds" in i.value for i in at.info)
    assert any("1 round ·" in m.value for m in at.sidebar.markdown)
    # A holes file that doesn't add up keeps Henry's data and says why.
    at.file_uploader(key="up_holes").upload("mine_holes.csv", hb.replace(b",PAR,", b",BIRDIE,", 1), "text/csv")
    at.run()
    assert not at.exception
    assert any("still Henry's data" in e.value and "mine_holes.csv" in e.value for e in at.error)
    assert [m.value for m in at.sidebar.markdown] == [m.value for m in full]
