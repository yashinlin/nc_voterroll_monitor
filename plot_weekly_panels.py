"""Weekly panel chart of county voter removals, ranked by cumulative excess.

Reads every output/county_removal_summary_*.csv (aggregate counts, no PII) and
writes output/weekly_panels_excess.png: one panel per week-pair, with the same
top-20 counties in the same left-to-right order in every panel.

Ranking (RANK_BY = "excess"): total excess over all weeks shown, where
excess = removed - expected and expected = the county's prior registered voters
x that week's statewide removal rate. Bars show % of the county's registered
voters removed that week (METRIC). Numbers above bars are people removed; the
5 tallest bars per panel also carry the county name. Dashed line = statewide
rate; hatched = small county (under 5,000 registered).

A text box on the figure explains the screening flag. Its wording, including
the Buncombe example for the first panel, is hard-coded and describes the
first pair. Re-check it if the data or the method changes.

Usage:  python plot_weekly_panels.py
Run diff_consec_wks.py first. The glob picks up every matching summary file, so
keep older or differently named copies out of output/ (for example in
output/old/) or a week will be drawn twice.

Limits: excess nets to about zero within each week, so this ranks counties
against the state, not against a "correct" number. Summing signed excess
hides one-week spikes (Cumberland, week of Oct 11 to Oct 18, +153.9, is not on
the chart). It assumes every voter is equally likely to be removed in every
county; age mix, student and mover churn, and batch timing can all create
excess. A screening flag, not a finding.
"""

from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
METRIC = "removal_rate_pct"   # or "excess"
TOP_N = 20

files = sorted(OUTPUT_DIR.glob("county_removal_summary_*.csv"))
if not files:
    raise SystemExit("No county_removal_summary_*.csv files found in output/")
weeks = {f.stem.replace("county_removal_summary_", ""): pd.read_csv(f) for f in files}

# Fixed county order: cumulative excess across all weeks (favors large counties)
RANK_BY = "excess"   # "excess" or "rate"
allw = pd.concat(weeks.values())
if RANK_BY == "excess":
    score = allw.groupby("county_desc")["excess"].sum()
else:
    g = allw.groupby("county_desc")[["removed", "prior_registered"]].sum()
    score = g["removed"] / g["prior_registered"]
order = score.nlargest(TOP_N).index.tolist()

labels = [c.title() for c in order]

fig, axes = plt.subplots(len(weeks), 1, figsize=(12, 3.2 * len(weeks)), sharex=True, sharey=True)
if len(weeks) == 1:
    axes = [axes]
H = fig.get_figheight()

ymax = 0
for ax, (tag, df) in zip(axes, weeks.items()):
    d = df.set_index("county_desc").reindex(order)
    ymax = max(ymax, d[METRIC].max())
    state_rate = df["removed"].sum() / df["prior_registered"].sum() * 100
    bars = ax.bar(range(len(order)), d[METRIC], color="#2a78d6")
    for bar, small in zip(bars, d["small_county"].fillna(False)):
        if small:
            bar.set_facecolor("#b4b2a9")
            bar.set_hatch("///")
    if METRIC == "removal_rate_pct":
        ax.axhline(state_rate, ls="--", lw=1, color="gray")

    top5 = set(d[METRIC].nlargest(5).index)
    for i, name in enumerate(order):
        val, n = d.loc[name, METRIC], int(d.loc[name, "removed"])
        label = f"{name.title()}  {n}" if name in top5 else str(n)
        ax.annotate(label, (i, val), xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", rotation=90,
                    fontsize=9 if name in top5 else 7)

    ax.margins(y=0.6)
    ax.set_title(tag.replace("_to_", "  to  "), fontsize=10, loc="left",
                 pad=70 if ax is axes[0] else 6)
    ax.set_ylabel("% removed" if METRIC == "removal_rate_pct" else "excess")
axes[0].set_ylim(0, ymax * 2.6)

axes[-1].set_xticks(range(len(order)))
axes[-1].set_xticklabels(labels, rotation=60, ha="right", fontsize=10)
top_ax = axes[0].secondary_xaxis("top")
top_ax.set_xticks(range(len(order)))
top_ax.set_xticklabels(labels, rotation=60, ha="left", fontsize=10)

if RANK_BY == "excess":
    head = "North Carolina counties with the most voter removals\nabove the statewide average rate"
    rank_line = "Ranked left to right by total extra removals over all weeks (removed minus expected)."
else:
    head = "North Carolina counties with the highest voter removal rates\nover all weeks"
    rank_line = "Ranked left to right by total removed / registered voters. Small counties can rank high on a few removals."
fig.suptitle(head, fontsize=13, y=1 - 0.1 / H, va="top")

tags = list(weeks)
first = tags[0].split("_to_")[0]
last = tags[-1].split("_to_")[1]
fig.text(0.5, 1 - 0.8 / H,
    f"{len(tags)} weekly comparisons, {first} to {last}.\n"
    f"{rank_line}\n"
    "Bar height = % of that county's registered voters removed that week. Number above bar = people removed.\n"
    "Dashed line = statewide rate. Hatched = small county (under 5,000 voters).",
    fontsize=10, ha="center", va="top")

fig.subplots_adjust(top=1 - 3.5 / H, bottom=2.85 / H, left=0.065, right=0.985, hspace=0.35)

fig.text(0.01, 0.1 / H,
    "Screening flag used\n"
    "Expected = county's registered voters x that week's statewide removal rate.\n"
    "Excess = actual removed - expected.\n"
    "Example (first panel): Buncombe, 223,448 registered x 0.025% = about 56 expected; 93 removed; excess = +37.\n"
    "The ranking sums excess over all weeks. It assumes every voter is equally likely to be removed in every county.\n"
    "However, age mix (deaths), student and mover churn, and batch timing\n"
    "can all create excess without any irregularity.\n"
    "Excess nets to about zero each week, so it ranks counties against the state, not against a 'correct' number.\n"
    "A county high across several weeks is more informative than one high week.\n"
    "Reason codes, not excess, give the 'why'.",
    fontsize=9, va="bottom", ha="left", linespacing=1.4,
    bbox=dict(boxstyle="round,pad=0.6", facecolor="#f6f1e0", edgecolor="#b4b2a9"))

out = OUTPUT_DIR / f"weekly_panels_{RANK_BY}.png"
# out = OUTPUT_DIR / "weekly_panels.png"
fig.savefig(out, dpi=150)
print("Saved", out)