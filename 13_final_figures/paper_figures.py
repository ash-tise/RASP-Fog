"""
paper_figures.py - redraw the three figures from figN_summary.csv at IEEE
two-column print sizes (no re-simulation).

    python3 13_final_figures/paper_figures.py [output_dir]

Writes nsfnet_fig1_workload.pdf, nsfnet_fig2_threat.pdf and
nsfnet_fig3_hysteresis.pdf (plus .png). Fig. 1 is sized for a
full-width figure* (7.16 in); Fig. 2 and Fig. 3 (panels stacked) for one column (3.5 in). Fonts are 8 pt.
"""
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else HERE

plt.rcParams.update({"font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
                     "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
                     "lines.linewidth": 1.2, "lines.markersize": 3.5, "pdf.fonttype": 42})

STYLE = {"RASP-Fog": ("#1f77b4", "o", "-"), "SA-FF": ("#ff7f0e", "s", "--"),
         "Static-Strong": ("#2ca02c", "^", ":"), "RASP-Reloc": ("#9467bd", "D", "-."),
         "RASP-Profile": ("#d62728", "v", "--")}


def load(fig):
    with open(os.path.join(HERE, f"{fig}_summary.csv")) as f:
        return list(csv.DictReader(f))


def series(rows, method, key):
    rs = sorted((r for r in rows if r["method"] == method), key=lambda r: float(r["x"]))
    return ([float(r["x"]) for r in rs], [float(r[key]) for r in rs],
            [float(r[key + "_ci"]) for r in rs])


def draw(ax, rows, methods, key, xlabel, ylabel, tag=None):
    for m in methods:
        x, y, ci = series(rows, m, key)
        c, mk, ls = STYLE[m]
        ax.errorbar(x, y, yerr=ci, color=c, marker=mk, ls=ls, capsize=2, elinewidth=0.8, label=m)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if tag:
        ax.set_title(tag, pad=3)
    ax.grid(alpha=0.3, lw=0.5)


def save(fig, name):
    fig.tight_layout(pad=0.4, w_pad=1.5)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), dpi=300)
    plt.close(fig)


rows = load("fig1")
m1 = ["RASP-Fog", "SA-FF", "Static-Strong"]
fig, ax = plt.subplots(1, 2, figsize=(7.16, 2.25))
draw(ax[0], rows, m1, "secure_pct", "Arrival rate (requests/s)", "Secure completion (%)", "(a)")
draw(ax[1], rows, m1, "sec_cpu_pct", "Arrival rate (requests/s)", "Security-only fog CPU (%)", "(b)")
ax[0].legend(loc="lower left")
save(fig, "nsfnet_fig1_workload")

rows = load("fig2")
fig, ax = plt.subplots(figsize=(3.5, 2.3))
draw(ax, rows, ["RASP-Fog", "RASP-Reloc", "RASP-Profile", "SA-FF"], "sec_term_pct",
     "Threat-increase probability", "Security-triggered termination (%)")
ax.legend(loc="upper left", ncol=2)
ax.set_ylim(bottom=-0.3, top=9)
save(fig, "nsfnet_fig2_threat")

rows = load("fig3")
fig, ax = plt.subplots(2, 1, figsize=(3.5, 3.6))
draw(ax[0], rows, ["RASP-Fog"], "changes_per_1000", r"Holding interval $\tau_H$ (s)",
     "Changes per 1,000 sessions", "(a)")
draw(ax[1], rows, ["RASP-Fog"], "sec_cpu_pct", r"Holding interval $\tau_H$ (s)",
     "Security-only fog CPU (%)", "(b)")
for a in ax:
    a.set_xticks([0, 2, 4, 8, 16, 32])
save(fig, "nsfnet_fig3_hysteresis")
print("wrote figures to", OUT)
