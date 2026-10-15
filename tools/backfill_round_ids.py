"""
One-off: give every round a Round_ID and every hole a Round_ID + Hole_Pos.

    python3 tools/backfill_round_ids.py          # check only, prints the plan
    python3 tools/backfill_round_ids.py --write  # append the columns to both CSVs

Date + Course_Name used to be the join key, but four dates have two rounds at
the same course. Rounds are numbered by their order in rounds_cleaned.csv, and
the hole rows for that date and course are split in the same order by each
round's hole count. Every split is checked (hole count and score sum against the
round row) before anything is written. Existing values are left byte-for-byte:
the new columns are appended to the end of each line.
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import round_import as ri  # noqa: E402


def main(write: bool) -> int:
    with open(ri.ROUNDS_CSV, newline="") as f:
        rounds = list(csv.DictReader(f))
    with open(ri.HOLES_CSV, newline="") as f:
        holes = list(csv.DictReader(f))
    if "Round_ID" in rounds[0] or "Round_ID" in holes[0]:
        print("Round_ID is already there; nothing to do.")
        return 0

    seen: dict[tuple, int] = defaultdict(int)
    round_ids = []
    for r in rounds:
        key = (r["Date"], r["Course_Name"])
        seen[key] += 1
        round_ids.append(ri.make_round_id(r["Date"], r["Course_Name"], seen[key]))

    holes_by_key: dict[tuple, list[int]] = defaultdict(list)
    for i, h in enumerate(holes):
        holes_by_key[(h["Date"], h["Course_Name"])].append(i)

    hole_ids: list[str | None] = [None] * len(holes)
    hole_pos: list[int | None] = [None] * len(holes)
    problems = []
    taken: dict[tuple, int] = defaultdict(int)
    for r, rid in zip(rounds, round_ids):
        key = (r["Date"], r["Course_Name"])
        n = int(r["Holes"])
        idx = holes_by_key[key][taken[key]:taken[key] + n]
        taken[key] += n
        score = sum(ri.hole_score_vs_par(holes[i]) for i in idx)
        if len(idx) != n or score != int(r["Score_vs_Par"]):
            problems.append(f"{rid}: {len(idx)} holes summing to {score:+d}, round row says {n} holes, {int(r['Score_vs_Par']):+d}")
        for pos, i in enumerate(idx, start=1):
            hole_ids[i], hole_pos[i] = rid, pos
        if seen[key] > 1:
            print(f"split {rid}: holes {[holes[i]['Hole'] for i in idx]} -> {score:+d} (round row {int(r['Score_vs_Par']):+d})")
    leftovers = [i for i, x in enumerate(hole_ids) if x is None]
    if leftovers:
        problems.append(f"{len(leftovers)} hole rows match no round (first at data row {leftovers[0] + 2})")
    if problems:
        print("Not writing anything:\n  " + "\n  ".join(problems))
        return 1
    print(f"OK: {len(rounds)} rounds, {len(holes)} holes, every split checks out.")
    if not write:
        print("Dry run. Re-run with --write to append the columns.")
        return 0

    _append_columns(ri.ROUNDS_CSV, ["Round_ID"], [[x] for x in round_ids])
    _append_columns(ri.HOLES_CSV, ["Round_ID", "Hole_Pos"], [[a, str(b)] for a, b in zip(hole_ids, hole_pos)])
    print("Wrote Round_ID to rounds and Round_ID + Hole_Pos to holes.")
    return 0


def _append_columns(path: Path, names: list[str], values: list[list[str]]):
    text = path.read_text()
    lines = text.split("\n")
    trailing = lines and lines[-1] == ""
    if trailing:
        lines = lines[:-1]
    assert len(lines) == len(values) + 1, f"{path}: {len(lines) - 1} data lines vs {len(values)} values"
    out = [lines[0] + "," + ",".join(names)]
    out += [line + "," + ",".join(v) for line, v in zip(lines[1:], values)]
    path.write_text("\n".join(out) + ("\n" if trailing else ""))


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv))
