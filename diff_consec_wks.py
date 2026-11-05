
"""Weekly diff of NCSBE statewide voter-file releases.

1) Flags voters whose status_cd is 'R' (removed) in the later file but was not 'R'
in the earlier one (merged on ncid)
2) Builds a county summary: prior_registered, removed, removal_rate_pct, expected (prior_registered x
statewide rate), excess (removed - expected), small_county (<5,000 registered).

Inputs: zipped releases listed in RELEASES, in data/ (gitignored). Dates are the
release dates (the file's internal timestamp), not the download dates in the
filenames.

Outputs, in output/ (gitignored). Each filename includes 2 release dates compared, 
ie. tagged PRIOR_to_CURRENT by release date (eg. removed_voters_2026-09-06_to_2026-09-13.csv). 
- removed_voters_*.csv row-level, contains names (PII). Never commit or share.
- county_removal_summary_*.csv  aggregate counts only.

Also prints reason and status breakdowns and three CHECK lines (removed total,
registered total, 100 counties). These test the summary's plumbing, not the
diff logic.

Usage:
  python diff_consec_wks.py all
  python diff_consec_wks.py 2026-09-06 2026-09-13

Limits: each pair is analyzed on its own, so this script does not track a county
across weeks (plot_weekly_panels.py does that visually). Batch timing, notice and
process are not visible in the data. A high excess is a screening flag, not a finding.
 """

from pathlib import Path
import pandas as pd
import sys
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

# (release date, zip path). Release date = internal file timestamp, NOT the filename date.
RELEASES = [
    ("2026-08-30", DATA_DIR / "ncvoter_Statewide 2026.08.31.zip"),
    ("2026-09-06", DATA_DIR / "ncvoter_Statewide 2026.09.07.zip"),
    ("2026-09-13", DATA_DIR / "ncvoter_Statewide 2026.09.14.zip"),
    ("2026-09-20", DATA_DIR / "ncvoter_Statewide 2026.09.21.zip"),
    ("2026-09-27", DATA_DIR / "ncvoter_Statewide 2026.10.01.zip"),
    ("2026-10-04", DATA_DIR / "ncvoter_Statewide 2026.10.08.zip"),
    ("2026-10-11", DATA_DIR / "ncvoter_Statewide 2026.10.13.zip"),
    ("2026-10-18", DATA_DIR / "ncvoter_Statewide 2026.10.23.zip"),
    ("2026-10-25", DATA_DIR / "ncvoter_Statewide 2026.10.30.zip"),
    ("2026-11-01", DATA_DIR / "ncvoter_Statewide 2026.11.04.zip"),
]
RELEASE_PATHS = dict(RELEASES)

KEY_COL = "ncid"  # statewide-unique voter id; voter_reg_num is only unique per-county

# Curated subset of the 70 source columns
USECOLS = [
    "county_desc",
    KEY_COL,
    "voter_reg_num",
    "last_name",
    "first_name",
    "party_cd",
    "status_cd",
    "voter_status_desc",
    "reason_cd",
    "voter_status_reason_desc",
    "registr_dt",
]

# Define arguments for read_csv data loading parameters
CATEGORY_COLS = ["county_desc", "party_cd", "status_cd", "voter_status_desc", "reason_cd", "voter_status_reason_desc"]
SEP = "\t"
QUOTECHAR = '"'
ENCODING = "latin-1"  # source file is not valid UTF-8 (e.g. 0xbd at byte ~2946)
CHUNKSIZE = 200_000

def load_voter_file(path: Path, usecols: list[str] = USECOLS) -> pd.DataFrame:
    """Streams the file in chunks (full statewide file is too large to fit in
    memory at once on this box) keeping only usecols, and concatenates the
    result."""
    dtype = {col: ("category" if col in CATEGORY_COLS else str) for col in usecols}
    chunks = pd.read_csv(
        path, sep=SEP, quotechar=QUOTECHAR, encoding=ENCODING, usecols=usecols, dtype=dtype, chunksize=CHUNKSIZE, compression="zip",
    )
    return pd.concat(chunks, ignore_index=True)

def diff_voter_rolls(df_current: pd.DataFrame, df_prior: pd.DataFrame, output_path: Path, key_col: str = KEY_COL) -> pd.DataFrame:
    """Removed = status_cd is 'R' in df_current but was not 'R' in df_prior."""

    prior_status = df_prior[[key_col, "status_cd"]].rename(columns={"status_cd": "status_cd_prior"})
    merged = df_current.merge(prior_status, on=key_col, how="left") # tack on prior_status to df_current
    removed = merged[(merged["status_cd"] == "R") & (merged["status_cd_prior"] != "R")].copy()
    output_path.parent.mkdir(parents=True, exist_ok=True) 
    # above creates parent directory if that does not already exist (eg. in the case of new volunteers)
    removed.to_csv(output_path, index=False)
    reason_counts = removed["reason_cd"].fillna("(blank)").replace("", "(blank)").value_counts()
    status_counts = removed["status_cd"].value_counts()
    no_prior_record = removed[removed["status_cd_prior"].isna()]
    print("=" * 60)

    if len(no_prior_record):
        print(f"\nNOTE: {len(no_prior_record)} removed voters have no prior-snapshot record at all")
    pct = len(removed) / len(df_current) if len(df_current) else 0.0
    print(f"Current snapshot rows: {len(df_current)}")
    print(f"Prior snapshot rows:   {len(df_prior)}")
    print(f"Removed voters:        {len(removed)} ({pct:.2%} of current)")
    print("\nBreakdown by reason_cd:")
    print(reason_counts.to_string())
    print("\nBreakdown by status_cd:")
    print(status_counts.to_string())
    print(f"\nSaved: {output_path}")
    print("=" * 60)

    return removed

def county_removal_summary(removed: pd.DataFrame, df_prior: pd.DataFrame, min_registered: int = 5000) -> pd.DataFrame:
    """Removals per county, with rate = removed / prior registered (status != 'R')."""
    registered = df_prior.loc[df_prior["status_cd"] != "R"].groupby("county_desc", observed=True).size()
    registered.index = registered.index.astype(str)
    removed_n = removed.groupby(removed["county_desc"].astype(str)).size()

    out = pd.DataFrame({"prior_registered": registered, "removed": removed_n})
    out["removed"] = out["removed"].fillna(0).astype(int)
    out["removal_rate_pct"] = (out["removed"] / out["prior_registered"] * 100).round(3)
    statewide_rate = out["removed"].sum() / out["prior_registered"].sum()
    out["expected"] = (out["prior_registered"] * statewide_rate).round(1)
    out["excess"] = (out["removed"] - out["expected"]).round(1)
    out["small_county"] = out["prior_registered"] < min_registered
    out.index.name = "county_desc"
    return out.sort_values("excess", ascending=False).reset_index()

def county_reason_table(removed: pd.DataFrame, counties: list[str]) -> pd.DataFrame:
    """reason_cd counts for the given counties (rows = county, columns = reason code)."""
    r = removed.assign(county_desc=removed["county_desc"].astype(str),
                       reason_cd=removed["reason_cd"].astype(str))
    return pd.crosstab(r["county_desc"], r["reason_cd"]).reindex(counties, fill_value=0)

def run_pair(df_prior: pd.DataFrame, df_current: pd.DataFrame, prior_date: str, current_date: str) -> None:
    """Diff two loaded snapshots and write removal outputs tagged by release date.

    df_prior needs ncid, status_cd, county_desc; df_current needs the full USECOLS.
    """
    print(f"\ndf_prior: {len(df_prior)} rows, df_current: {len(df_current)} rows")
    for name, df in [("df_prior", df_prior), ("df_current", df_current)]:
        dupes = df[KEY_COL].duplicated().sum()
        if dupes:
            print(f"WARNING: {dupes} duplicate {KEY_COL} values in {name}")

    tag = f"{prior_date}_to_{current_date}"
    removed = diff_voter_rolls(df_current, df_prior, OUTPUT_DIR / f"removed_voters_{tag}.csv")
    summary = county_removal_summary(removed, df_prior)
    summary.to_csv(OUTPUT_DIR / f"county_removal_summary_{tag}.csv", index=False)
    print(summary.head(15).to_string(index=False))

    n_removed, n_reg = int(summary["removed"].sum()), int(summary["prior_registered"].sum())
    n_reg_check = int((df_prior["status_cd"] != "R").sum())
    print("CHECK removed total:", n_removed, "vs", len(removed), "OK" if n_removed == len(removed) else "FAIL")
    print("CHECK registered total:", n_reg, "vs", n_reg_check, "OK" if n_reg == n_reg_check else "FAIL")
    print("CHECK counties:", len(summary), "(expect 100)", "OK" if len(summary) == 100 else "FAIL")

def run_weekly_diff(prior_date: str, current_date: str) -> None:
    """Load two releases by date and run run_pair on them."""
    df_prior = load_voter_file(RELEASE_PATHS[prior_date], usecols=[KEY_COL, "status_cd", "county_desc"])
    df_current = load_voter_file(RELEASE_PATHS[current_date])
    run_pair(df_prior, df_current, prior_date, current_date)


def run_all_pairs(releases=RELEASES) -> None:
    """Run every consecutive pair, loading each file once.

    The current snapshot becomes the next prior, trimmed to the 3 columns
    that run_pair needs from a prior snapshot.
    """
    df_prior, prior_date = None, None
    for date, path in releases:
        print(f"[{datetime.now():%H:%M:%S}] Loading {date}", flush=True)
        df_current = load_voter_file(path)
        if df_prior is not None:
            print(f"[{datetime.now():%H:%M:%S}] Diffing {prior_date} -> {date}", flush=True)
            run_pair(df_prior, df_current, prior_date, date)
        df_prior = df_current[[KEY_COL, "status_cd", "county_desc"]].copy()
        prior_date = date
        del df_current
    print(f"[{datetime.now():%H:%M:%S}] Done")

if __name__ == "__main__":
    if sys.argv[1:] == ["all"]:
        run_all_pairs()
    elif len(sys.argv) == 3 and all(d in RELEASE_PATHS for d in sys.argv[1:]):
        run_weekly_diff(sys.argv[1], sys.argv[2])
    else:
        sys.exit(f"Usage: python diff_consec_wks.py all | PRIOR_DATE CURRENT_DATE\nValid dates: {[d for d, _ in RELEASES]}")
