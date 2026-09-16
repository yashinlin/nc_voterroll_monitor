from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
PRIOR_VOTER_FILE = DATA_DIR / "ncvoter_Statewide 2026.08.31" / "ncvoter_Statewide.txt"
CURRENT_VOTER_FILE = DATA_DIR / "ncvoter_Statewide 2026.09.07" / "ncvoter_Statewide.txt"

KEY_COL = "ncid"  # statewide-unique voter id; voter_reg_num is only unique per-county
# Curated subset of the 70 source columns: this box has ~3.8GB RAM, far short of what a full 7.8M-row x 70-col DataFrame needs, so only analysis-relevant + human-review columns are kept. Extend if later analysis needs more.
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
# Low-cardinality columns loaded as category dtype instead of str: with ~9.2M
# rows per snapshot on a 3.8GB-RAM box, this is the difference between fitting
# in memory and not.
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
        path, sep=SEP, quotechar=QUOTECHAR, encoding=ENCODING, usecols=usecols, dtype=dtype, chunksize=CHUNKSIZE
    )
    return pd.concat(chunks, ignore_index=True)

def diff_voter_rolls(df_current: pd.DataFrame, df_prior: pd.DataFrame, output_path: Path, key_col: str = KEY_COL) -> pd.DataFrame:
    """Removed = status_cd is 'R' in df_current but was not 'R' in df_prior."""

    prior_status = df_prior[[key_col, "status_cd"]].rename(columns={"status_cd": "status_cd_prior"})
    merged = df_current.merge(prior_status, on=key_col, how="left")
    removed = merged[(merged["status_cd"] == "R") & (merged["status_cd_prior"] != "R")].copy()
    output_path.parent.mkdir(parents=True, exist_ok=True)
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


def run_weekly_diff():
    print(f"Loading prior snapshot from {PRIOR_VOTER_FILE}")
    # diff_voter_rolls reads df_prior[KEY_COL] (for the join) and status_cd (to
    # check whether a voter was already Removed before this period), plus
    # len(df_prior) for the summary — so those two columns is all we load.    
    
    df_prior = load_voter_file(PRIOR_VOTER_FILE, usecols=[KEY_COL, "status_cd"])
    print(f"Loading current snapshot from {CURRENT_VOTER_FILE}")
    df_current = load_voter_file(CURRENT_VOTER_FILE)
    print(f"\ndf_prior: {len(df_prior)} rows, df_current: {len(df_current)} rows")

    for name, df in [("df_prior", df_prior), ("df_current", df_current)]:
        dupes = df[KEY_COL].duplicated().sum()
        if dupes:
            print(f"WARNING: {dupes} duplicate {KEY_COL} values in {name}")

    output_path = OUTPUT_DIR / "removed_voters_2026.08.31_to_2026.09.07.csv"
    diff_voter_rolls(df_current, df_prior, output_path)


if __name__ == "__main__":
    run_weekly_diff()
