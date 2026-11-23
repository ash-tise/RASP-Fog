"""
plot_baselines.py - draw the placement-baseline figures from the stored results
(no re-simulation), square plots in the shared style of ../figstyle.py.

    python3 16_placement_baselines/plot_baselines.py [output_dir]

For each capacity scenario (nominal, constrained):
    base_<scenario>_secure  (a) secure completion, (b) RASP-Fog minus each
                            baseline, paired by seed (percentage points)
    base_<scenario>_delay   (a) mean end-to-end delay, (b) share of arrivals
                            placed in the cloud
Two square panels side by side (IEEE two-column width). Error bars are 95%
t-intervals over the 25 seeds.
"""
import csv
import os
import sys

import baseline_config as cfg  # noqa: E402  (puts 15_rate_figures and the repo root on sys.path)
import figstyle  # noqa: E402
from figstyle import STYLE, legend  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else cfg.HERE
XLABEL = "Arrival rate (requests/s)"
KNEE = {"nominal": 18, "constrained": 9}
MARKED = {"nominal": {4, 8, 12, 16, 18, 20, 22, 24, 28, 32, 40, 48},
          "constrained": {2, 4, 6, 8, 9, 10, 11, 12, 14, 16, 20, 24}}
TITLE = {"nominal": "Nominal capacity", "constrained": "Constrained fog and cloud"}


def load(name):
    with open(os.path.join(cfg.HERE, name)) as f:
        return list(csv.DictReader(f))


def series(rows, sc, key, method=None, vs=None):
    rs = [r for r in rows if r["scenario"] == sc
          and (method is None or r.get("method") == method) and (vs is None or r.get("vs") == vs)]
    rs.sort(key=lambda r: float(r["rate"]))
    f = lambda v: 0.0 if v in ("", "nan") else float(v)   # noqa: E731
    return [float(r["rate"]) for r in rs], [f(r[key]) for r in rs], [f(r[key + "_ci"]) for r in rs]


def style(ax, sc, ylabel):
    ax.set_xlabel(XLABEL)
    ax.set_ylabel(ylabel)
    ax.axvline(KNEE[sc], color="0.6", lw=0.7, ls=":", zorder=0)


def secure(summary, paired, sc):
    fig, (a, b) = figstyle.figure(2)
    for m in cfg.METHODS:
        figstyle.line(a, m, *series(summary, sc, "secure_pct", method=m), marked=MARKED[sc])
    style(a, sc, "Secure completion (%)")
    legend(a, "lower left")
    for m in cfg.METHODS[1:]:
        figstyle.line(b, m, *series(paired, sc, "secure_pct", vs=m), marked=MARKED[sc],
                      label=f"vs {figstyle.LABEL.get(m, m)}")
    b.axhline(0, color="0.2", lw=0.6)
    style(b, sc, "RASP-Fog gain (percentage points)")
    legend(b, "lower left")
    a.set_title(f"(a) {TITLE[sc]}", pad=2)
    b.set_title("(b) RASP-Fog minus baseline, paired", pad=2)
    figstyle.save(fig, OUT, f"base_{sc}_secure")


def delay(summary, sc):
    fig, (a, b) = figstyle.figure(2)
    for m in cfg.METHODS:
        figstyle.line(a, m, *series(summary, sc, "mean_delay", method=m), marked=MARKED[sc])
        figstyle.line(b, m, *series(summary, sc, "cloud_pct", method=m), marked=MARKED[sc])
    style(a, sc, "Mean end-to-end delay (ms)")
    style(b, sc, "Requests placed in the cloud (%)")
    legend(a, "lower right")
    a.set_title(f"(a) {TITLE[sc]}", pad=2)
    b.set_title("(b) Cloud offloading", pad=2)
    figstyle.save(fig, OUT, f"base_{sc}_delay")


if __name__ == "__main__":
    summary, paired = load("baselines_summary.csv"), load("baselines_paired.csv")
    for sc in cfg.SCENARIOS:
        secure(summary, paired, sc)
        delay(summary, sc)
    print("wrote figures to", OUT)
