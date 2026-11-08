"""Pure helpers in tools/round_import.py (no network, no CSV writes)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import round_import as ri  # noqa: E402


@pytest.mark.parametrize("text", [
    "https://www.pdga.com/tour/event/88276",
    "https://www.pdga.com/apps/tournament/live/event?eventId=88276&division=MPO",
    "https://www.pdga.com/tour/results?TournID=88276",
    "  88276 ",
])
def test_event_id_accepts_links_and_numbers(text):
    assert ri.event_id(text) == 88276


@pytest.mark.parametrize("text", ["", "pdga.com/tour/event/", "88276 MPO"])
def test_event_id_rejects_junk(text):
    with pytest.raises(ValueError):
        ri.event_id(text)


def test_short_event_name_drops_year_annual_and_sponsor():
    assert ri._short_event_name("2026 Arizona Open presented by Innova") == "Arizona Open"
    assert ri._short_event_name("5th Annual Ice Bowl powered by MVP") == "Ice Bowl"
    assert ri._short_event_name("Tempe Weekly") == "Tempe Weekly"


def test_round_date_shifts_utc_to_local_within_event_dates():
    r = {"started": "2026-03-08T02:30:00Z", "start_date": "2026-03-07", "end_date": "2026-03-08"}
    assert ri.round_date(r) == "2026-03-07"


def test_round_date_falls_back_when_outside_event_or_missing():
    assert ri.round_date({"started": "2026-03-01T18:00:00Z", "start_date": "2026-03-07"}) == "2026-03-07"
    assert ri.round_date({"end_date": "2026-03-08"}) == "2026-03-08"


def test_is_fairway_par3_needs_circle():
    assert not ri.is_fairway("hit", 3)
    assert ri.is_fairway("c2", 3)
    assert ri.is_fairway("hit", 4)
    assert not ri.is_fairway(None, 4)


def _w(cond, temp, wind, gust, rain):
    return {"Conditions": cond, "Temp_Max_F": temp, "Wind_Mph": wind, "Gust_Max_Mph": gust, "Rain_Mm": rain}


def test_suggest_conditions_picks_nearest_weather():
    past = [_w("Calm", 75, 3, 8, 0), _w("Calm", 78, 4, 9, 0), _w("Windy", 70, 18, 30, 0),
            _w("Windy", 68, 20, 32, 0), _w("Rain", 55, 8, 15, 12)]
    assert ri.suggest_conditions(_w("", 72, 19, 31, 0), past) == "Windy"
    assert ri.suggest_conditions(_w("", 76, 3, 7, 0), past) == "Calm"
    assert ri.suggest_conditions(None, past) is None
    assert ri.suggest_conditions(_w("", 76, 3, 7, 0), []) is None
