"""Charts removals by recorded reason, by week.

Reads output/reason_counts_by_county_week.csv only (aggregate counts, no PII)
and writes output/reasons_by_week.png: stacked bars of people removed per week,
plus the weekly share for deceased and the three 'moved' categories.

The grouping is ours, not an official one (see GROUP): Felony = RF + RR; Other =
administrative, duplicate, noncitizen, inactive after 2 federal elections, old
purge law. Codes missing from GROUP stop the script on purpose.

Usage:  python plot_reasons.py
Run reason_counts.py first.

Limits: reason is the category recorded in the file, not proof of how or
why a removal happened.
"""

from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
agg = pd.read_csv(OUTPUT_DIR / "reason_counts_by_county_week.csv")

GROUP = {
    "RD": "Deceased", "RL": "Moved from county", "RS": "Moved from state",
    "RH": "Moved within state", "RF": "Felony", "RR": "Felony", "RQ": "Voter request",
    "RA": "Other", "R2": "Other", "RN": "Other", "RM": "Other", "RP": "Other",
}
ORDER = ["Deceased", "Moved from county", "Moved from state", "Moved within state",
         "Felony", "Voter request", "Other"]
COLORS = ["#2a78d6", "#eb6834", "#f2b134", "#7aa6d6", "#6b6b6b", "#59a869", "#b4b2a9"]

agg["group"] = agg["reason_cd"].map(GROUP)
assert agg["group"].notna().all(), "unmapped reason code"

wk = agg.groupby(["week_end", "group"])["removed"].sum().unstack(fill_value=0)[ORDER]
totals = wk.sum(axis=1)
share = wk.div(totals, axis=0) * 100
print(wk.assign(total=totals).to_string())

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 9), sharex=True)
wk.plot(kind="bar", stacked=True, ax=ax1, color=COLORS, width=0.75)
ax1.tick_params(axis="x", labelbottom=True)
ax1.set_xticklabels(wk.index, rotation=45, ha="right")
ax1.set_xlabel("Week ending (NCSBE release date)")
ax1.set_ylabel("People removed")
ax1.set_title("Voters removed from NC rolls each week, by recorded reason", fontsize=13, loc="left")
for i, t in enumerate(totals):
    ax1.annotate(str(t), (i, t), xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9)
ax1.legend(fontsize=9, ncol=4, loc="upper left", frameon=False)
ax1.margins(y=0.3)

for g, c in zip(ORDER, COLORS):
    if g in ("Deceased", "Moved from county", "Moved from state", "Moved within state"):
        ax2.plot(range(len(share)), share[g], marker="o", color=c, label=g)
ax2.set_ylabel("% of that week's removals")
ax2.set_xticks(range(len(share)))
ax2.set_xticklabels(share.index, rotation=45, ha="right")
ax2.set_xlabel("Week ending (NCSBE release date)")
ax2.legend(fontsize=9, frameon=False)
ax2.set_title("Share of weekly removals: deceased and the three 'moved' categories", fontsize=11, loc="left")

fig.text(0.01, 0.005,
    "Reason = the category recorded in the NCSBE file. It does not show how the process ran, whether notice was given, "
    "or when in the week a removal happened.\nGrouping is ours: Felony = RF + RR; Other = administrative, duplicate, "
    "noncitizen, inactive after 2 federal elections, old purge law.",
    fontsize=8, va="bottom")
fig.tight_layout(rect=[0, 0.05, 1, 1])
out = OUTPUT_DIR / "reasons_by_week.png"
fig.savefig(out, dpi=150)
print("Saved", out)
