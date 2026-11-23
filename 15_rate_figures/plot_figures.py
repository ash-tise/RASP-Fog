"""
plot_figures.py - draw the four arrival-rate figures from the stored results
(no re-simulation), as square plots in the shared style of ../figstyle.py
(3.5 x 3.5 in per plot, 8 pt fonts, major and minor grid).

    python3 15_rate_figures/plot_figures.py [output_dir]

Writes rate_fig_secure, rate_fig_sec_term, rate_fig_delay and rate_fig_changes
(.pdf and .png) in the shared style of ../figstyle.py. Error bars are 95%
t-intervals over the seeds. The secure-completion figure has a second square
panel, side by side with the first (two-column width), with each adaptive
method's paired gain over Static-Strong, because the absolute curves sit within
~1.5 points.
"""
import csv
import os
import sys

import exp_config as cfg  # noqa: E402  (also puts the repo root on sys.path)
from figstyle import plt, STYLE, legend  # noqa: E402,F401
import figstyle  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else HERE

METHODS = ["RASP-Fog", "SA-FF", "RASP-Profile", "RASP-Reloc", "Static-Strong"]
XLABEL = "Arrival rate (requests/s)"
KNEE = 18                      # saturation onset from the pilot (README)


def load(name):
    with open(os.path.join(HERE, name)) as f:
        return list(csv.DictReader(f))


def series(rows, method, key, nan_as_zero=False):
    rs = sorted((r for r in rows if r["method"] == method), key=lambda r: float(r["rate"]))
    fix = (lambda v: 0.0 if v != v else v) if nan_as_zero else (lambda v: v)
    return ([float(r["rate"]) for r in rs], [fix(float(r[key])) for r in rs],
            [fix(float(r[key + "_ci"])) for r in rs])


# The line passes through every simulated rate; markers and error bars are drawn
# only at these, so the dense knee sampling does not crowd the figure.
MARKED = {4, 8, 12, 16, 18, 20, 22, 24, 28, 32, 40, 48}


def line(ax, m, x, y, ci):
    figstyle.line(ax, m, x, y, ci, marked=MARKED)


def axes_style(ax, ylabel, xlabel=True):
    ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(XLABEL)
    ax.set_xlim(2, 50)
    ax.axvline(KNEE, color="0.6", lw=0.7, ls=":", zorder=0)


def save(fig, name):
    figstyle.save(fig, OUT, name)


def secure(summary, raw):
    fig, (a, b) = figstyle.figure(2)
    for m in METHODS:
        line(a, m, *series(summary, m, "secure_pct"))
    axes_style(a, "Secure completion (%)")
    a.set_title("(a)", pad=2)
    # (b) paired gain over Static-Strong, per seed
    by = {(r["method"], int(r["rate"]), int(r["seed"])): float(r["secure_pct"]) for r in raw}
    for m in METHODS[:-1]:
        x, y, ci = [], [], []
        for rate in cfg.RATES:
            mu, hw, _ = cfg.mean_ci([by[(m, rate, s)] - by[("Static-Strong", rate, s)]
                                     for s in cfg.SEEDS])
            x.append(rate), y.append(mu), ci.append(0 if hw != hw else hw)
        line(b, m, x, y, ci)
    b.axhline(0, color=STYLE["Static-Strong"][0], lw=1.0, ls=STYLE["Static-Strong"][2])
    axes_style(b, "Gain over Static-Strong\n(percentage points)")
    b.text(KNEE - 0.5, 1.95, "saturation", ha="right", va="top", fontsize=6.5, color="0.4")
    b.set_title("(b)", pad=2)
    legend(a, "lower left")
    save(fig, "rate_fig_secure")


def single(summary, key, ylabel, name, loc, after=None, nan_zero=(), labels=None):
    """nan_zero: methods whose NaN values are drawn as 0; labels: legend overrides."""
    fig, ax = figstyle.figure()
    labels = labels or {}
    for m in METHODS:
        figstyle.line(ax, m, *series(summary, m, key, nan_as_zero=m in nan_zero),
                      marked=MARKED, label=labels.get(m))
    axes_style(ax, ylabel)
    legend(ax, loc)
    if after:                  # may replace the legend placement
        after(ax)
    save(fig, name)


def changes_labels(ax):
    ax.set_ylim(-50, 1300)
    legend(ax, "lower left", bbox_to_anchor=(0.0, 0.08))
    ax.text(49, 1170, r"no hysteresis ($\tau_H$ = 0)", ha="right", fontsize=6.5, color="0.3")
    ax.text(49, 750, r"hysteresis ($\tau_H$ = 8 s)", ha="right", fontsize=6.5, color="0.3")
    ax.text(49, 50, "fixed profile", ha="right", fontsize=6.5, color="0.3")


def sec_term(summary):
    # Static-Strong never upgrades, so its termination rate has no denominator
    # (NaN in the CSVs); it is 0 by construction and drawn as 0.
    single(summary, "sec_term_pct", "Security-triggered\ntermination (%)", "rate_fig_sec_term",
           "upper left", nan_zero=("Static-Strong",),
           labels={"Static-Strong": "Static-Strong\n(0 by construction)"},
           after=lambda ax: ax.set_ylim(-0.4, 9.2))   # headroom so the legend clears the curves


if __name__ == "__main__":
    summary, raw = load("rate_summary.csv"), load("rate_raw.csv")
    secure(summary, raw)
    sec_term(summary)
    single(summary, "mean_delay", "Mean end-to-end delay (ms)", "rate_fig_delay", "lower right")
    single(summary, "changes_per_1000", "Profile changes\nper 1,000 admitted",
           "rate_fig_changes", "lower left", changes_labels)
    print("wrote figures to", OUT)
