"""
The README's "What the data shows" numbers, computed instead of hand-typed.

    python3 tools/summary.py           # print the block
    python3 tools/summary.py --write   # replace the block in README.md
    python3 tools/summary.py --check   # exit 1 if README.md is out of date

Uses the same loader and helpers as the dashboard (analysis.py), with no
filters, so the README always matches the app's default view.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import analysis as a  # noqa: E402

README = ROOT / "README.md"
START, END = "<!-- summary:start -->", "<!-- summary:end -->"
STAT_NAMES = {"Fairway_Pct": "fairway %", "C1R_Pct": "C1R %", "C2R_Pct": "C2R %",
              "C1X_Pct": "C1X putting %", "OB_Pct": "OB rate"}


def _n(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}"


def _date(d) -> str:
    return f"{d:%B} {d.day}"


def summary() -> str:
    rounds, holes = a.load_tables()
    first, last = rounds["Date"].min(), rounds["Date"].max()
    best = rounds.loc[rounds[a.PER_18].idxmin()]
    lengths = rounds["Holes"].value_counts().sort_index()
    other = ", ".join(str(int(n)) for n in lengths.index if n != 18)

    under = (holes["Score_vs_Par"] < 0).mean()
    par = (holes["Score_vs_Par"] == 0).mean()
    over = (holes["Score_vs_Par"] > 0).mean()
    eagles = int((holes["Score_Label"] == "EAGLE").sum())
    aces = holes[holes["Score_Label"] == "ACE"]
    ace_txt = "; ".join(f"{r['Course_Name']} #{r['Hole']}, {int(r['Distance'])} ft, {_date(r['Date'])}"
                        for _, r in aces.iterrows())
    worst = holes.loc[holes["Score_vs_Par"].idxmax()]

    cols = list(STAT_NAMES)
    corr = rounds[cols + [a.PER_18]].corr()[a.PER_18].drop(a.PER_18)
    order = corr.abs().sort_values(ascending=False).index
    corr_txt = ", ".join(f"{STAT_NAMES[c]} {corr[c]:+.2f}" for c in order)

    hist = a.correlation_history(rounds, a.PER_18, cols, 8)
    checkpoints = sorted({8, (8 + len(rounds)) // 2, len(rounds)})
    parts = []
    for k in checkpoints:
        h = hist[hist["Round_number"] == k].set_index("Stat")["Correlation"]
        lead = h.abs().idxmax()
        parts.append(f"after {k} rounds the strongest was {STAT_NAMES[lead]} ({h[lead]:+.2f}), "
                     f"fairway % sat at {h['Fairway_Pct']:+.2f}")
    history_txt = "; ".join(parts)
    band = a.bootstrap_band(rounds, a.PER_18, cols).set_index("Stat")
    top2 = list(order[:2])
    overlap = band.loc[top2[0], "Low"] <= band.loc[top2[1], "High"] and band.loc[top2[1], "Low"] <= band.loc[top2[0], "High"]
    history_txt += (f". The 80% bootstrap bands for {STAT_NAMES[top2[0]]} and {STAT_NAMES[top2[1]]} "
                    f"{'overlap, so the top spot is not settled' if overlap else 'do not overlap'}")

    costs = a.stroke_costs(holes).set_index("Key")
    c1r = costs.loc["C1R"]
    top = costs.sort_values("Cost_per_18", ascending=False)
    short = {"OB": "OB", "C1R": "missed C1R", "C2R": "missed C2R", "Fairway": "missed fairway"}
    cost_txt = ", ".join(f"{short[k]} {_n(r['Cost_per_18'])}" for k, r in top.iterrows())

    p3 = holes[holes["Par"] == 3]
    p3_dist = p3["Distance"].corr(p3["Score_vs_Par"])
    p3_c1r = p3["Distance"].corr(p3["C1R_bin"])
    by_par = holes["Par"].value_counts().sort_index()

    lines = [
        f"{len(rounds)} rounds ({len(holes):,} holes) played {_date(first)} – {_date(last)}, "
        f"{last.year} across {rounds['Course_Name'].nunique()} courses. "
        f"Rounds run from {int(lengths.index.min())} to {int(lengths.index.max())} holes "
        f"({int(lengths.get(18, 0))} are 18 holes; the rest are {other}), "
        f"so **round scores here are per 18 holes** (score vs par × 18 ÷ holes) unless marked raw.",
        "",
        f"- **Average round: {_n(abs(rounds[a.PER_18].mean()))} strokes under par per 18** "
        f"({_n(rounds[a.RAW].mean())} raw). Best round: {_n(best[a.PER_18])} per 18 "
        f"({int(best[a.RAW]):+d} over {int(best['Holes'])} holes at {best['Course_Name']}, {_date(best['Date'])})."
        ,
        f"- **Hole mix:** {under:.0%} under par (including {eagles} eagles and {len(aces)} "
        f"ace{'s' * (len(aces) != 1)}{': ' + ace_txt if len(aces) else ''}), {par:.0%} pars, {over:.0%} over par. "
        f"Worst hole on record: a {worst['Score_Label'].lower()}, {int(worst['Strokes'])} on a "
        f"{int(worst['Distance'])}-ft par {int(worst['Par'])} ({worst['Course_Name']}, {_date(worst['Date'])}).",
        f"- **Round-level correlations with score per 18,** strongest first: {corr_txt}. "
        f"Small samples, so these move as rounds are added: {history_txt}.",
        f"- **Where the strokes go** (cost per 18 versus never making that mistake; these overlap): {cost_txt} strokes.",
        f"- **Missing the green costs about a full stroke:** holes where I miss C1R average "
        f"{c1r['Swing']:.2f} strokes worse than holes where I hit it.",
        f"- **Distance works mostly through C1R:** on par 3s, distance correlates {p3_dist:+.2f} with score "
        f"but {p3_c1r:+.2f} with hitting C1R. Holes by par: "
        + ", ".join(f"{int(n)} par {int(p)}s" for p, n in by_par.items()) + ".",
    ]
    # Typographic minus for negative numbers (not for hyphens inside words or dates).
    return re.sub(r"(?<=[\s(])-(?=\d)", "−", "\n".join(lines))


def main() -> int:
    block = f"{START}\n{summary()}\n{END}"
    if "--write" in sys.argv or "--check" in sys.argv:
        text = README.read_text()
        if START not in text or END not in text:
            print(f"README.md has no {START} … {END} block.")
            return 1
        new = text[:text.index(START)] + block + text[text.index(END) + len(END):]
        if "--check" in sys.argv:
            ok = new == text
            print("README summary is up to date." if ok else "README summary is out of date: run tools/summary.py --write")
            return 0 if ok else 1
        README.write_text(new)
        print("Updated README.md")
        return 0
    print(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
