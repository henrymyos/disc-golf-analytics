"""
Add Rounds — a local page for getting new rounds into the dashboard's CSVs.

    python3 -m streamlit run tools/add_rounds.py

Paste a PDGA event link: every round you played in it is pulled from PDGA Live
(scores, pars, distances, fairway / C1R / C2R / OB per hole, putting and
scramble), conditions are suggested from the weather during the round, and
you tap BH or FH for each tee shot. Saving appends the rows to the CSVs;
"Push" commits them so the live dashboard picks them up.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import round_import as ri  # noqa: E402

REPO = ri.DATA.parent
SHOT_LABELS = {"BH": "BH", "FH": "FH", "BH ROLLER": "BHR", "FH ROLLER": "FHR"}

st.set_page_config(page_title="Add rounds", page_icon="🥏", layout="wide")
st.title("🥏 Add rounds")
if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))


def pending() -> list[dict]:
    return ri.load_json(ri.PENDING, [])


def save_pending(rs: list[dict]):
    ri.save_json(ri.PENDING, rs)


def known_conditions() -> list[str]:
    labels = {p["Conditions"] for p in ri.past_conditions()}
    with open(ri.ROUNDS_CSV, newline="") as f:
        labels |= {r["Conditions"].strip() for r in csv.DictReader(f) if r["Conditions"].strip()}
    return sorted(labels, key=str.lower)


# ─── Fetch from PDGA Live ─────────────────────────────────────────────────────
with st.form("fetch", border=False):
    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
    link = c1.text_input("PDGA event link or number", placeholder="https://www.pdga.com/tour/event/106640")
    go = c2.form_submit_button("Get my rounds", use_container_width=True)
if go and link.strip():
    try:
        with st.spinner("Reading PDGA Live…"):
            found = ri.fetch_event(link)
            rs = pending()
            have = {r["id"] for r in rs}
            added, skipped = 0, 0
            for r in found:
                if r["id"] in have or ri.already_logged(r):
                    skipped += 1
                    continue
                try:
                    r["weather"] = ri.round_weather(r)
                except Exception:
                    r["weather"] = None
                r["suggested"] = ri.suggest_conditions(r["weather"])
                r["notes"] = ri._short_event_name(r["event"])
                r["shots"] = [None] * len(r["holes"])
                rs.append(r)
                added += 1
            save_pending(rs)
        if not found:
            st.warning("You don't have any finished rounds in that event (PDGA #%d)." % ri.PDGA_NUM)
        else:
            st.success(f"Added {added} round{'s' * (added != 1)}" + (f", skipped {skipped} already logged or waiting below." if skipped else "."))
    except Exception as e:  # network, bad link, PDGA changed its API
        st.error(f"Couldn't read that event: {e}")

st.caption("Casual rounds aren't on PDGA Live, so for now those still go in by hand.")

# ─── Rounds waiting for shot types ────────────────────────────────────────────
rs = sorted(pending(), key=lambda r: (ri.round_date(r), r["round"]))
names = ri.load_json(ri.COURSE_NAMES, {})
conditions = known_conditions()

if not rs:
    st.info("Nothing waiting. Paste an event link above to pull in its rounds.")


def set_shot(rid: int, i: int):
    all_rs = pending()
    for r in all_rs:
        if r["id"] == rid:
            r["shots"][i] = st.session_state[f"shot_{rid}_{i}"]
    save_pending(all_rs)


def copy_shots(shots: list, dst_id: int):
    all_rs = pending()
    for r in all_rs:
        if r["id"] == dst_id:
            r["shots"] = list(shots)
            for i, s in enumerate(r["shots"]):
                st.session_state[f"shot_{dst_id}_{i}"] = s
    save_pending(all_rs)


def fill_rest(rid: int, value: str):
    all_rs = pending()
    for r in all_rs:
        if r["id"] == rid:
            r["shots"] = [s or value for s in r["shots"]]
            for i, s in enumerate(r["shots"]):
                st.session_state[f"shot_{rid}_{i}"] = s
    save_pending(all_rs)


def drop(rid: int):
    save_pending([r for r in pending() if r["id"] != rid])


for r in rs:
    rid, n = r["id"], len(r["holes"])
    to_par = sum(h["score"] for h in r["holes"]) - r["par"]
    with st.container(border=True):
        st.subheader(f"{ri.round_date(r)} · {ri._short_event_name(r['event'])} · Round {r['round']}")
        st.caption(f"{r['layout']} · par {r['par']} · {n} holes · shot **{to_par:+d}**")
        if not r.get("has_stats"):
            st.warning("No stats were kept on PDGA Live for this round, so fairway / C1R / C2R would all save as NO.")

        mapped = names.get(r["layout"], [None, None])
        a, b, c, d = st.columns([2, 2, 2, 3])
        course = a.text_input("Course", value=mapped[0] or "", key=f"course_{rid}", placeholder="e.g. RM North")
        layout = b.text_input("Layout", value=mapped[1] or r["layout"], key=f"layout_{rid}")
        opts = conditions + ([r["suggested"]] if r.get("suggested") and r["suggested"] not in conditions else [])
        w = r.get("weather")
        cond = c.selectbox("Conditions", opts, index=opts.index(r["suggested"]) if r.get("suggested") in opts else None,
                           key=f"cond_{rid}", accept_new_options=True, placeholder="Pick or type",
                           help=(f"Weather during the round: {w['Temp_Max_F']:.0f}°F, wind {w['Wind_Mph']:.0f} mph "
                                 f"(gusts {w['Gust_Max_Mph']:.0f}), rain {w['Rain_Mm']} mm. Suggested from the past rounds "
                                 "whose weather was closest.") if w else "No weather found for this round.")
        notes = d.text_input("Notes", value=r.get("notes", ""), key=f"notes_{rid}")

        st.markdown("**Tee shots** <span style='opacity:.6'>· BHR / FHR = roller</span>", unsafe_allow_html=True)
        for row in range(0, n, 6):
            cols = st.columns(6)
            for i in range(row, min(row + 6, n)):
                h = r["holes"][i]
                key = f"shot_{rid}_{i}"
                if key not in st.session_state:
                    st.session_state[key] = r["shots"][i]
                diff = h["score"] - h["par"]
                mark = {-2: "🟢🟢", -1: "🟢", 0: "", 1: "🟥"}.get(diff, "🟥🟥")
                with cols[i - row]:
                    st.markdown(f"**{h['hole']}** · {h['length']}′ · par {h['par']} · {h['score']} {mark}")
                    st.segmented_control(f"Hole {h['hole']}", list(SHOT_LABELS), format_func=SHOT_LABELS.get,
                                         key=key, label_visibility="collapsed", on_change=set_shot, args=(rid, i))

        shots = [st.session_state.get(f"shot_{rid}_{i}") for i in range(n)]
        done = sum(s is not None for s in shots)
        # Same layout played again: copy the tee shots from another round waiting here, or from the last logged one.
        twin = next((o for o in rs if o["id"] != rid and o["layout"] == r["layout"] and len(o["holes"]) == n
                     and all(st.session_state.get(f"shot_{o['id']}_{i}") for i in range(n))), None)
        source = (f"round {twin['round']}", [st.session_state[f"shot_{twin['id']}_{i}"] for i in range(n)]) if twin else None
        if not source and course.strip():
            last = ri.last_logged_shots(course.strip(), layout.strip(), n)
            source = (last[0], last[1]) if last else None
        bcols = st.columns([2, 2, 2, 2, 3])
        bcols[0].button("Rest are BH", key=f"bh_{rid}", on_click=fill_rest, args=(rid, "BH"), disabled=done == n)
        bcols[1].button("Rest are FH", key=f"fh_{rid}", on_click=fill_rest, args=(rid, "FH"), disabled=done == n)
        if source:
            bcols[2].button(f"Copy from {source[0]}", key=f"copy_{rid}", on_click=copy_shots, args=(source[1], rid),
                            help=f"Same course and layout — copies those tee shots (you can still change any hole)")
        bcols[3].button("Don't log this round", key=f"drop_{rid}", on_click=drop, args=(rid,))
        missing = [x for x, ok in (("tee shots", done == n), ("course", course.strip()), ("conditions", cond)) if not ok]
        if bcols[4].button(f"Save round ({done}/{n} tee shots)", key=f"save_{rid}", type="primary",
                           disabled=bool(missing), use_container_width=True,
                           help=("Still needs: " + ", ".join(missing)) if missing else None):
            ri.save_round(r, course.strip(), layout.strip(), shots, cond, notes.strip(), w)
            names[r["layout"]] = [course.strip(), layout.strip()]
            ri.save_json(ri.COURSE_NAMES, names)
            drop(rid)
            st.session_state["flash"] = f"Saved {ri.round_date(r)} at {course.strip()} ({to_par:+d})."
            st.rerun()

# ─── Publish ──────────────────────────────────────────────────────────────────
st.divider()
FILES = ["data/rounds_cleaned.csv", "data/holes_cleaned.csv", "data/conditions_weather.csv", "data/course_names.json"]
changed = subprocess.run(["git", "status", "--porcelain", "--", *FILES], cwd=REPO, capture_output=True, text=True).stdout.strip()
if changed:
    with open(ri.ROUNDS_CSV) as f:
        before = subprocess.run(["git", "show", "HEAD:data/rounds_cleaned.csv"], cwd=REPO, capture_output=True, text=True).stdout
        new_rows = f.read().strip().count("\n") - before.strip().count("\n")
    st.markdown(f"**{new_rows} new round{'s' * (new_rows != 1)}** saved but not on the live dashboard yet.")
    if st.button("Push to the live dashboard", type="primary"):
        msg = f"Add {new_rows} round{'s' * (new_rows != 1)}"
        steps = [["git", "add", "--", *FILES], ["git", "commit", "-m", msg], ["git", "push"]]
        for cmd in steps:
            p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
            if p.returncode:
                st.error(f"`{' '.join(cmd)}` failed:\n\n```\n{p.stderr or p.stdout}\n```")
                break
        else:
            st.success("Pushed. Streamlit Cloud redeploys in a minute or two.")
else:
    st.caption("Everything saved is already on the live dashboard.")
