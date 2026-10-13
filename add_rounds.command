#!/bin/zsh
# Double-click to open the Add Rounds page (local only).
cd "$(dirname "$0")"
(sleep 3; open http://localhost:8601) &
exec python3 -m streamlit run tools/add_rounds.py --server.port 8601 --server.headless true --browser.gatherUsageStats false
