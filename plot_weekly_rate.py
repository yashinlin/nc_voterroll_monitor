"""Weekly panel chart of county voter removals, ranked by overall removal rate.

Same code as plot_weekly_panels.py with RANK_BY = "rate" and the screening
text box removed. Reads every output/county_removal_summary_*.csv (aggregate
counts, no PII) and writes output/weekly_panels_rate.png.

Ranking: total removed / total prior registered over all weeks shown (the
simple-rate approach Michael suggested). Bars show % of the county's registered
voters removed that week. Numbers above bars are people removed; the 5 tallest
bars per panel carry the county name. Dashed line = statewide rate; hatched =
small county (under 5,000 registered).

Usage:  python plot_weekly_rate.py
Run diff_consec_wks.py first. Keep older or differently named summary files out
of output/ or a week will be drawn twice.

Limits: a rate ranking favors small counties, where a few removals move the
rate a lot (many top-20 bars here are 1 to 6 people). It does not say whether
a rate is unusual for the county's size. Use it next to the excess chart, not
instead of it. It cannot show batch timing, notice, or process.
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
RANK_BY = "rate"   # "excess" or "rate"
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


out = OUTPUT_DIR / f"weekly_panels_{RANK_BY}.png"
# out = OUTPUT_DIR / "weekly_panels.png"
fig.savefig(out, dpi=150)
print("Saved", out)