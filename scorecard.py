"""
HTML scorecard for one round: a hole-by-hole strip, coloured by score with the
stroke count printed in every cell, so colour is never the only signal.
"""
from __future__ import annotations

import html

import pandas as pd

SHOT_SHORT = {"BH": "BH", "FH": "FH", "BH ROLLER": "BHR", "FH ROLLER": "FHR"}


def _chunk_size(n: int) -> int:
    for size in (9, 10, 7, 8):
        if n % size == 0:
            return size
    return 9


def _rel(v: int) -> str:
    return "E" if v == 0 else f"{v:+d}"


def scorecard_html(holes: pd.DataFrame, score_colors: dict[str, str]) -> str:
    """holes: one round's rows in play order (Hole_Pos), with the loader's derived columns."""
    holes = holes.sort_values("Hole_Pos")
    counts = holes["Hole"].value_counts()
    repeated = set(counts[counts > 1].index)
    size = _chunk_size(len(holes))

    cell = "padding:4px 2px;text-align:center;min-width:2.1em;border:1px solid rgba(128,128,128,.25);"
    head = "padding:4px 6px;text-align:left;white-space:nowrap;opacity:.75;font-weight:600;" \
           "border:1px solid rgba(128,128,128,.25);"
    blocks = []
    for start in range(0, len(holes), size):
        part = holes.iloc[start:start + size]

        def row(title: str, cells: list[str]) -> str:
            return f"<tr><th scope='row' style='{head}'>{title}</th>" + "".join(cells) + "</tr>"

        hole_cells, par_cells, dist_cells, score_cells = [], [], [], []
        tee_cells, fw_cells, c1_cells, c2_cells, ob_cells = [], [], [], [], []
        for _, h in part.iterrows():
            label = html.escape(str(h["Hole"]))
            mark = "<sup>†</sup>" if h["Hole"] in repeated else ""
            hole_cells.append(f"<th scope='col' style='{cell}'>{label}{mark}</th>")
            par_cells.append(f"<td style='{cell}'>{int(h['Par'])}</td>")
            dist_cells.append(f"<td style='{cell}font-size:.8em'>{int(h['Distance'])}</td>")
            rel = int(h["Score_vs_Par"])
            name = h["Score_Label"]
            if rel == 0 and name != "ACE":
                style = f"{cell}font-weight:700;"
            else:
                color = score_colors.get(name, "#888")
                style = f"{cell}background:{color};color:#fff;font-weight:700;"
            score_cells.append(
                f"<td style='{style}' title='{html.escape(name.title())}'>{int(h['Strokes'])}"
                f"<div style='font-size:.7em;font-weight:500'>{_rel(rel)}</div></td>"
            )
            tee_cells.append(f"<td style='{cell}font-size:.8em'>{SHOT_SHORT.get(h['Shot_Type'], html.escape(str(h['Shot_Type'])))}</td>")
            for col, out in (("Fairway", fw_cells), ("C1R", c1_cells), ("C2R", c2_cells)):
                hit = h[col] == "YES"
                out.append(f"<td style='{cell}{'' if hit else 'opacity:.45'}'>{'✓' if hit else '✗'}</td>")
            ob = h["OB"] == "YES"
            ob_cells.append(f"<td style='{cell}{'color:#dc4526;font-weight:700' if ob else 'opacity:.45'}'>"
                            f"{'OB' if ob else '–'}</td>")

        blocks.append(
            "<table style='border-collapse:collapse;margin:0 0 .6em 0;font-size:.85em'>"
            + row("Hole", hole_cells) + row("Par", par_cells) + row("Feet", dist_cells)
            + row("Score", score_cells) + row("Tee", tee_cells) + row("Fairway", fw_cells)
            + row("C1R", c1_cells) + row("C2R", c2_cells) + row("OB", ob_cells)
            + "</table>"
        )

    legend_items = [("EAGLE", "Eagle/ace"), ("BIRDIE", "Birdie"), ("BOGEY", "Bogey"),
                    ("DOUBLE BOGEY", "Double"), ("TRIPLE BOGEY", "Triple+")]
    legend = " ".join(
        f"<span style='display:inline-block;width:.9em;height:.9em;background:{score_colors[k]};"
        f"vertical-align:middle;margin:0 .25em 0 .6em'></span>{t}" for k, t in legend_items
    )
    note = ""
    if repeated:
        labels = ", ".join(sorted(repeated, key=lambda x: (len(x), x)))
        note = (f"<div style='font-size:.8em;opacity:.8;margin-top:.3em'>† Hole {html.escape(labels)} appears more "
                f"than once in this round's data. Both are kept, in the order played; "
                f"what they are is a data question for Henry.</div>")
    return (
        "<div style='overflow-x:auto'>" + "".join(blocks) + "</div>"
        f"<div style='font-size:.8em;opacity:.85'>Big number = strokes, small = vs par. "
        f"Par is unshaded.{legend}</div>{note}"
    )
