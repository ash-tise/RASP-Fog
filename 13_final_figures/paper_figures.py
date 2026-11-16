"""
paper_figures.py - redraw the three figures from figN_summary.csv at IEEE
one-column size (no re-simulation), in the shared style of ../figstyle.py
(the same colors, markers and line styles as the arrival-rate figures in
../15_rate_figures).

    python3 13_final_figures/paper_figures.py [output_dir]

Writes nsfnet_fig1_workload.pdf, nsfnet_fig2_threat.pdf and
nsfnet_fig3_hysteresis.pdf (plus .png). Fig. 1 is one column with panels stacked (nsfnet_fig1_workload_wide is the
side-by-side 8.4 x 3.3 in alternative, scaled into the column in LaTeX); Fig. 2 is 4.2 x 3.3 in scaled into the column; Fig. 3 is 3.5 in, stacked. Error bars are 95% t-intervals over seeds.
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from figstyle import plt, COLUMN_W, line, legend, save  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else HERE


def load(fig):
    with open(os.path.join(HERE, f"{fig}_summary.csv")) as f:
        return list(csv.DictReader(f))


def series(rows, method, key):
    """x, mean and CI half-width for one method; NaN means (undefined) dropped."""
    rs = sorted((r for r in rows if r["method"] == method), key=lambda r: float(r["x"]))
    rs = [r for r in rs if r[key] not in ("", "nan")]
    return ([float(r["x"]) for r in rs], [float(r[key]) for r in rs],
            [float(r[key + "_ci"]) if r[key + "_ci"] not in ("", "nan") else 0 for r in rs])


# ---------------------------------------------------------------- Fig. 1 workload
rows = load("fig1")
m1 = ["RASP-Fog", "SA-FF", "Static-Strong"]
# Same geometry as the report's original Fig. 2: drawn at 8.4 x 3.3 in with
# 10 pt text, then scaled to the column width by \includegraphics.
BIG = {"font.size": 10, "axes.labelsize": 10, "axes.titlesize": 10,
       "legend.fontsize": 8, "xtick.labelsize": 9, "ytick.labelsize": 9,
       "lines.markersize": 4.5, "lines.linewidth": 1.4, "axes.linewidth": 0.9,
       "xtick.major.width": 0.8, "ytick.major.width": 0.8, "grid.linewidth": 0.6}
with plt.rc_context(BIG):
    fig, ax = plt.subplots(1, 2, figsize=(8.4, 3.3))
    for m in m1:
        line(ax[0], m, *series(rows, m, "secure_pct"))
        line(ax[1], m, *series(rows, m, "sec_cpu_pct"))
    ax[0].set_ylabel("Secure completion (%)")
    ax[1].set_ylabel("Security-only fog CPU (%)")
    for a in ax:
        a.set_xlabel("Arrival rate (requests/s)")
    ax[0].set_title("(a)")
    ax[1].set_title("(b)")
    legend(ax[0], "lower left")       # one legend for both panels
    save(fig, OUT, "nsfnet_fig1_workload_wide")   # side-by-side alternative

# Default: one column, panels stacked, true 8 pt text (same layout as Fig. 3 here).
fig, ax = plt.subplots(2, 1, figsize=(COLUMN_W, 4.0), sharex=True)
for m in m1:
    line(ax[0], m, *series(rows, m, "secure_pct"))
    line(ax[1], m, *series(rows, m, "sec_cpu_pct"))
ax[0].set_ylabel("Secure completion (%)")
ax[1].set_ylabel("Security-only fog CPU (%)")
ax[1].set_xlabel("Arrival rate (requests/s)")
ax[0].set_title("(a)", pad=2)
ax[1].set_title("(b)", pad=2)
legend(ax[0], "lower left")
save(fig, OUT, "nsfnet_fig1_workload")

# ---------------------------------------------------------------- Fig. 2 threat
# At p_up = 0 the threat never rises, no session needs a mandatory upgrade, and
# the termination rate is 0/0. That point is not plotted.
rows = load("fig2")
# Same geometry as the report's original Fig. 3: 4.2 x 3.3 in, scaled to the column.
with plt.rc_context(BIG):
    fig, ax = plt.subplots(figsize=(4.2, 3.3))
    for m in ["RASP-Fog", "RASP-Reloc", "RASP-Profile", "SA-FF"]:
        x, y, ci = series(rows, m, "sec_term_pct")
        keep = [i for i, v in enumerate(x) if v > 0]
        line(ax, m, [x[i] for i in keep], [y[i] for i in keep], [ci[i] for i in keep])
    ax.set_xlim(0, 0.63)
    ax.set_ylim(0, 9)
    ax.set_xticks([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    ax.set_xlabel("Threat-increase probability")
    ax.set_ylabel("Security-triggered termination (%)")
    legend(ax, "upper left", ncol=2)
    save(fig, OUT, "nsfnet_fig2_threat")

# ---------------------------------------------------------------- Fig. 3 hysteresis
rows = load("fig3")
fig, ax = plt.subplots(2, 1, figsize=(COLUMN_W, 4.0), sharex=True)   # same size as Fig. 1
line(ax[0], "RASP-Fog", *series(rows, "RASP-Fog", "changes_per_1000"))
line(ax[1], "RASP-Fog", *series(rows, "RASP-Fog", "sec_cpu_pct"))
ax[0].set_ylabel("Changes per 1,000 sessions")
ax[1].set_ylabel("Security-only fog CPU (%)")
ax[1].set_xlabel(r"Holding interval $\tau_H$ (s)")
ax[1].set_xticks([0, 2, 4, 8, 16, 32])
ax[0].set_title("(a)", pad=2)
ax[1].set_title("(b)", pad=2)
save(fig, OUT, "nsfnet_fig3_hysteresis")
print("wrote figures to", OUT)
