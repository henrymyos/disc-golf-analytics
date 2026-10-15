"""
Disc Golf Performance Analytics
A personal analytics dashboard for tracking and analyzing my disc golf rounds.
"""

import os

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import LeaveOneOut, cross_val_predict

from analysis import HOLES_PATH, bootstrap_band, correlation_history, PER_18, RAW, ROUNDS_PATH, DataError, hole_grid, load_tables, stroke_costs
from scorecard import scorecard_html

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Disc Golf Analytics",
    page_icon="🥏",
    layout="wide",
    initial_sidebar_state="auto",
)

# Color palette. Streamlit follows the viewer's own light/dark theme, so every
# colour here has to carry on both surfaces: each one clears 2.5:1 against the
# dark surface (#1a1a19) and 2.7:1 against the light one (#fcfcfb), which pins
# them to OKLCH lightness ~0.49-0.68. Chroma is held near 0.15-0.20 so they read
# as colours rather than as tinted grey.
COLOR_GOOD = "#149a63"     # green  — under par, hit the green
COLOR_BAD = "#dc4526"      # red    — over par, missed
COLOR_NEUTRAL = "#3f92e0"  # blue   — non-polar series (score trend, backhand)
COLOR_ACCENT = "#cc6f19"   # orange — second categorical series (forehand, C1R rate)
COLOR_MUTED = "#8e8e88"    # grey   — the neutral middle of the score scale

# One palette for score labels, shared by every chart that colors by Score_Label
# so a BOGEY is the same red everywhere. Covers every label in LABEL_OFFSETS.
# This is a diverging scale: greens under par, a neutral grey at PAR, and reds
# running to magenta as the hole gets worse. The old ramp drove the bad end
# toward black (#290d0c sat at 1.04:1 on a dark background — invisible); each
# step now separates by hue and chroma instead of by going darker.
SCORE_COLORS = {
    "ACE": "#00b08c", "EAGLE": "#00a179", "BIRDIE": COLOR_GOOD,
    "PAR": COLOR_MUTED,
    "BOGEY": COLOR_BAD, "DOUBLE BOGEY": "#c53019", "TRIPLE BOGEY": "#c02a3d",
    "QUADRUPLE BOGEY": "#b32663", "QUINTUPLE BOGEY": "#a32484",
    "SEXTUPLE BOGEY": "#9226a3",
}


# Human names for every column that reaches a chart axis, legend or table header.
STAT_LABELS = {
    "Fairway_Pct": "Fairway %", "C1R_Pct": "C1R %", "C2R_Pct": "C2R %",
    "C1X_Pct": "C1X putting %", "C2_Pct": "C2 putting %", "Scramble_Pct": "Scramble %",
    "OB_Pct": "OB rate",
}
PCT = lambda label, **kw: st.column_config.NumberColumn(label, format="percent", **kw)
RAW_COLUMN_CONFIG = {
    "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
    "Course_Name": "Course", "Layout": "Layout", "Holes": "Holes", "Course_Par": "Course par",
    "Score_vs_Par": "Score vs par", "Score_per_18": st.column_config.NumberColumn("Score vs par (per 18)", format="%.1f"),
    **{k: PCT(v) for k, v in STAT_LABELS.items()},
    "Conditions": "Conditions", "Notes": "Notes", "Round_ID": "Round ID", "Round_Label": "Round",
    "Hole": "Hole", "Hole_Pos": "Order played", "Par": "Par", "Distance": "Distance (ft)",
    "Score_Label": "Score", "Shot_Type": "Tee shot", "Fairway": "Fairway", "C1R": "C1R", "C2R": "C2R",
    "OB": "OB", "Strokes": "Strokes",
}


# ─── Data loading ─────────────────────────────────────────────────────────────
@st.cache_data
def load_data(rounds_mtime: float, holes_mtime: float):
    return load_tables(ROUNDS_PATH, HOLES_PATH)


try:
    rounds, holes = load_data(
        os.path.getmtime(ROUNDS_PATH),
        os.path.getmtime(HOLES_PATH),
    )
except DataError as e:
    st.error(str(e))
    st.stop()

# ─── Filters, section and URL state ───────────────────────────────────────────
# Every filter and the section live in the URL (st.query_params), so a copied
# link reopens the same view: ?course=Quailwood&conditions=Hot&view=strokes
SECTIONS = {
    "overview": "📈 Overview",
    "strokes": "🧮 Where My Strokes Go",
    "drivers": "🎯 What Drives My Score",
    "courses": "🗺️ Courses & Holes",
    "distance": "📏 Distance",
    "shots": "🥏 Shot Type",
    "model": "🤖 Score Model",
    "data": "📋 Raw Data",
}
ALL_COURSES = sorted(rounds["Course_Name"].unique())
ALL_CONDITIONS = sorted(rounds["Conditions"].dropna().unique(), key=str.lower)
MIN_DATE, MAX_DATE = rounds["Date"].min().date(), rounds["Date"].max().date()


def _match(values, options):
    """URL values -> valid options: exact matches first, else case-insensitive ones."""
    out = []
    for v in values:
        hits = [o for o in options if o == v] or [o for o in options if o.lower() == v.strip().lower()]
        out += [h for h in hits if h not in out]
    return out


def _parse_date(v, fallback):
    if not v:
        return fallback
    try:
        d = pd.to_datetime(v).date()
        return min(max(d, MIN_DATE), MAX_DATE)
    except (TypeError, ValueError):
        return fallback


if "_url_loaded" not in st.session_state:
    qp = st.query_params
    st.session_state["f_course"] = _match(qp.get_all("course"), ALL_COURSES)
    st.session_state["_url_layout"] = qp.get_all("layout")
    st.session_state["f_conditions"] = _match(qp.get_all("conditions"), ALL_CONDITIONS)
    st.session_state["f_18"] = qp.get("holes") == "18"
    st.session_state["f_score"] = "raw" if qp.get("score") == "raw" else "per 18 holes"
    st.session_state["f_dates"] = (_parse_date(qp.get("from"), MIN_DATE), _parse_date(qp.get("to"), MAX_DATE))
    st.session_state["view"] = qp.get("view") if qp.get("view") in SECTIONS else "overview"
    if qp.get("round") in set(rounds["Round_ID"]):
        st.session_state["round_pick"] = qp.get("round")
    st.session_state["_url_loaded"] = True

st.sidebar.title("Filters")

selected_courses = st.sidebar.multiselect(
    "Course", options=ALL_COURSES, key="f_course", placeholder="All courses",
    help="Leave empty for all courses.",
)
course_rounds_pool = rounds[rounds["Course_Name"].isin(selected_courses)] if selected_courses else rounds
layout_courses = course_rounds_pool.groupby("Layout")["Course_Name"].agg(lambda c: sorted(set(c)))
layout_opts = sorted(layout_courses.index, key=str.lower)
if "_url_layout" in st.session_state:
    st.session_state["f_layout"] = _match(st.session_state.pop("_url_layout"), layout_opts)
st.session_state["f_layout"] = [l for l in st.session_state.get("f_layout", []) if l in layout_opts]


def _layout_label(l):
    cs = layout_courses[l]
    return l if len(selected_courses) == 1 else f"{l} · {', '.join(cs[:2])}{' …' if len(cs) > 2 else ''}"


selected_layouts = st.sidebar.multiselect(
    "Layout", options=layout_opts, key="f_layout", placeholder="All layouts",
    format_func=_layout_label,
)
selected_conditions = st.sidebar.multiselect(
    "Conditions", options=ALL_CONDITIONS, key="f_conditions", placeholder="Any conditions",
)
only_18 = st.sidebar.checkbox("18-hole rounds only", key="f_18")
date_range = st.sidebar.date_input(
    "Date range", key="f_dates", min_value=MIN_DATE, max_value=MAX_DATE,
)
score_mode = st.sidebar.radio(
    "Score",
    options=["per 18 holes", "raw"],
    horizontal=True,
    key="f_score",
    help="Rounds run from 9 to 30 holes, so by default every round score is scaled to "
         "18 holes (score vs par × 18 ÷ holes). Raw shows the score as played.",
)
SCORE = PER_18 if score_mode == "per 18 holes" else RAW
SCORE_SUFFIX = " (per 18)" if SCORE == PER_18 else " (raw)"

# Apply filters. Filters pick rounds; holes follow their round via Round_ID.
rounds_f = course_rounds_pool
if selected_layouts:
    rounds_f = rounds_f[rounds_f["Layout"].isin(selected_layouts)]
if selected_conditions:
    rounds_f = rounds_f[rounds_f["Conditions"].isin(selected_conditions)]
if only_18:
    rounds_f = rounds_f[rounds_f["Holes"] == 18]
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    rounds_f = rounds_f[(rounds_f["Date"] >= start) & (rounds_f["Date"] <= end)]
holes_f = holes[holes["Round_ID"].isin(rounds_f["Round_ID"])]

st.sidebar.divider()
st.sidebar.markdown(
    f"**Filtered data**\n\n{len(rounds_f)} round{'' if len(rounds_f) == 1 else 's'} · {len(holes_f)} holes"
)
st.sidebar.caption("The link in the address bar keeps these filters and the section, so you can share it.")
st.sidebar.markdown(
    "Built by Henry · "
    "[GitHub](https://github.com/henrymyos/disc-golf-analytics)"
)


def sync_url(round_id=None):
    params = {}
    if selected_courses:
        params["course"] = selected_courses
    if selected_layouts:
        params["layout"] = selected_layouts
    if selected_conditions:
        params["conditions"] = selected_conditions
    if only_18:
        params["holes"] = "18"
    if SCORE == RAW:
        params["score"] = "raw"
    if isinstance(date_range, tuple) and len(date_range) == 2:
        if date_range[0] != MIN_DATE:
            params["from"] = date_range[0].isoformat()
        if date_range[1] != MAX_DATE:
            params["to"] = date_range[1].isoformat()
    view_now = st.session_state.get("view") or "overview"
    if view_now != "overview":
        params["view"] = view_now
    if round_id:
        params["round"] = round_id
    want = {k: (v if isinstance(v, list) else [v]) for k, v in params.items()}
    have = {k: st.query_params.get_all(k) for k in st.query_params.keys()}
    if want != have:
        st.query_params.from_dict(params)


# ─── Header ───────────────────────────────────────────────────────────────────
st.title("🥏 Disc Golf Performance Analytics")
st.markdown(
    "Personal performance dashboard built on my own round data. "
    "Tracking what actually drives my score — and what doesn't."
)

if rounds_f.empty:
    sync_url()
    st.warning("No data matches the current filters. Adjust the sidebar to see results.")
    st.stop()

# ─── KPI row ──────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Rounds", len(rounds_f))
c2.metric("Holes played", len(holes_f))
c3.metric(f"Avg score vs par{SCORE_SUFFIX}", f"{rounds_f[SCORE].mean():.1f}")
best = rounds_f[SCORE].min()
c4.metric(f"Best round{SCORE_SUFFIX}", f"{best:.1f}" if SCORE == PER_18 else int(best))
c5.metric("Under-par rate", f"{(holes_f['Score_vs_Par'] < 0).mean():.0%}",
          help="Share of holes under par — birdies plus eagles and aces.")

st.divider()

# ─── Section picker ───────────────────────────────────────────────────────────
def _keep_view():
    # Clicking the active segment would deselect it; stay on the section instead.
    if st.session_state.get("view") is None:
        st.session_state["view"] = st.session_state.get("_last_view", "overview")
    st.session_state["_last_view"] = st.session_state["view"]


view = st.segmented_control(
    "Section", options=list(SECTIONS), format_func=SECTIONS.get, key="view",
    on_change=_keep_view, label_visibility="collapsed",
) or "overview"
sync_url(st.session_state.get("round_pick") if view == "overview" else None)
st.write("")

# ─── Tab 1: Overview ──────────────────────────────────────────────────────────
if view == "overview":
    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("Score trend over time")
        fig = px.line(
            rounds_f.sort_values("Date", kind="stable"),
            x="Date", y=SCORE,
            markers=True,
            custom_data=["Round_ID"],
            hover_data={"Course_Name": True, "Layout": True, "Holes": True,
                        "Score_vs_Par": True, "Score_per_18": ":.1f", "Conditions": True},
            labels={"Score_vs_Par": "Score vs par (raw)", "Score_per_18": "Score vs par (per 18)",
                    "Course_Name": "Course"},
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_traces(line_color=COLOR_NEUTRAL, line_width=2,
                          marker=dict(size=10, color=COLOR_NEUTRAL))
        fig.update_layout(
            height=350,
            yaxis_title=f"Strokes vs par{SCORE_SUFFIX} (lower = better)",
            yaxis=dict(autorange="reversed"),
            clickmode="event+select",
            # Two rounds on one day share an x; "closest" makes a click pick the point under the cursor.
            hovermode="closest",
        )
        trend_event = st.plotly_chart(fig, width="stretch", key="trend",
                                      on_select="rerun", selection_mode="points")
        st.caption("Click a point to open that round's scorecard below.")
        picked = tuple(p["customdata"][0] for p in trend_event.selection.points
                       if p.get("customdata")) if trend_event else ()
        if picked and picked != st.session_state.get("_trend_pick"):
            st.session_state["round_pick"] = picked[0]
        st.session_state["_trend_pick"] = picked

    with col2:
        st.subheader("Score distribution")
        dist = holes_f["Score_Label"].value_counts(normalize=True).mul(100).round(1)
        order = ["ACE", "EAGLE", "BIRDIE", "PAR", "BOGEY",
                 "DOUBLE BOGEY", "TRIPLE BOGEY", "QUADRUPLE BOGEY",
                 "QUINTUPLE BOGEY", "SEXTUPLE BOGEY"]
        dist = dist.reindex([o for o in order if o in dist.index])
        fig = px.bar(
            dist.reset_index(),
            x="Score_Label", y="proportion",
            color="Score_Label", color_discrete_map=SCORE_COLORS,
            text="proportion",
            labels={"Score_Label": "Score", "proportion": "% of holes"},
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(height=350, showlegend=False,
                          xaxis_title="", yaxis_title="% of holes")
        st.plotly_chart(fig, width="stretch")

    st.subheader("Performance by course")
    course_stats = (
        rounds_f.groupby("Course_Name")
        .agg(Rounds=(SCORE, "count"),
             Avg_score=(SCORE, "mean"),
             Best=(SCORE, "min"),
             Avg_C1R=("C1R_Pct", "mean"),
             Avg_C1X=("C1X_Pct", "mean"),
             Avg_Fairway=("Fairway_Pct", "mean"),
             Avg_OB=("OB_Pct", "mean"))
        .reset_index().sort_values("Avg_score")
    )
    st.dataframe(
        course_stats, width="stretch", hide_index=True,
        column_config={
            "Course_Name": "Course", "Rounds": "Rounds",
            "Avg_score": st.column_config.NumberColumn(f"Avg score{SCORE_SUFFIX}", format="%+.1f"),
            "Best": st.column_config.NumberColumn(f"Best{SCORE_SUFFIX}", format="%+.1f"),
            "Avg_C1R": PCT("C1R %"), "Avg_C1X": PCT("C1X putting %"),
            "Avg_Fairway": PCT("Fairway %"), "Avg_OB": PCT("OB rate"),
        },
    )


    # ─── Scorecard ───────────────────────────────────────────────────────────
    st.subheader("Scorecard")
    round_opts = rounds_f.sort_values("Date", ascending=False, kind="stable")["Round_ID"].tolist()
    labels = dict(zip(rounds["Round_ID"], rounds["Round_Label"]))
    if st.session_state.get("round_pick") not in round_opts:
        st.session_state["round_pick"] = None
    rid = st.selectbox("Round", round_opts, key="round_pick", index=None,
                       format_func=lambda r: labels.get(r, r),
                       placeholder="Pick a round, or click a point on the trend")
    sync_url(rid)
    if rid:
        rnd = rounds.loc[rounds["Round_ID"] == rid].iloc[0]
        rh = holes[holes["Round_ID"] == rid]
        st.markdown(
            f"**{rnd['Round_Label']}** · {int(rnd['Holes'])} holes · par {int(rnd['Course_Par'])} · "
            f"**{int(rnd['Score_vs_Par']):+d}** ({rnd['Score_per_18']:+.1f} per 18) · {rnd['Conditions']}"
            + (f" · {rnd['Notes']}" if isinstance(rnd["Notes"], str) and rnd["Notes"].strip() else "")
        )
        # Two rounds at one course on one day sit on top of each other on the trend, so a
        # click can only land on one of them. Offer the other(s) right here.
        siblings = rounds[(rounds["Date"] == rnd["Date"]) & (rounds["Course_Name"] == rnd["Course_Name"])
                          & (rounds["Round_ID"] != rid) & rounds["Round_ID"].isin(round_opts)]
        if len(siblings):
            def _open_round(r):
                st.session_state["round_pick"] = r
            scols = st.columns(len(siblings) + 2)
            scols[0].caption("Same course, same day:")
            for sc, (_, sib) in zip(scols[1:], siblings.iterrows()):
                sc.button(f"Open R{sib['Round_ID'].rsplit('_', 1)[-1]} ({int(sib['Score_vs_Par']):+d})",
                          key=f"sib_{sib['Round_ID']}", on_click=_open_round, args=(sib["Round_ID"],))
        st.markdown(scorecard_html(rh, SCORE_COLORS), unsafe_allow_html=True)

        stat_rows = [("Score vs par (per 18)", "Score_per_18", "score"),
                     ("Score vs par (raw)", "Score_vs_Par", "score"),
                     ("Fairway", "Fairway_Pct", "pct"), ("C1R (green in reg)", "C1R_Pct", "pct"),
                     ("C2R", "C2R_Pct", "pct"), ("C1X putting", "C1X_Pct", "pct"),
                     ("C2 putting", "C2_Pct", "pct"), ("Scramble", "Scramble_Pct", "pct"),
                     ("OB rate", "OB_Pct", "pct")]
        fmt = {"score": lambda v: f"{v:+.1f}", "pct": lambda v: f"{v:.0%}"}
        dfmt = {"score": lambda v: f"{v:+.1f}", "pct": lambda v: f"{v * 100:+.0f} pts"}
        compare = pd.DataFrame([
            {"Stat": name, "This round": fmt[kind](rnd[col]),
             f"My average ({len(rounds_f)} rounds in view)": fmt[kind](rounds_f[col].mean()),
             "Difference": dfmt[kind](rnd[col] - rounds_f[col].mean())}
            for name, col, kind in stat_rows if col in rnd.index
        ])
        st.dataframe(compare, width="stretch", hide_index=True)


# ─── Where my strokes go ──────────────────────────────────────────────────────
if view == "strokes":
    st.markdown(
        "**Where do my strokes go?** For each mistake: how much worse a hole goes when it "
        "happens, times how often it happens, scaled to an 18-hole round. That's the "
        "strokes it costs me per round compared with never making that mistake."
    )
    costs = stroke_costs(holes_f)
    valid = costs[costs["Holes_when"].gt(0) & costs["Holes_otherwise"].gt(0)]
    if valid.empty:
        st.info("Every hole in this view went the same way on every stat, so there's nothing to compare. "
                "Widen the filters.")
    else:
        plot = valid.sort_values("Cost_per_18")
        bar_text = [f"{c:.1f} strokes · n={w} of {w + o} holes"
                    for c, w, o in zip(plot["Cost_per_18"], plot["Holes_when"], plot["Holes_otherwise"])]
        fig = go.Figure(go.Bar(
            x=plot["Cost_per_18"], y=plot["Event"], orientation="h",
            marker_color=[COLOR_BAD if c > 0 else COLOR_GOOD for c in plot["Cost_per_18"]],
            text=bar_text, textposition="auto",
            customdata=plot[["Swing", "Per_18", "Holes_when", "Holes_otherwise"]].values,
            hovertemplate=("<b>%{y}</b><br>Costs %{x:.2f} strokes per 18<br>"
                           "%{customdata[0]:.2f} strokes worse per hole it happens<br>"
                           "Happens %{customdata[1]:.1f} times per 18<br>"
                           "n = %{customdata[2]} holes it happened, %{customdata[3]} it didn't<extra></extra>"),
        ))
        fig.add_vline(x=0, line_color="gray")
        fig.update_layout(height=80 + 70 * len(plot), xaxis_title="Strokes per 18-hole round",
                          yaxis_title="", margin=dict(l=10, r=10, t=10, b=40))
        st.plotly_chart(fig, width="stretch")

        lines = []
        for _, r in valid.sort_values("Cost_per_18", ascending=False).iterrows():
            small = " (small sample, read loosely)" if min(r["Holes_when"], r["Holes_otherwise"]) < 10 else ""
            n_txt = f"n = {int(r['Holes_when'])} of {int(r['Holes_when'] + r['Holes_otherwise'])} holes"
            if r["Swing"] > 0:
                lines.append(
                    f"- **{r['Event']} costs about {r['Cost_per_18']:.1f} strokes a round.** It happens "
                    f"{r['Per_18']:.1f} times per 18 holes, and those holes average {r['Swing']:.2f} strokes "
                    f"worse than the rest ({n_txt}){small}."
                )
            else:
                lines.append(
                    f"- **{r['Event']} hasn't cost me strokes in this view.** Those holes average "
                    f"{abs(r['Swing']):.2f} strokes *better* than the rest ({n_txt}){small}."
                )
        for _, r in costs[~costs.index.isin(valid.index)].iterrows():
            how = "every" if r["Holes_otherwise"] == 0 else "no"
            lines.append(f"- **{r['Event']}:** happened on {how} hole in this view, so there's nothing to compare.")
        st.markdown("\n".join(lines))
        st.caption(
            "These overlap and don't add up: an OB hole usually misses C1R and the fairway too, so the same "
            "lost stroke shows up in more than one bar. Each bar answers \"what if only this one improved?\""
        )

        st.subheader("What if")
        w1, w2, w3 = st.columns([2, 2, 3])
        names = dict(zip(valid["Key"], valid["Event"]))
        default_key = "OB" if "OB" in names else valid["Key"].iloc[0]
        wf_key = w1.selectbox("Cut", list(names), index=list(names).index(default_key),
                              format_func=lambda k: {"OB": "OB", "C1R": "missed C1R", "C2R": "missed C2R",
                                                     "Fairway": "missed fairways"}[k], key="whatif_event")
        cut = w2.slider("by %", min_value=0, max_value=100, value=50, step=5, key="whatif_cut")
        row = valid.set_index("Key").loc[wf_key]
        saved = max(row["Cost_per_18"], 0) * cut / 100
        w3.metric("Strokes saved per 18", f"{saved:.1f}",
                  help="Assumes each avoided mistake turns that hole into an average non-mistake hole.")
        noun = {"OB": "OB holes", "C1R": "missed C1Rs", "C2R": "missed C2Rs", "Fairway": "missed fairways"}[wf_key]
        st.caption(
            f"Cutting {noun} by {cut}% means {row['Per_18'] * cut / 100:.1f} fewer per 18 holes, "
            f"each worth about {row['Swing']:.2f} strokes."
        )


# ─── Tab 2: What Drives My Score ──────────────────────────────────────────────
if view == "drivers":
    st.markdown(
        "**The big question:** of all my tracked stats, which ones actually correlate "
        "with shooting a low score?"
    )

    skill_cols = ["Fairway_Pct", "C1R_Pct", "C2R_Pct", "C1X_Pct", "OB_Pct"]
    available = [c for c in skill_cols if c in rounds_f.columns and rounds_f[c].notna().any()]

    # With two rounds a correlation is +/-1 by construction regardless of the data,
    # so ranking "strongest predictor" below this is meaningless, not merely noisy.
    MIN_ROUNDS_FOR_CORR = 3

    if len(rounds_f) < MIN_ROUNDS_FOR_CORR:
        st.info(
            f"Correlations need at least {MIN_ROUNDS_FOR_CORR} rounds to mean anything — "
            f"this view has {len(rounds_f)}. With two rounds every correlation comes out "
            f"as exactly +1 or −1 no matter what the numbers are. Widen the filters."
        )
    elif available:
        corrs = (
            rounds_f[available + [SCORE]]
            .corr()[SCORE].drop(SCORE).sort_values()
        )
        # A stat that never changes across the filtered rounds has no correlation at all.
        # Leaving the NaNs in gives blank bars and makes idxmax return NaN, which then
        # raises KeyError when used to look up a value.
        undefined = sorted(corrs[corrs.isna()].index)
        corrs = corrs.dropna()

    if len(rounds_f) >= MIN_ROUNDS_FOR_CORR and available and corrs.empty:
        st.info(
            "None of the tracked stats vary across the rounds in this view, so no "
            "correlation can be computed. Widen the filters to compare rounds that differ."
        )
    elif len(rounds_f) >= MIN_ROUNDS_FOR_CORR and available:
        col1, col2 = st.columns([3, 2])
        with col1:
            st.subheader("Stat correlations with round score")
            fig = px.bar(
                x=corrs.values, y=[STAT_LABELS.get(c, c) for c in corrs.index], orientation="h",
                color=corrs.values,
                color_continuous_scale=[(0, COLOR_GOOD), (0.5, COLOR_MUTED), (1, COLOR_BAD)],
                color_continuous_midpoint=0,
                labels={"x": f"Correlation with score vs par{SCORE_SUFFIX}", "y": "", "color": "Correlation"},
            )
            fig.add_vline(x=0, line_color="gray")
            fig.update_layout(height=350, coloraxis_showscale=False)
            st.plotly_chart(fig, width="stretch")

        with col2:
            st.subheader("Interpretation")
            stat_names = {
                "Fairway_Pct": "Fairway accuracy",
                "C1R_Pct": "Greens in regulation (C1R)",
                "C2R_Pct": "Reaching Circle 2 (C2R)",
                "C1X_Pct": "Putting from C1 (C1X)",
                "OB_Pct": "OB rate",
            }
            strongest = corrs.abs().idxmax()
            weakest = corrs.abs().idxmin()
            sv = corrs[strongest]
            direction = "lower" if sv < 0 else "higher"

            if len(rounds_f) < 8:
                caveat = (
                    f"- ⚠️ With only **{len(rounds_f)} rounds** in this view, these correlations "
                    f"are barely constrained by the data — one round can swing them from "
                    f"strong to nothing. Read them as noise until the sample grows."
                )
            else:
                caveat = (
                    f"- ⚠️ With only **{len(rounds_f)} rounds** in this view, these correlations "
                    f"are unstable — the strongest predictor has flipped between rounds before. "
                    f"Treat this as a working hypothesis, not a conclusion."
                )
            lines = [
                f"**More negative correlation = stat improves my score.**\n",
                f"- **{stat_names.get(strongest, strongest)} is currently my strongest predictor** "
                f"({sv:+.2f}). When this stat goes up, my score tends to be {direction}.",
                f"- **{stat_names.get(weakest, weakest)}** has the weakest relationship "
                f"to my score right now.",
            ]
            if undefined:
                names = ", ".join(stat_names.get(u, u) for u in undefined)
                lines.append(
                    f"- **{names}** — no correlation shown: this stat is identical across "
                    f"every round in view, so there is nothing to correlate against."
                )
            lines.append(caveat)
            st.markdown("\n".join(lines))

    # ─── How sure are we? ────────────────────────────────────────────────────
    st.subheader("How sure are we? Correlations as rounds added up")
    MIN_ROUNDS_FOR_HISTORY = 8
    hist_stats = [c for c in ["Fairway_Pct", "C1R_Pct", "C2R_Pct", "C1X_Pct", "OB_Pct"] if c in rounds_f.columns]
    if len(rounds_f) < MIN_ROUNDS_FOR_HISTORY:
        st.info(f"The history starts at {MIN_ROUNDS_FOR_HISTORY} rounds; this view has {len(rounds_f)}. "
                f"Widen the filters to see how the correlations moved.")
    else:
        @st.cache_data
        def _history(ids: tuple, score: str):
            sub = rounds[rounds["Round_ID"].isin(ids)]
            return (correlation_history(sub, score, hist_stats, MIN_ROUNDS_FOR_HISTORY),
                    bootstrap_band(sub, score, hist_stats))

        hist, band = _history(tuple(sorted(rounds_f["Round_ID"])), SCORE)
        HIST_COLORS = {"Fairway_Pct": COLOR_NEUTRAL, "C1R_Pct": COLOR_GOOD, "C2R_Pct": "#a35bd6",
                       "C1X_Pct": COLOR_ACCENT, "OB_Pct": COLOR_BAD}
        HIST_DASH = {"Fairway_Pct": "solid", "C1R_Pct": "solid", "C2R_Pct": "dash",
                     "C1X_Pct": "dot", "OB_Pct": "dashdot"}
        n_total = int(hist["Round_number"].max())
        fig = go.Figure()
        for stat in hist_stats:
            d = hist[hist["Stat"] == stat]
            name = STAT_LABELS.get(stat, stat)
            fig.add_scatter(
                x=d["Round_number"], y=d["Correlation"], mode="lines", name=name,
                line=dict(color=HIST_COLORS[stat], width=2.5, dash=HIST_DASH[stat]),
                customdata=d[["Round_Label"]].values,
                hovertemplate=f"<b>{name}</b> %{{y:+.2f}}<br>After %{{x}} rounds<br>%{{customdata[0]}}<extra></extra>",
            )
            b = band[band["Stat"] == stat].iloc[0]
            fig.add_scatter(
                x=[n_total], y=[b["Correlation"]], mode="markers+text", showlegend=False,
                marker=dict(color=HIST_COLORS[stat], size=9),
                error_y=dict(type="data", symmetric=False, array=[b["High"] - b["Correlation"]],
                             arrayminus=[b["Correlation"] - b["Low"]], color=HIST_COLORS[stat], thickness=2, width=6),
                text=[f" {name}"], textposition="middle right", textfont=dict(color=HIST_COLORS[stat]),
                hovertemplate=(f"<b>{name}</b> now %{{y:+.2f}}<br>80% band {b['Low']:+.2f} to {b['High']:+.2f}"
                               "<extra></extra>"),
            )
        fig.add_hline(y=0, line_color="gray")
        fig.update_layout(
            height=420, xaxis_title="Rounds played (in date order)",
            yaxis_title=f"Correlation with score{SCORE_SUFFIX}", yaxis=dict(range=[-1.05, 1.05]),
            xaxis=dict(range=[MIN_ROUNDS_FOR_HISTORY - 1, n_total + max(4, n_total * 0.18)]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            margin=dict(l=10, r=10, t=40, b=40),
        )
        st.plotly_chart(fig, width="stretch")
        band_txt = "; ".join(
            f"{STAT_LABELS.get(r['Stat'], r['Stat'])} {r['Correlation']:+.2f} ({r['Low']:+.2f} to {r['High']:+.2f})"
            for _, r in band.reindex(band["Correlation"].abs().sort_values(ascending=False).index).iterrows()
        )
        st.caption(
            f"Each line is that stat's correlation with score over the first N rounds of this view, starting at "
            f"{MIN_ROUNDS_FOR_HISTORY}. The bars on the right are 80% bootstrap bands for today's values "
            f"(resampling whole rounds 2,000 times): {band_txt}. Overlapping bands mean the ranking between "
            f"those stats isn't settled yet."
        )

    st.subheader("Hole-level impact: hitting C1R vs not")
    c1r_holes = holes_f.groupby("C1R")["Score_vs_Par"].agg(["mean", "count"]).round(2)
    c1r_holes.columns = ["Avg score vs par", "Holes"]
    c1r_holes = c1r_holes.reset_index()

    fig = px.bar(
        c1r_holes, x="C1R", y="Avg score vs par",
        color="C1R", color_discrete_map={"YES": COLOR_GOOD, "NO": COLOR_BAD},
        text="Avg score vs par", hover_data=["Holes"],
        labels={"C1R": "Hit C1R"},
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.add_hline(y=0, line_color="gray")
    fig.update_layout(height=300, showlegend=False, xaxis_title="Hit green in regulation?")
    st.plotly_chart(fig, width="stretch")

    yes_n = (holes_f["C1R"] == "YES").sum()
    no_n = (holes_f["C1R"] == "NO").sum()
    if yes_n > 0 and no_n > 0:
        swing = (holes_f[holes_f["C1R"] == "NO"]["Score_vs_Par"].mean()
                 - holes_f[holes_f["C1R"] == "YES"]["Score_vs_Par"].mean())
        st.info(
            f"**Per-hole swing:** {swing:.2f} strokes. "
            f"If I improved my C1R rate by 10 percentage points (≈2 holes per round), "
            f"I'd save roughly {swing * 2:.1f} strokes per round."
        )


# ─── Course and hole explorer ─────────────────────────────────────────────────
# Diverging steps for score vs par, matching SCORE_COLORS: ace/albatross .. quad+.
HEAT_STEPS = [(-3, SCORE_COLORS["ACE"]), (-2, SCORE_COLORS["EAGLE"]), (-1, SCORE_COLORS["BIRDIE"]),
              (0, COLOR_MUTED), (1, SCORE_COLORS["BOGEY"]), (2, SCORE_COLORS["DOUBLE BOGEY"]),
              (3, SCORE_COLORS["TRIPLE BOGEY"]), (4, SCORE_COLORS["QUADRUPLE BOGEY"])]


def heat_colorscale():
    lo, hi = HEAT_STEPS[0][0] - 0.5, HEAT_STEPS[-1][0] + 0.5
    scale = []
    for v, c in HEAT_STEPS:
        scale += [((v - 0.5 - lo) / (hi - lo), c), ((v + 0.5 - lo) / (hi - lo), c)]
    return scale, lo, hi


def rel_text(v):
    if pd.isna(v):
        return ""
    v = int(v)
    return "E" if v == 0 else f"{v:+d}"


if view == "courses":
    st.markdown(
        "Pick a course and a layout to see every hole across every round I've played it. "
        "Cells show the score vs par (E = par), so the colour is never the only signal."
    )
    course_counts = rounds_f["Course_Name"].value_counts()
    ccol, lcol = st.columns(2)
    x_course = ccol.selectbox(
        "Course", sorted(course_counts.index), key="explore_course",
        format_func=lambda c: f"{c} ({course_counts[c]} round{'' if course_counts[c] == 1 else 's'})",
    )
    course_rounds = rounds_f[rounds_f["Course_Name"] == x_course]
    layout_counts = course_rounds["Layout"].value_counts()
    ALL = "All layouts"
    layout_opts = ([ALL] if len(layout_counts) > 1 else []) + list(layout_counts.index)
    if st.session_state.get("explore_layout") not in layout_opts:
        st.session_state["explore_layout"] = layout_opts[0]
    n_for = lambda l: len(course_rounds) if l == ALL else layout_counts[l]
    x_layout = lcol.selectbox(
        "Layout", layout_opts, key="explore_layout",
        format_func=lambda l: f"{l} ({n_for(l)} round{'' if n_for(l) == 1 else 's'})",
    )
    sel_rounds = course_rounds if x_layout == ALL else course_rounds[course_rounds["Layout"] == x_layout]

    if len(sel_rounds) == 1:
        only = sel_rounds.iloc[0]
        st.info("This layout has been played once, so here's that round's scorecard.")
        st.markdown(
            f"**{only['Round_Label']}** · **{int(only['Score_vs_Par']):+d}** "
            f"({only['Score_per_18']:+.1f} per 18) · {only['Conditions']}"
        )
        st.markdown(scorecard_html(holes[holes["Round_ID"] == only["Round_ID"]], SCORE_COLORS),
                    unsafe_allow_html=True)
    else:
        if x_layout == ALL:
            st.caption("Different layouts can use different tees and pars, so rows line up by the order "
                       "holes were played. Pick one layout for a like-for-like view.")
        z, row_labels, per_hole = hole_grid(holes, sel_rounds)
        col_labels = (sel_rounds.set_index("Round_ID").loc[z.columns]
                      .apply(lambda r: r["Date"].strftime("%b ") + str(r["Date"].day)
                             + (f" R{r.name.rsplit('_', 1)[-1]}" if r["Round_Label"].endswith(tuple(f"R{i}" for i in range(1, 10))) else ""),
                             axis=1).tolist())
        scale, zmin, zmax = heat_colorscale()
        text = z.map(rel_text) if hasattr(z, "map") else z.applymap(rel_text)
        fig = go.Figure(go.Heatmap(
            z=z.clip(zmin + 0.5, zmax - 0.5).values, x=list(range(len(col_labels))), y=list(z.index),
            text=text.values, texttemplate="%{text}", textfont=dict(color="white", size=12),
            colorscale=scale, zmin=zmin, zmax=zmax, showscale=False, xgap=2, ygap=2,
            customdata=[[rl] * len(col_labels) for rl in row_labels],
            hovertemplate="Hole %{customdata} · %{x}<br>%{text} vs par<extra></extra>",
        ))
        fig.update_xaxes(tickvals=list(range(len(col_labels))), ticktext=col_labels, side="top",
                         title_text="Round")
        fig.update_yaxes(tickvals=list(z.index), ticktext=list(row_labels), autorange="reversed",
                         title_text="Hole")
        fig.update_layout(height=120 + 26 * len(z), margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(fig, width="stretch")
        if row_labels.str.endswith("†").any():
            st.caption("† This hole label appears at more than one position in the round, so each gets its own "
                       "row in the order played. What it is is a data question for Henry.")

        tough = per_hole.sort_values(["Avg", "OB_rate"], ascending=False).head(3)
        st.subheader("Toughest holes")
        tcols = st.columns(len(tough))
        for tc, (_, t) in zip(tcols, tough.iterrows()):
            tc.metric(f"Hole {t['Hole']} · par {t['Par']} · {t['Distance']:.0f} ft", f"{t['Avg']:+.2f}",
                      help=f"Average score vs par over {int(t['Rounds'])} rounds")
            tc.caption(f"Birdie {t['Birdie_rate']:.0%} · bogey or worse {t['Bogey_rate']:.0%} · OB {t['OB_rate']:.0%}")

        st.subheader("Every hole")
        st.dataframe(
            per_hole.drop(columns="Hole_Pos"), width="stretch", hide_index=True,
            column_config={
                "Hole": "Hole", "Par": "Par",
                "Distance": st.column_config.NumberColumn("Distance (ft)", format="%d"),
                "Rounds": "Rounds",
                "Avg": st.column_config.NumberColumn("Avg vs par", format="%+.2f"),
                "Birdie_rate": st.column_config.NumberColumn("Birdie rate", format="percent"),
                "Bogey_rate": st.column_config.NumberColumn("Bogey+ rate", format="percent"),
                "OB_rate": st.column_config.NumberColumn("OB rate", format="percent"),
            },
        )


# ─── Tab 3: Distance Analysis ─────────────────────────────────────────────────
if view == "distance":
    st.markdown(
        "Distance distributions differ by par, so analysis is split by par class."
    )

    par_choice = st.radio(
        "Par class",
        options=[3, 4],
        format_func=lambda p: f"Par {p}",
        horizontal=True,
    )

    par_bins = {
        3: ([0, 250, 325, 400, 1200],
            ["<250 ft", "250–325 ft", "325–400 ft", "400+ ft"]),
        4: ([0, 400, 500, 600, 700, 2000],
            ["<400 ft", "400–500 ft", "500–600 ft", "600–700 ft", "700+ ft"]),
    }

    ph = holes_f[holes_f["Par"] == par_choice].copy()

    if len(ph) < 5:
        st.warning(f"Not enough par {par_choice} data with current filters.")
    else:
        col1, col2 = st.columns([3, 2])

        with col1:
            st.subheader("Distance vs score")
            # trendline_scope="overall" is essential here: without it plotly fits one OLS
            # per color group, and Score_vs_Par is constant inside a Score_Label by
            # definition (every BIRDIE is -1), so each fit collapses to a flat line.
            # Renamed columns, because the OLS trendline hover prints the raw column names.
            fig = px.scatter(
                ph.rename(columns={"Score_vs_Par": "Score vs par", "Score_Label": "Score",
                                   "Course_Name": "Course"}),
                x="Distance", y="Score vs par",
                color="Score",
                color_discrete_map=SCORE_COLORS,
                hover_data=["Course", "Hole"],
                trendline="ols", trendline_scope="overall",
                trendline_color_override=COLOR_NEUTRAL,
            )
            fig.add_hline(y=0, line_color="gray", line_dash="dash")
            fig.update_layout(
                height=400,
                xaxis_title="Distance (ft)",
                yaxis_title="Score vs par (lower = better)",
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig, width="stretch")

        with col2:
            st.subheader(f"Correlations (par {par_choice} only)")
            dist_corrs = {
                "Distance vs Score": ph["Distance"].corr(ph["Score_vs_Par"]),
                "Distance vs C1R": ph["Distance"].corr(ph["C1R_bin"]),
                "Distance vs Fairway": ph["Distance"].corr(ph["Fairway_bin"]),
            }
            for k, v in dist_corrs.items():
                st.metric(k, "n/a" if pd.isna(v) else f"{v:+.3f}")

            def strength(v):
                a = abs(v)
                if a < 0.1: return "essentially no"
                if a < 0.3: return "a weak"
                if a < 0.5: return "a moderate"
                return "a strong"

            def describe(label, v, up, down):
                # A NaN correlation means one side never varied in this view. Falling
                # through the strength() ladder would label it "a strong negative".
                if pd.isna(v):
                    return (f"- **{label} (n/a)** — not enough variation in this view "
                            f"to compute a correlation.")
                sign = "positive" if v > 0 else "negative"
                return (f"- **{label} ({v:+.2f})** — {strength(v)} {sign} relationship: "
                        f"{up if v > 0 else down}")

            st.markdown("\n".join([
                "**What these mean:**\n",
                describe("Distance vs Score", dist_corrs["Distance vs Score"],
                         "longer holes tend to score worse (more strokes over par).",
                         "longer holes tend to score better."),
                describe("Distance vs C1R", dist_corrs["Distance vs C1R"],
                         "as distance grows, my chance of reaching the green in regulation goes up.",
                         "as distance grows, my chance of reaching the green in regulation drops."),
                describe("Distance vs Fairway", dist_corrs["Distance vs Fairway"],
                         "longer drives are more likely to stay in the fairway.",
                         "longer drives are less likely to stay in the fairway."),
            ]))

        st.subheader("Performance by distance range")
        bins, labels = par_bins[par_choice]
        ph["dist_bin"] = pd.cut(ph["Distance"], bins=bins, labels=labels)
        binned = (
            ph.groupby("dist_bin", observed=True)
            .agg(n=("Score_vs_Par", "count"),
                 Avg_score=("Score_vs_Par", "mean"),
                 Under_par_rate=("Score_vs_Par", lambda x: (x < 0).mean()),
                 C1R_rate=("C1R_bin", "mean"))
            .round(3).reset_index()
        )

        col1, col2 = st.columns([3, 2])
        with col1:
            fig = go.Figure()
            fig.add_bar(x=binned["dist_bin"], y=binned["Avg_score"],
                        name="Avg score vs par",
                        marker_color=[COLOR_GOOD if x < 0 else COLOR_BAD
                                      for x in binned["Avg_score"]],
                        text=binned["Avg_score"].round(2), textposition="outside")
            fig.add_scatter(x=binned["dist_bin"], y=binned["C1R_rate"],
                            name="C1R rate", yaxis="y2",
                            mode="lines+markers",
                            line=dict(color=COLOR_ACCENT, width=3),
                            marker=dict(size=10, color=COLOR_ACCENT))

            y_min = float(binned["Avg_score"].min())
            y_max = float(binned["Avg_score"].max())
            pad = max(0.25, (y_max - y_min) * 0.25)
            # axis is reversed: pass [high, low] so the "negative end" gets headroom for labels
            y_range = [y_max + pad, y_min - pad]

            fig.update_layout(
                height=350,
                yaxis=dict(title="Avg score vs par (lower = better)", range=y_range),
                yaxis2=dict(title="C1R rate", overlaying="y", side="right",
                            range=[0, 1], tickformat=".0%"),
                xaxis_title="Distance range",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            )
            st.plotly_chart(fig, width="stretch")

        with col2:
            st.dataframe(
                binned, width="stretch", hide_index=True,
                column_config={
                    "dist_bin": "Distance", "n": "Holes",
                    "Avg_score": st.column_config.NumberColumn("Avg vs par", format="%+.2f"),
                    "Under_par_rate": PCT("Under par"), "C1R_rate": PCT("C1R rate"),
                },
            )


# ─── Tab 4: Shot Type ─────────────────────────────────────────────────────────
if view == "shots":
    st.markdown(
        "**Tee-shot type only** (BH / FH / Other). Approach shots aren't tagged. "
        "Useful for asking: which shot type actually keeps me in play and out of trouble?"
    )

    if "Shot_Type" not in holes_f.columns:
        st.warning("Shot type data isn't available in the current dataset.")
        st_holes = holes_f.iloc[0:0]
    else:
        st_holes = holes_f[
            holes_f["Shot_Type"].notna() & (holes_f["Shot_Type"] != "")
        ].copy()

        # Hide shot types with too few shots to be meaningful (e.g. FH ROLLER).
        MIN_SHOTS = 20
        type_counts = st_holes["Shot_Type"].value_counts()
        kept_types = type_counts[type_counts >= MIN_SHOTS].index
        st_holes = st_holes[st_holes["Shot_Type"].isin(kept_types)].copy()

    if st_holes.empty:
        if "Shot_Type" in holes_f.columns:
            st.warning("No shot-type data with current filters.")
    else:
        SHOT_COLORS = {"BH": COLOR_NEUTRAL, "FH": COLOR_ACCENT, "Other": COLOR_MUTED}

        st.subheader("Tee-shot mix")
        mix = st_holes["Shot_Type"].value_counts()
        kpis = st.columns(len(mix))
        for kpi, (name, n) in zip(kpis, mix.items()):
            kpi.metric(f"{name} tee shots", f"{n}", f"{n / len(st_holes):.0%} of tracked")

        agg = (
            st_holes.groupby("Shot_Type")
            .agg(Tee_shots=("Score_vs_Par", "count"),
                 Avg_score=("Score_vs_Par", "mean"),
                 Fairway_rate=("Fairway_bin", "mean"),
                 C1R_rate=("C1R_bin", "mean"),
                 OB_rate=("OB_bin", "mean"),
                 Under_par_rate=("Score_vs_Par", lambda x: (x < 0).mean()))
            .round(3).reset_index()
        )

        st.subheader("Per-shot-type breakdown")
        col1, col2 = st.columns([3, 2])
        with col1:
            fig = px.bar(
                agg, x="Shot_Type", y="Avg_score",
                color="Shot_Type", color_discrete_map=SHOT_COLORS,
                text="Avg_score",
                labels={"Avg_score": "Avg score vs par", "Shot_Type": ""},
            )
            fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            fig.add_hline(y=0, line_color="gray", line_dash="dash")

            y_min = min(float(agg["Avg_score"].min()), 0.0)
            y_max = max(float(agg["Avg_score"].max()), 0.0)
            pad = max(0.25, (y_max - y_min) * 0.25)
            y_range = [y_max + pad, y_min - pad]

            fig.update_layout(
                height=350, showlegend=False,
                yaxis=dict(title="Avg score vs par (lower = better)", range=y_range),
            )
            st.plotly_chart(fig, width="stretch")
        with col2:
            st.dataframe(
                agg, width="stretch", hide_index=True,
                column_config={
                    "Shot_Type": "Tee shot", "Tee_shots": "Tee shots",
                    "Avg_score": st.column_config.NumberColumn("Avg vs par", format="%+.2f"),
                    "Fairway_rate": PCT("Fairway"), "C1R_rate": PCT("C1R"), "OB_rate": PCT("OB"),
                    "Under_par_rate": PCT("Under par"),
                },
            )

        st.subheader("Fairway, C1R, OB rates by shot type")
        rates_long = agg.melt(
            id_vars="Shot_Type",
            value_vars=["Fairway_rate", "C1R_rate", "OB_rate"],
            var_name="Metric", value_name="Rate",
        )
        rates_long["Metric"] = rates_long["Metric"].map({
            "Fairway_rate": "Fairway hit",
            "C1R_rate": "Green in reg (C1R)",
            "OB_rate": "OB",
        })
        fig = px.bar(
            rates_long, x="Metric", y="Rate", color="Shot_Type",
            color_discrete_map=SHOT_COLORS, barmode="group",
            labels={"Shot_Type": "Tee shot", "Metric": "", "Rate": "Rate"},
            text=rates_long["Rate"].map(lambda v: f"{v:.0%}"),
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            height=350, yaxis=dict(tickformat=".0%", title="Rate"),
            xaxis_title="",
        )
        st.plotly_chart(fig, width="stretch")

        st.subheader("Shot type by par class")
        par_breakdown = (
            st_holes.groupby(["Par", "Shot_Type"])
            .agg(Holes=("Score_vs_Par", "count"),
                 Avg_score=("Score_vs_Par", "mean"))
            .round(2).reset_index()
        )
        st.dataframe(
            par_breakdown, width="stretch", hide_index=True,
            column_config={"Par": "Par", "Shot_Type": "Tee shot", "Holes": "Holes",
                           "Avg_score": st.column_config.NumberColumn("Avg vs par", format="%+.2f")},
        )

        # Dynamic interpretation
        if len(agg) >= 2 and {"BH", "FH"}.issubset(set(agg["Shot_Type"])):
            bh = agg[agg["Shot_Type"] == "BH"].iloc[0]
            fh = agg[agg["Shot_Type"] == "FH"].iloc[0]
            better = "backhand" if bh["Avg_score"] < fh["Avg_score"] else "forehand"
            fwy_gap = (bh["Fairway_rate"] - fh["Fairway_rate"]) * 100
            fwy_winner = "BH" if fwy_gap > 0 else "FH"
            st.info(
                f"**Read:** my **{better}** scores better on average "
                f"(BH {bh['Avg_score']:+.2f} vs FH {fh['Avg_score']:+.2f} per hole). "
                f"**{fwy_winner}** hits the fairway more often ({abs(fwy_gap):.0f} pp gap). "
                f"Sample sizes — BH: {int(bh['Tee_shots'])} shots, FH: {int(fh['Tee_shots'])} shots. "
                f"FH is mostly used on par 3s right now, so the comparison isn't apples-to-apples."
            )


# ─── Tab 5: Score Model ───────────────────────────────────────────────────────
if view == "model":
    st.markdown(
        f"A simple linear model predicting **round score vs par{SCORE_SUFFIX}** from skill stats. "
        "Trained on every round in the current filters; honesty about the tiny sample is "
        "the point — predictions show a directional read, not an oracle."
    )

    feature_cols = ["Fairway_Pct", "C1R_Pct", "C2R_Pct", "C1X_Pct", "OB_Pct"]
    feats_available = [c for c in feature_cols if c in rounds_f.columns]
    model_df = rounds_f.dropna(subset=feats_available + [SCORE])

    if len(model_df) < 4:
        st.warning(
            f"Need at least 4 rounds with complete stats to fit a model; "
            f"current view has {len(model_df)}."
        )
    else:
        X = model_df[feats_available].values
        y = model_df[SCORE].values

        model_choice = st.radio(
            "Model",
            options=["Linear regression", "Ridge (regularized)"],
            horizontal=True,
            help="Ridge shrinks coefficients toward zero; safer when features are correlated.",
        )
        model = LinearRegression() if model_choice == "Linear regression" else Ridge(alpha=1.0)

        # Leave-one-out CV for an honest out-of-sample read
        loo_preds = cross_val_predict(model, X, y, cv=LeaveOneOut())
        loo_mae = mean_absolute_error(y, loo_preds)

        # Fit on all data for coefficient inspection and what-if
        model.fit(X, y)
        train_pred = model.predict(X)
        train_mae = mean_absolute_error(y, train_pred)

        col1, col2, col3 = st.columns(3)
        col1.metric("Rounds in fit", len(model_df))
        col2.metric("Leave-one-out MAE", f"{loo_mae:.2f} strokes",
                    help="Average prediction error on rounds the model didn't see during training.")
        col3.metric("Training MAE", f"{train_mae:.2f} strokes",
                    help="Lower than LOO MAE means the model is overfitting — expected with this sample size.")

        st.subheader("Predicted vs actual round score")
        pred_df = pd.DataFrame({
            "Round": model_df["Date"].dt.strftime("%Y-%m-%d") + " · " + model_df["Course_Name"],
            "Actual": y,
            "Predicted (LOO)": loo_preds,
            "Raw": model_df["Score_vs_Par"].values,
            "Per 18": model_df["Score_per_18"].values,
            "Holes": model_df["Holes"].values,
        })
        fig = px.scatter(
            pred_df, x="Actual", y="Predicted (LOO)",
            hover_data={"Round": True, "Holes": True, "Raw": True, "Per 18": ":.1f"},
            labels={"Actual": f"Actual score vs par{SCORE_SUFFIX}",
                    "Predicted (LOO)": f"Predicted (LOO){SCORE_SUFFIX}",
                    "Raw": "Score vs par (raw)", "Per 18": "Score vs par (per 18)"},
        )
        lo = min(y.min(), loo_preds.min()) - 1
        hi = max(y.max(), loo_preds.max()) + 1
        fig.add_shape(type="line", x0=lo, x1=hi, y0=lo, y1=hi,
                      line=dict(color="gray", dash="dash"))
        fig.update_traces(marker=dict(size=12, color=COLOR_NEUTRAL))
        fig.update_layout(height=380)
        st.plotly_chart(fig, width="stretch")

        st.subheader("Feature coefficients")
        coefs = pd.DataFrame({
            "Stat": [STAT_LABELS.get(f, f) for f in feats_available],
            "Coefficient": model.coef_,
        }).sort_values("Coefficient")
        coefs["Direction"] = coefs["Coefficient"].apply(
            lambda c: "↓ score (better)" if c < 0 else "↑ score (worse)"
        )
        fig = px.bar(
            coefs, x="Coefficient", y="Stat", orientation="h",
            color="Coefficient",
            color_continuous_scale=[(0, COLOR_GOOD), (0.5, COLOR_MUTED), (1, COLOR_BAD)],
            color_continuous_midpoint=0,
            text=coefs["Coefficient"].round(2),
        )
        fig.update_traces(textposition="outside")
        fig.add_vline(x=0, line_color="gray")
        fig.update_layout(height=300, coloraxis_showscale=False)
        st.plotly_chart(fig, width="stretch")

        st.caption(
            "Coefficients are on the raw 0–1 scale of each stat. A coefficient of −5 on a stat "
            "means a 10-percentage-point gain in that stat predicts ~0.5 strokes lower per round."
        )

        st.subheader("What-if: simulate a round")
        st.markdown(
            "Set each skill level and see the model's predicted score. "
            "Sliders are clamped to the range the model has actually seen — "
            "predictions outside that band would be pure extrapolation. "
            "C2R is also held at or above C1R, since C1 sits inside C2."
        )
        means = model_df[feats_available].mean()
        mins = model_df[feats_available].min()
        maxs = model_df[feats_available].max()
        what_if = {}
        cols = st.columns(len(feats_available))
        for col, feat in zip(cols, feats_available):
            lo = float(round(mins[feat], 2))
            hi = float(round(maxs[feat], 2))
            # Avoid degenerate slider when min == max
            if hi - lo < 0.01:
                lo = max(0.0, lo - 0.05)
                hi = min(1.0, hi + 0.05)
            default = float(round(means[feat], 2))
            default = min(max(default, lo), hi)
            what_if[feat] = col.slider(
                STAT_LABELS.get(feat, feat), min_value=lo, max_value=hi,
                value=default, step=0.01,
                help=f"Observed range in current data: {mins[feat]:.0%} – {maxs[feat]:.0%}",
            )

        # C1R is a subset of C2R -- a green hit inside 33 ft is also inside 66 ft --
        # so C2R can never be below C1R. The sliders move independently, so clamp
        # before the model ever sees an impossible round.
        if {"C1R_Pct", "C2R_Pct"} <= set(what_if) and what_if["C2R_Pct"] < what_if["C1R_Pct"]:
            st.warning(
                f"C2R % can't be below C1R % — every green hit inside C1 is inside C2 too. "
                f"Raising C2R from {what_if['C2R_Pct']:.0%} to {what_if['C1R_Pct']:.0%} "
                f"for this prediction."
            )
            what_if["C2R_Pct"] = what_if["C1R_Pct"]

        x_new = np.array([[what_if[f] for f in feats_available]])
        pred_score = float(model.predict(x_new)[0])
        st.metric(
            f"Predicted round score vs par{SCORE_SUFFIX}",
            f"{pred_score:+.1f}",
            delta=f"{pred_score - model_df[SCORE].mean():+.1f} vs my average",
            delta_color="inverse",
        )

        st.info(
            f"⚠️ With only **{len(model_df)} rounds**, the LOO MAE of "
            f"{loo_mae:.1f} strokes is on the order of my round-to-round spread. "
            f"Treat the model as a coefficient explorer, not a forecaster."
        )


# ─── Tab 6: Raw data ──────────────────────────────────────────────────────────
if view == "data":
    st.subheader("Rounds")
    st.dataframe(rounds_f.drop(columns=["Round_Label"]), width="stretch", hide_index=True,
                 column_config=RAW_COLUMN_CONFIG)
    st.subheader("Holes")
    st.dataframe(holes_f.drop(columns=[c for c in holes_f.columns if c.endswith("_bin")]),
                 width="stretch", hide_index=True, column_config=RAW_COLUMN_CONFIG)
