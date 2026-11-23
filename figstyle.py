"""
figstyle.py - one plotting style for every paper figure.

SciencePlots "science" + "ieee" (no LaTeX), Times New Roman, square plot areas,
a major and minor grid, a framed legend inside the axes, and one fixed color,
marker and line style per method, so a method looks the same in every figure.
Import it before creating figures:

    from figstyle import plt, STYLE, figure, line, legend, save

Every axes is square (set_box_aspect(1)). A single plot is SQUARE x SQUARE in
(one IEEE column); a row of n panels is n squares side by side, at most the
IEEE two-column width.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import AutoMinorLocator  # noqa: E402
import scienceplots  # noqa: E402,F401  registers the "science" styles

plt.style.use(["science", "ieee", "no-latex"])
plt.rcParams.update({"font.family": "serif",
                     "font.serif": ["Times New Roman", "Times", "Liberation Serif"],
                     "mathtext.fontset": "stix", "pdf.fonttype": 42,
                     "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
                     "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
                     "lines.linewidth": 1.0, "lines.markersize": 3.6,
                     "axes.linewidth": 0.6, "savefig.dpi": 600,
                     "xtick.minor.visible": True, "ytick.minor.visible": True,
                     "axes.grid": True, "axes.grid.which": "both", "axes.axisbelow": True})

# Paul Tol "muted" colors; each method also has its own marker and dash,
# so the curves stay distinct in grayscale print.
STYLE = {"RASP-Fog":      ("#332288", "o", "-"),
         "SA-FF":         ("#CC6677", "s", (0, (4, 1.5))),
         "LA":            ("#DDAA33", "p", (0, (6, 1.5, 1, 1.5))),
         "LB":            ("#117733", "h", (0, (1, 1.2))),
         "RASP-Profile":  ("#999933", "v", (0, (1, 1))),
         "RASP-Reloc":    ("#882255", "D", (0, (4, 1.2, 1, 1.2))),
         "Static-Strong": ("#44AA99", "^", (0, (2, 1.2)))}

LABEL = {"LA": "LA (latency-aware)", "LB": "LB (load-aware)"}

SQUARE = 3.5       # side of one square plot = IEEE single-column width (in)
COLUMN_W = SQUARE
DOUBLE_W = 7.16    # IEEE two-column width (in)


def grid(ax):
    """Clean major grid plus a fainter minor grid, behind the data."""
    ax.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))
    ax.grid(True, which="major", color="0.82", lw=0.5, ls="-")
    ax.grid(True, which="minor", color="0.92", lw=0.4, ls=":")
    ax.set_axisbelow(True)


def figure(n=1, side=None):
    """A figure with n square axes in one row. Returns (fig, ax) for n = 1,
    else (fig, [axes])."""
    side = side or (SQUARE if n == 1 else min(SQUARE, DOUBLE_W / n))
    fig, axes = plt.subplots(1, n, figsize=(side * n, side))
    axes = [axes] if n == 1 else list(axes)
    for ax in axes:
        ax.set_box_aspect(1)
        grid(ax)
    return (fig, axes[0]) if n == 1 else (fig, axes)


def line(ax, m, x, y, ci, marked=None, label=None):
    """Line through all points; hollow markers and thin 95% CI bars at the
    x values in `marked` (all points if None)."""
    c, mk, ls = STYLE[m]
    keep = [i for i, v in enumerate(x) if marked is None or v in marked]
    ax.plot(x, y, color=c, ls=ls, marker=mk, label=label or LABEL.get(m, m),
            markerfacecolor="white", markeredgewidth=0.8, markevery=keep)
    ax.errorbar([x[i] for i in keep], [y[i] for i in keep], yerr=[ci[i] for i in keep],
                color=c, ls="none", elinewidth=0.5, capsize=1.2, capthick=0.5)


def legend(ax, loc, **kw):
    """Framed legend inside the axes, in a corner the curves leave empty."""
    opts = dict(frameon=True, fancybox=False, framealpha=1, edgecolor="0.0",
                handlelength=2.8, borderpad=0.4, labelspacing=0.3)
    opts.update(kw)
    leg = ax.legend(loc=loc, **opts)
    leg.get_frame().set_linewidth(0.5)
    return leg


def save(fig, out_dir, name):
    fig.tight_layout(pad=0.3)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(out_dir, f"{name}.{ext}"))
    plt.close(fig)
