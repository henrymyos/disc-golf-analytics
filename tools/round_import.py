"""
Pull tournament rounds from PDGA Live and turn them into rows for the two CSVs.

PDGA Live has hole scores, pars, lengths and (when the player keeps stats) a
per-hole breakdown of where the drive and the approach ended up. Tee shot type
(BH/FH) isn't recorded anywhere, so the Add Rounds page asks for it.
"""
from __future__ import annotations

import csv
import json
import re
import statistics
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

PDGA_NUM = 227040
DATA = Path(__file__).resolve().parent.parent / "data"
ROUNDS_CSV = DATA / "rounds_cleaned.csv"
HOLES_CSV = DATA / "holes_cleaned.csv"
PENDING = DATA / "pending_rounds.json"          # fetched, waiting for shot types (not committed)
COURSE_NAMES = DATA / "course_names.json"       # PDGA layout name -> [Course_Name, Layout]
WEATHER = DATA / "conditions_weather.csv"       # past rounds' weather + the Conditions label given

ROUND_COLS = ["Date", "Course_Name", "Layout", "Holes", "Course_Par", "Score_vs_Par", "Fairway_Pct",
              "Scramble_Pct", "C1R_Pct", "C2R_Pct", "C1X_Pct", "C2_Pct", "OB_Pct", "Conditions", "Notes",
              "Round_ID"]
HOLE_COLS = ["Date", "Course_Name", "Hole", "Par", "Distance", "Score_Label", "Shot_Type", "Fairway", "C1R", "C2R", "OB",
             "Round_ID", "Hole_Pos"]
WEATHER_COLS = ["Date", "Course_Name", "Conditions", "Temp_Max_F", "Wind_Mph", "Gust_Max_Mph", "Rain_Mm"]
SHOT_TYPES = ["BH", "FH", "BH ROLLER", "FH ROLLER"]
LABELS = {-2: "EAGLE", -1: "BIRDIE", 0: "PAR", 1: "BOGEY", 2: "DOUBLE BOGEY", 3: "TRIPLE BOGEY",
          4: "QUADRUPLE BOGEY", 5: "QUINTUPLE BOGEY", 6: "SEXTUPLE BOGEY"}

# PDGA stat ids (from the PDGA Live stats page)
FAIRWAY_HITS, SCRAMBLE, C1X_PUTTING, C2_PUTTING, OB_COUNT = 1, 5, 7, 8, 21


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "disc-golf-analytics round import"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def event_id(text: str) -> int:
    """Accepts an event id or any PDGA event / PDGA Live link."""
    m = re.search(r"(?:event/|eventId=|TournID=)(\d+)", text) or re.fullmatch(r"\s*(\d+)\s*", text)
    if not m:
        raise ValueError("Paste a PDGA event link (pdga.com/tour/event/…) or the event number.")
    return int(m.group(1))


def _short_event_name(name: str) -> str:
    name = re.split(r"\s+(?:presented|sponsored|powered)\b", name, flags=re.I)[0]
    return re.sub(r"^(?:\d{4}\s+|\d+(?:st|nd|rd|th)\s+annual\s+)", "", name, flags=re.I).strip()


def fetch_event(text: str, pdga_num: int = PDGA_NUM) -> list[dict]:
    """Every round the player has in this event, with hole-by-hole stats."""
    tid = event_id(text)
    ev = _get(f"https://www.pdga.com/apps/tournament/live-api/live_results_fetch_event?TournID={tid}")["data"]
    out = []
    for div in sorted(ev["Divisions"], key=lambda d: d["Division"] != "MPO"):
        if out:
            break  # found the player's division
        for rnd in range(1, (div.get("LatestRound") or 0) + 1):
            data = _get("https://www.pdga.com/apps/tournament/live-api/live_results_fetch_round"
                        f"?TournID={tid}&Division={div['Division']}&Round={rnd}")["data"]
            data = data[0] if isinstance(data, list) else data
            me = next((s for s in data["scores"] if s.get("PDGANum") == pdga_num), None)
            if not me:
                if rnd == 1:
                    break  # not in this division
                continue
            if not me.get("Completed"):
                continue
            layout = next(l for l in data["layouts"] if l["LayoutID"] == me["LayoutID"])
            detail = sorted(layout["Detail"], key=lambda h: h["Ordinal"])
            breakdown = {h["holeOrdinal"]: h["holeBreakdown"]
                         for h in _get(f"https://www.pdga.com/api/v1/feat/live-scores/{me['ScoreID']}/hole-breakdowns")}
            stats = next((s["stats"] for s in _get(f"https://www.pdga.com/api/v1/feat/stats/round-stats/{me['RoundID']}")
                          if s["score"]["resultId"] == me["ResultID"]), [])
            overview = _get(f"https://www.pdga.com/api/v1/feat/live-result-overview/{me['ResultID']}")
            started = next((p["liveScore"]["createdAt"] for p in overview["playerRounds"]
                            if p["liveRound"]["round"] == rnd), None)
            out.append({
                "id": me["ScoreID"], "event": ev.get("Name") or ev.get("TournamentName") or f"Event {tid}",
                "event_id": tid, "location": ev.get("Location") or ev.get("LocationShort"),
                "start_date": ev.get("StartDate"), "end_date": ev.get("EndDate"),
                "division": div["Division"], "round": rnd, "started": started,
                "layout": layout["Name"].strip(), "par": layout["Par"],
                "holes": [{"hole": int(h["Label"]) if str(h["Label"]).isdigit() else h["Ordinal"],
                           "par": h["Par"], "length": h["Length"],
                           "score": int(me["HoleScores"][i]),
                           **{k: (breakdown.get(h["Ordinal"]) or {}).get(k) for k in ("driving", "green", "ob")}}
                          for i, h in enumerate(detail)],
                "stats": {str(s["statId"]): [s["statCount"], s["statOpportunityCount"]] for s in stats},
                "has_stats": bool(breakdown) and all(b.get("driving") for b in breakdown.values()),
            })
    return out


# ─── Weather → Conditions ─────────────────────────────────────────────────────

def _geocode(place: str):
    city = place.split(",")[0].strip()
    res = _get("https://geocoding-api.open-meteo.com/v1/search?count=10&name=" + urllib.parse.quote(city)).get("results") or []
    state = place.split(",")[1].strip().lower() if "," in place else ""
    best = next((r for r in res if state and state in (r.get("admin1", "").lower(), r.get("country_code", "").lower())), None)
    return best or (res[0] if res else None)


def round_weather(r: dict) -> dict | None:
    """Temperature, wind and rain over the ~4 hours of the round."""
    if not r.get("location") or not r.get("started"):
        return None
    g = _geocode(r["location"])
    if not g:
        return None
    start = datetime.fromisoformat(r["started"].replace("Z", "+00:00"))
    day = start.date()
    q = (f"latitude={g['latitude']}&longitude={g['longitude']}&start_date={day - timedelta(days=1)}&end_date={day + timedelta(days=1)}"
         "&hourly=temperature_2m,wind_speed_10m,wind_gusts_10m,precipitation&temperature_unit=fahrenheit"
         "&wind_speed_unit=mph&timezone=GMT")
    try:
        h = _get("https://archive-api.open-meteo.com/v1/archive?" + q)["hourly"]
    except Exception:
        h = _get("https://api.open-meteo.com/v1/forecast?past_days=92&" + q)["hourly"]  # archive lags a few days
    times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in h["time"]]
    idx = [i for i, t in enumerate(times) if start - timedelta(minutes=30) <= t <= start + timedelta(hours=4)
           and h["temperature_2m"][i] is not None]
    if not idx:
        return None
    return {"Temp_Max_F": round(max(h["temperature_2m"][i] for i in idx), 1),
            "Wind_Mph": round(statistics.mean(h["wind_speed_10m"][i] for i in idx), 1),
            "Gust_Max_Mph": round(max(h["wind_gusts_10m"][i] for i in idx), 1),
            "Rain_Mm": round(sum(h["precipitation"][i] or 0 for i in idx), 1)}


def past_conditions() -> list[dict]:
    if not WEATHER.exists():
        return []
    with open(WEATHER, newline="") as f:
        return [{**r, **{k: float(r[k]) for k in WEATHER_COLS[3:]}} for r in csv.DictReader(f)]


def suggest_conditions(w: dict | None, past: list[dict] | None = None, k: int = 3) -> str | None:
    """The Conditions label of the past rounds whose weather was most like this one (weighted nearest neighbours)."""
    past = past if past is not None else past_conditions()
    if not w or not past:
        return None
    sd = {c: statistics.pstdev([p[c] for p in past]) or 1 for c in WEATHER_COLS[3:]}
    weight = {"Temp_Max_F": 1, "Wind_Mph": 1.5, "Gust_Max_Mph": 1, "Rain_Mm": 1}

    def dist(p):
        return sum((weight[c] * (min(w[c], 5) if c == "Rain_Mm" else w[c]) / sd[c]
                    - weight[c] * (min(p[c], 5) if c == "Rain_Mm" else p[c]) / sd[c]) ** 2 for c in sd) ** 0.5

    votes: dict[str, float] = {}
    for p in sorted(past, key=dist)[:k]:
        votes[p["Conditions"]] = votes.get(p["Conditions"], 0) + 1 / (dist(p) + 0.3)
    return max(votes, key=votes.get)


# ─── Building the CSV rows ────────────────────────────────────────────────────

def course_slug(course: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", course.lower()).strip("-")


def make_round_id(date: str, course: str, n: int) -> str:
    """YYYY-MM-DD_<course-slug>_<n>: n counts rounds at that course that day, in the order they were logged."""
    return f"{date}_{course_slug(course)}_{n}"


def next_round_id(date: str, course: str) -> str:
    n = 1
    if ROUNDS_CSV.exists():
        with open(ROUNDS_CSV, newline="") as f:
            n += sum(r["Date"] == date and r["Course_Name"] == course for r in csv.DictReader(f))
    return make_round_id(date, course, n)


def hole_score_vs_par(h: dict) -> int:
    """Score vs par of a holes_cleaned.csv row (an ace is 1 stroke, whatever the par)."""
    label, par = h["Score_Label"], int(h["Par"])
    if label == "ACE":
        return 1 - par
    return next(k for k, v in LABELS.items() if v == label)


def is_fairway(driving: str | None, par: int) -> bool:
    # A par-3 drive only counts if it finishes inside C2; on longer holes landing in the fairway is enough.
    return driving in (("c1", "c2", "parked") if par == 3 else ("hit", "c1", "c2", "parked"))


def round_date(r: dict) -> str:
    """Local date the round was played (event dates bound it; scorecards are created at the tee)."""
    if r.get("started"):
        # PDGA Live gives UTC; US events are 4–10 hours behind, so a 7-hour shift lands on the right day.
        d = (datetime.fromisoformat(r["started"].replace("Z", "+00:00")) - timedelta(hours=7)).date().isoformat()
        if (not r.get("start_date") or d >= r["start_date"]) and (not r.get("end_date") or d <= r["end_date"]):
            return d
    return r.get("start_date") or r.get("end_date")


def build_rows(r: dict, course: str, layout: str, shots: list[str], conditions: str, notes: str):
    date, n = round_date(r), len(r["holes"])
    round_id = next_round_id(date, course)
    holes = []
    for pos, (h, shot) in enumerate(zip(r["holes"], shots), start=1):
        diff = h["score"] - h["par"]
        label = "ACE" if h["score"] == 1 else LABELS.get(diff)
        if label is None:
            raise ValueError(f"No score label for {h['score']} on a par {h['par']} (hole {h['hole']})")
        c1 = h["green"] in ("c1", "parked")
        holes.append({"Date": date, "Course_Name": course, "Hole": h["hole"], "Par": h["par"], "Distance": h["length"],
                      "Score_Label": label, "Shot_Type": shot, "Fairway": "YES" if is_fairway(h["driving"], h["par"]) else "NO",
                      "C1R": "YES" if c1 else "NO", "C2R": "YES" if c1 or h["green"] == "c2" else "NO",
                      "OB": "YES" if (h["ob"] or 0) > 0 else "NO", "Round_ID": round_id, "Hole_Pos": pos})
    pct = lambda yes, total: round(yes / total, 3) if total else 0
    stat = lambda i: r["stats"].get(str(i), [0, 0])
    ob_throws = stat(OB_COUNT)[0] if str(OB_COUNT) in r["stats"] else sum(h["ob"] or 0 for h in r["holes"])
    rnd = {"Date": date, "Course_Name": course, "Layout": layout, "Holes": n, "Course_Par": r["par"],
           "Score_vs_Par": sum(h["score"] for h in r["holes"]) - r["par"],
           "Fairway_Pct": pct(sum(x["Fairway"] == "YES" for x in holes), n),
           "Scramble_Pct": pct(*stat(SCRAMBLE)),
           "C1R_Pct": pct(sum(x["C1R"] == "YES" for x in holes), n),
           "C2R_Pct": pct(sum(x["C2R"] == "YES" for x in holes), n),
           "C1X_Pct": pct(*stat(C1X_PUTTING)), "C2_Pct": pct(*stat(C2_PUTTING)),
           "OB_Pct": pct(ob_throws, n), "Conditions": conditions, "Notes": notes, "Round_ID": round_id}
    return rnd, holes


def _append(path: Path, cols: list[str], rows: list[dict]):
    new = not path.exists()
    if not new:
        with open(path, "rb") as f:
            f.seek(-1, 2)
            needs_newline = f.read(1) != b"\n"
        # Write in the file's own column order so a column added to the CSV later never shifts values.
        with open(path, newline="") as f:
            header = next(csv.reader(f))
        missing = [c for c in cols if c not in header]
        if missing:
            raise ValueError(f"{path.name} has no {', '.join(missing)} column; run tools/backfill_round_ids.py first")
        cols = header
    with open(path, "a", newline="") as f:
        if new:
            f.write(",".join(cols) + "\n")
        elif needs_newline:
            f.write("\n")
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        for row in rows:
            w.writerow({c: _fmt(row.get(c, "")) for c in cols})


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))
    return v


def already_logged(r: dict) -> bool:
    """A round on the same date with the same score and hole count is already in rounds_cleaned.csv."""
    with open(ROUNDS_CSV, newline="") as f:
        return any(row["Date"] == round_date(r) and int(row["Holes"]) == len(r["holes"])
                   and int(row["Score_vs_Par"]) == sum(h["score"] for h in r["holes"]) - r["par"]
                   for row in csv.DictReader(f))


def last_logged_shots(course: str, layout: str, n: int) -> tuple[str, list[str]] | None:
    """Tee shots from the most recent logged round on this course and layout (for 'copy from last time')."""
    with open(ROUNDS_CSV, newline="") as f:
        matches = sorted(((r["Date"], r["Round_ID"]) for r in csv.DictReader(f)
                          if r["Course_Name"] == course and r["Layout"] == layout and int(r["Holes"]) == n), reverse=True)
    if not matches:
        return None
    date, rid = matches[0]
    with open(HOLES_CSV, newline="") as f:
        rows = [h for h in csv.DictReader(f) if h["Round_ID"] == rid]
    if len(rows) != n:
        return None
    return date, [h["Shot_Type"].strip() for h in sorted(rows, key=lambda h: int(h["Hole_Pos"]))]


def save_round(r: dict, course: str, layout: str, shots: list[str], conditions: str, notes: str, weather: dict | None):
    rnd, holes = build_rows(r, course, layout, shots, conditions, notes)
    _append(ROUNDS_CSV, ROUND_COLS, [rnd])
    _append(HOLES_CSV, HOLE_COLS, holes)
    if weather:
        _append(WEATHER, WEATHER_COLS, [{"Date": rnd["Date"], "Course_Name": course, "Conditions": conditions, **weather}])
    return rnd


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, value):
    path.write_text(json.dumps(value, indent=1) + "\n")
