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
