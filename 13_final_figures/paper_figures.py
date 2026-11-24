"""
paper_figures.py - redraw the three figures from figN_summary.csv (no
re-simulation) in the shared style of ../figstyle.py: every plot square, major
and minor grid, the same fonts, legend, colors, markers and line styles as the
arrival-rate figures in ../15_rate_figures.

    python3 13_final_figures/paper_figures.py [output_dir]

Writes nsfnet_fig1_workload, nsfnet_fig2_threat and nsfnet_fig3_hysteresis
(.pdf and .png). Fig. 2 is one 3.5 x 3.5 in square. Figs. 1 and 3 stack two
square panels, (a) above (b), sharing the x axis, in one IEEE column
(3.5 in wide, same font scale as Fig. 2; use a single-column figure in LaTeX).
Error bars are 95% t-intervals over seeds.
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from figstyle import plt, figure, grid, line, legend, save, SQUARE  # noqa: E402

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


def stacked():
    """Two square axes stacked vertically in one 3.5 in column, sharing x.
    Margins are fixed (not tight_layout) so both plot areas line up exactly."""
    left, right, top, gap, bottom = 0.52, 0.08, 0.20, 0.24, 0.40   # inches
    side = SQUARE - left - right
    W, H = SQUARE, top + 2 * side + gap + bottom
    fig = plt.figure(figsize=(W, H))
    a1 = fig.add_axes([left / W, bottom / H, side / W, side / H])
    a0 = fig.add_axes([left / W, (bottom + side + gap) / H, side / W, side / H], sharex=a1)
    for a in (a0, a1):
        grid(a)
    a0.tick_params(labelbottom=False)
    return fig, [a0, a1]


def save_fixed(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"))
    plt.close(fig)


# ---------------------------------------------------------------- Fig. 1 workload
rows = load("fig1")
m1 = ["RASP-Fog", "SA-FF", "Static-Strong"]
fig, ax = stacked()
for m in m1:
    line(ax[0], m, *series(rows, m, "secure_pct"))
    line(ax[1], m, *series(rows, m, "sec_cpu_pct"))
ax[0].set_ylabel("Secure completion (%)")
ax[1].set_ylabel("Security-only fog CPU (%)")
ax[1].set_xlabel("Arrival rate (requests/s)")   # shared x axis
ax[0].set_title("(a)", pad=2)
ax[1].set_title("(b)", pad=2)
legend(ax[0], "lower left")       # one legend for both panels
save_fixed(fig, "nsfnet_fig1_workload")

# ---------------------------------------------------------------- Fig. 2 threat
# At p_up = 0 the threat never rises, no session needs a mandatory upgrade, and
# the termination rate is 0/0. That point is not plotted.
rows = load("fig2")
fig, ax = figure()
for m in ["RASP-Fog", "RASP-Reloc", "RASP-Profile", "SA-FF"]:
    x, y, ci = series(rows, m, "sec_term_pct")
    keep = [i for i, v in enumerate(x) if v > 0]
    line(ax, m, [x[i] for i in keep], [y[i] for i in keep], [ci[i] for i in keep])
ax.set_xlim(0, 0.63)
ax.set_ylim(0, 9)
ax.set_xticks([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
ax.set_xlabel("Threat-increase probability")
ax.set_ylabel("Security-triggered termination (%)")
legend(ax, "upper left")
save(fig, OUT, "nsfnet_fig2_threat")

# ---------------------------------------------------------------- Fig. 3 hysteresis
rows = load("fig3")
fig, ax = stacked()
line(ax[0], "RASP-Fog", *series(rows, "RASP-Fog", "changes_per_1000"))
line(ax[1], "RASP-Fog", *series(rows, "RASP-Fog", "sec_cpu_pct"))
ax[0].set_ylabel("Changes per 1,000 sessions")
ax[1].set_ylabel("Security-only fog CPU (%)")
ax[1].set_xlabel(r"Holding interval $\tau_H$ (s)")   # shared x axis
ax[1].set_xticks([0, 4, 8, 16, 32])
ax[0].set_title("(a)", pad=2)
ax[1].set_title("(b)", pad=2)
save_fixed(fig, "nsfnet_fig3_hysteresis")
print("wrote figures to", OUT)
