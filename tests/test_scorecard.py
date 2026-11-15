"""Run from the repo root: uv run --with-requirements requirements.txt --with pytest pytest -q"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import analysis as a  # noqa: E402
from scorecard import _chunk_size, scorecard_html  # noqa: E402

COLORS = {k: "#123456" for k in ("EAGLE", "BIRDIE", "BOGEY", "DOUBLE BOGEY", "TRIPLE BOGEY", "ACE")}


def one_round():
    _, holes = a.load_tables(ROOT / "data" / "rounds_cleaned.csv", ROOT / "data" / "holes_cleaned.csv")
    rid = holes.groupby("Round_ID").size().loc[lambda s: s == 18].index[0]
    return holes[holes["Round_ID"] == rid].copy()


def test_chunk_size_prefers_even_rows():
    assert [_chunk_size(n) for n in (18, 20, 21, 24, 13)] == [9, 10, 7, 8, 9]


def test_eighteen_holes_make_two_tables_with_every_stroke_count():
    holes = one_round()
    out = scorecard_html(holes, COLORS)
    assert out.count("<table") == 2
    cells = re.findall(r"<td style='[^']*' title='[^']*'>(\d+)<div", out)
    assert list(map(int, cells)) == holes.sort_values("Hole_Pos")["Strokes"].tolist()
    assert "†" not in out


def test_repeated_hole_is_marked_and_labels_are_escaped():
    holes = one_round()
    holes.iloc[1, holes.columns.get_loc("Hole")] = holes.iloc[0]["Hole"]
    holes.iloc[2, holes.columns.get_loc("Hole")] = "<b>"
    out = scorecard_html(holes, COLORS)
    assert out.count("<sup>†</sup>") == 2 and "appears more than once" in out
    assert "&lt;b&gt;" in out and "<b>" not in out
