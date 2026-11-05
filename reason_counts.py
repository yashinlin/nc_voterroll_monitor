"""Counts removals by reason code, county, and week.

Reads the row-level removed_voters_*.csv files in output/ (PII: names), and
writes only aggregate counts, which are safe to share.

Output: output/reason_counts_by_county_week.csv
  columns: week_end, county_desc, reason_cd, reason_desc, removed
Also prints the code-to-description table from the data and checks each
week's total against EXPECTED.

Update EXPECTED by hand when you add a week: copy the new pair's "Removed
voters" total from output/run_all.log. EXPECTED comes from the same run as the
CSVs, so it checks the files against the log, not the diff logic.

Usage:  python reason_counts.py
Run after diff_consec_wks.py has finished, never while it is running.

Limits: reason_cd is the category recorded in the NCSBE file. It does not show
how the process ran, whether notice was given, or timing within the week.
"""

from pathlib import Path
import pandas as pd

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
EXPECTED = {  # removed totals from the run log, by pair end date
	"2026-09-06": 2011, "2026-09-13": 1734, "2026-09-20": 2238, "2026-09-27": 1919,
	"2026-10-04": 2092, "2026-10-11": 2218, "2026-10-18": 2141, "2026-10-25": 2443,     
    "2026-11-01": 2411,
}

frames = []
for f in sorted(OUTPUT_DIR.glob("removed_voters_20??-??-??_to_20??-??-??.csv")):
	tag = f.stem.replace("removed_voters_", "")
	df = pd.read_csv(f, usecols=["county_desc", "reason_cd", "voter_status_reason_desc"], dtype=str)
	df["reason_cd"] = df["reason_cd"].fillna("(blank)")
	df["reason_desc"] = df["voter_status_reason_desc"].fillna("(blank)")
	df["pair"] = tag
	df["week_end"] = tag.split("_to_")[1]
	frames.append(df.drop(columns="voter_status_reason_desc"))

allr = pd.concat(frames, ignore_index=True)

# 1. code -> description, straight from the data
print(allr.groupby(["reason_cd", "reason_desc"]).size().rename("n").reset_index().to_string(index=False))

# 2. consistency check against the run log
got = allr.groupby("week_end").size().to_dict()
for wk, n in EXPECTED.items():
	print(wk, got.get(wk), n, "OK" if got.get(wk) == n else "FAIL")

# 3. aggregate table (counts only, no names): safe to share
agg = (allr.groupby(["week_end", "county_desc", "reason_cd", "reason_desc"])
	   .size().rename("removed").reset_index())
agg.to_csv(OUTPUT_DIR / "reason_counts_by_county_week.csv", index=False)
print("Saved", OUTPUT_DIR / "reason_counts_by_county_week.csv", len(agg), "rows")
