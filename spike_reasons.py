"""Reason mix for the two largest single-week county spikes (aggregate counts only)."""
from pathlib import Path
import pandas as pd

agg = pd.read_csv(Path(__file__).resolve().parent / "output" / "reason_counts_by_county_week.csv")
agg["county_desc"] = agg["county_desc"].str.upper()

for county, wk, expected_total in [("CUMBERLAND", "2026-10-18", 217), ("GUILFORD", "2026-10-25", 283)]:
    sub = agg[(agg["county_desc"] == county) & (agg["week_end"] == wk)]
    total = int(sub["removed"].sum())
    print(f"\n{county}, week ending {wk}: {total} removed", "OK" if total == expected_total else "FAIL")
    print(sub.sort_values("removed", ascending=False)[["reason_cd", "reason_desc", "removed"]].to_string(index=False))