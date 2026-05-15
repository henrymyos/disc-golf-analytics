"""
Disc Golf Performance Analytics
A personal analytics dashboard for tracking and analyzing my disc golf rounds.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Disc Golf Analytics",
    page_icon="🥏",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Color palette
COLOR_GOOD = "#1d9e75"
COLOR_BAD = "#d4534f"
COLOR_NEUTRAL = "#5a8bb8"


# ─── Data loading ─────────────────────────────────────────────────────────────
@st.cache_data
def load_data():
    rounds = pd.read_csv("data/rounds_cleaned.csv", parse_dates=["Date"])
    holes = pd.read_csv("data/holes_cleaned.csv", parse_dates=["Date"])
    holes["C1R_bin"] = (holes["C1R"] == "YES").astype(int)
    holes["Fairway_bin"] = (holes["Fairway"] == "YES").astype(int)
    holes["OB_bin"] = (holes["OB"] == "YES").astype(int)
    return rounds, holes


rounds, holes = load_data()

# ─── Sidebar filters ──────────────────────────────────────────────────────────
st.sidebar.title("Filters")

selected_courses = st.sidebar.multiselect(
    "Course",
    options=sorted(rounds["Course_Name"].unique()),
    default=sorted(rounds["Course_Name"].unique()),
)

min_date, max_date = rounds["Date"].min(), rounds["Date"].max()
date_range = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

# Apply filters
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    rounds_f = rounds[
        (rounds["Date"] >= start) & (rounds["Date"] <= end)
        & (rounds["Course_Name"].isin(selected_courses))
    ]
    holes_f = holes[
        (holes["Date"] >= start) & (holes["Date"] <= end)
        & (holes["Course_Name"].isin(selected_courses))
    ]
else:
    rounds_f = rounds[rounds["Course_Name"].isin(selected_courses)]
    holes_f = holes[holes["Course_Name"].isin(selected_courses)]

st.sidebar.divider()
st.sidebar.markdown(
    f"**Filtered data**\n\n{len(rounds_f)} rounds · {len(holes_f)} holes"
)
st.sidebar.markdown(
    "Built by Henry · "
    "[GitHub](https://github.com/henrymyos/disc-golf-analytics)"
)


# ─── Header ───────────────────────────────────────────────────────────────────
st.title("🥏 Disc Golf Performance Analytics")
st.markdown(
    "Personal performance dashboard built on my own round data. "
    "Tracking what actually drives my score — and what doesn't."
)

if rounds_f.empty:
    st.warning("No data matches the current filters. Adjust the sidebar to see results.")
    st.stop()

# ─── KPI row ──────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Rounds", len(rounds_f))
c2.metric("Holes played", len(holes_f))
c3.metric("Avg score vs par", f"{rounds_f['Score_vs_Par'].mean():.1f}")
c4.metric("Best round", int(rounds_f["Score_vs_Par"].min()))
c5.metric("Birdie rate", f"{(holes_f['Score_vs_Par'] < 0).mean():.0%}")

st.divider()

# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 Overview", "🎯 What Drives My Score", "📏 Distance Analysis", "📋 Raw Data"]
)

# ─── Tab 1: Overview ──────────────────────────────────────────────────────────
with tab1:
    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("Score trend over time")
        fig = px.line(
            rounds_f.sort_values("Date"),
            x="Date", y="Score_vs_Par",
            markers=True,
            hover_data=["Course_Name", "Layout", "Conditions"],
        )
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_traces(line_color=COLOR_NEUTRAL, line_width=2,
                          marker=dict(size=10, color=COLOR_NEUTRAL))
        fig.update_layout(
            height=350,
            yaxis_title="Strokes vs par (lower = better)",
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Score distribution")
        dist = holes_f["Score_Label"].value_counts(normalize=True).mul(100).round(1)
        order = ["EAGLE", "BIRDIE", "PAR", "BOGEY", "DOUBLE BOGEY", "TRIPLE BOGEY"]
        dist = dist.reindex([o for o in order if o in dist.index])
        color_map = {
            "EAGLE": "#0d6e4e", "BIRDIE": COLOR_GOOD, "PAR": COLOR_NEUTRAL,
            "BOGEY": COLOR_BAD, "DOUBLE BOGEY": "#a3322f", "TRIPLE BOGEY": "#7a2622",
        }
        fig = px.bar(
            dist.reset_index(),
            x="Score_Label", y="proportion",
            color="Score_Label", color_discrete_map=color_map,
            text="proportion",
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(height=350, showlegend=False,
                          xaxis_title="", yaxis_title="% of holes")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Performance by course")
    course_stats = (
        rounds_f.groupby("Course_Name")
        .agg(Rounds=("Score_vs_Par", "count"),
             Avg_score=("Score_vs_Par", "mean"),
             Avg_C1R=("C1R_Pct", "mean"),
             Avg_C1X=("C1X_Pct", "mean"),
             Avg_Fairway=("Fairway_Pct", "mean"))
        .round(2).reset_index().sort_values("Avg_score")
    )
    st.dataframe(course_stats, use_container_width=True, hide_index=True)


# ─── Tab 2: What Drives My Score ──────────────────────────────────────────────
with tab2:
    st.markdown(
        "**The big question:** of all my tracked stats, which ones actually correlate "
        "with shooting a low score?"
    )

    skill_cols = ["Fairway_Pct", "C1R_Pct", "C2R_Pct", "C1X_Pct", "OB_Pct"]
    available = [c for c in skill_cols if c in rounds_f.columns and rounds_f[c].notna().any()]

    if len(rounds_f) >= 2 and available:
        corrs = (
            rounds_f[available + ["Score_vs_Par"]]
            .corr()["Score_vs_Par"].drop("Score_vs_Par").sort_values()
        )

        col1, col2 = st.columns([3, 2])
        with col1:
            st.subheader("Stat correlations with round score")
            fig = px.bar(
                x=corrs.values, y=corrs.index, orientation="h",
                color=corrs.values,
                color_continuous_scale=[(0, COLOR_GOOD), (0.5, "lightgray"), (1, COLOR_BAD)],
                color_continuous_midpoint=0,
                labels={"x": "Correlation with Score_vs_Par", "y": ""},
            )
            fig.add_vline(x=0, line_color="gray")
            fig.update_layout(height=350, coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Interpretation")
            stat_names = {
                "Fairway_Pct": "Fairway accuracy",
                "C1R_Pct": "Greens in regulation (C1R)",
                "C2R_Pct": "Reaching Circle 2 (C2R)",
                "C1X_Pct": "Putting from C1 (C1X)",
                "OB_Pct": "Avoiding OB",
            }
            strongest = corrs.abs().idxmax()
            weakest = corrs.abs().idxmin()
            sv = corrs[strongest]
            direction = "lower" if sv < 0 else "higher"

            st.markdown(
                f"**More negative correlation = stat improves my score.**\n\n"
                f"- **{stat_names.get(strongest, strongest)} is currently my strongest predictor** "
                f"({sv:+.2f}). When this stat goes up, my score tends to be {direction}.\n"
                f"- **{stat_names.get(weakest, weakest)}** has the weakest relationship "
                f"to my score right now.\n"
                f"- ⚠️ With only **{len(rounds_f)} rounds** in this view, these correlations are "
                f"unstable — the strongest predictor has flipped between rounds before. "
                f"Treat this as a working hypothesis, not a conclusion."
            )

    st.subheader("Hole-level impact: hitting C1R vs not")
    c1r_holes = holes_f.groupby("C1R")["Score_vs_Par"].agg(["mean", "count"]).round(2)
    c1r_holes.columns = ["Avg score vs par", "Holes"]
    c1r_holes = c1r_holes.reset_index()

    fig = px.bar(
        c1r_holes, x="C1R", y="Avg score vs par",
        color="C1R", color_discrete_map={"YES": COLOR_GOOD, "NO": COLOR_BAD},
        text="Avg score vs par", hover_data=["Holes"],
    )
    fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
    fig.add_hline(y=0, line_color="gray")
    fig.update_layout(height=300, showlegend=False, xaxis_title="Hit green in regulation?")
    st.plotly_chart(fig, use_container_width=True)

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


# ─── Tab 3: Distance Analysis ─────────────────────────────────────────────────
with tab3:
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
            fig = px.scatter(
                ph, x="Distance", y="Score_vs_Par",
                color="Score_Label",
                color_discrete_map={"BIRDIE": COLOR_GOOD, "PAR": COLOR_NEUTRAL, "BOGEY": COLOR_BAD},
                hover_data=["Course_Name", "Hole"],
                trendline="ols", trendline_color_override="black",
            )
            fig.add_hline(y=0, line_color="gray", line_dash="dash")
            fig.update_layout(
                height=400,
                xaxis_title="Distance (ft)",
                yaxis_title="Score vs par (lower = better)",
                yaxis=dict(autorange="reversed"),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader(f"Correlations (par {par_choice} only)")
            dist_corrs = {
                "Distance vs Score": ph["Distance"].corr(ph["Score_vs_Par"]),
                "Distance vs C1R": ph["Distance"].corr(ph["C1R_bin"]),
                "Distance vs Fairway": ph["Distance"].corr(ph["Fairway_bin"]),
            }
            for k, v in dist_corrs.items():
                st.metric(k, f"{v:+.3f}")

            def strength(v):
                a = abs(v)
                if a < 0.1: return "essentially no"
                if a < 0.3: return "a weak"
                if a < 0.5: return "a moderate"
                return "a strong"

            s_score = dist_corrs["Distance vs Score"]
            s_c1r = dist_corrs["Distance vs C1R"]
            s_fwy = dist_corrs["Distance vs Fairway"]

            st.markdown(
                f"**What these mean:**\n\n"
                f"- **Distance vs Score ({s_score:+.2f})** — {strength(s_score)} "
                f"{'positive' if s_score > 0 else 'negative'} relationship: longer holes tend to "
                f"score {'worse (more strokes over par)' if s_score > 0 else 'better'}.\n"
                f"- **Distance vs C1R ({s_c1r:+.2f})** — {strength(s_c1r)} "
                f"{'positive' if s_c1r > 0 else 'negative'} relationship: as distance grows, "
                f"my chance of reaching the green in regulation "
                f"{'goes up' if s_c1r > 0 else 'drops'}.\n"
                f"- **Distance vs Fairway ({s_fwy:+.2f})** — {strength(s_fwy)} "
                f"{'positive' if s_fwy > 0 else 'negative'} relationship: longer drives are "
                f"{'more' if s_fwy > 0 else 'less'} likely to stay in the fairway."
            )

        st.subheader("Performance by distance range")
        bins, labels = par_bins[par_choice]
        ph["dist_bin"] = pd.cut(ph["Distance"], bins=bins, labels=labels)
        binned = (
            ph.groupby("dist_bin", observed=True)
            .agg(n=("Score_vs_Par", "count"),
                 Avg_score=("Score_vs_Par", "mean"),
                 Birdie_rate=("Score_vs_Par", lambda x: (x < 0).mean()),
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
                            mode="lines+markers", line_color="black", line_width=2)
            fig.update_layout(
                height=350,
                yaxis=dict(title="Avg score vs par (lower = better)", autorange="reversed"),
                yaxis2=dict(title="C1R rate", overlaying="y", side="right",
                            range=[0, 1], tickformat=".0%"),
                xaxis_title="Distance range",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.dataframe(binned, use_container_width=True, hide_index=True)


# ─── Tab 4: Raw data ──────────────────────────────────────────────────────────
with tab4:
    st.subheader("Rounds")
    st.dataframe(rounds_f, use_container_width=True, hide_index=True)
    st.subheader("Holes")
    st.dataframe(holes_f, use_container_width=True, hide_index=True)
