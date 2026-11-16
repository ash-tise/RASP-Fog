"""
figstyle.py - one plotting style for every paper figure.

SciencePlots "science" + "ieee" (no LaTeX), Times New Roman, a light grid, and one
fixed color, marker and line style per method, so a method looks the same in
every figure. Import it before creating figures:

    from figstyle import plt, STYLE, line, legend, save
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import scienceplots  # noqa: E402,F401  registers the "science" styles

plt.style.use(["science", "ieee", "no-latex"])
plt.rcParams.update({"font.family": "serif",
                     "font.serif": ["Times New Roman", "Times"],
                     "mathtext.fontset": "stix", "pdf.fonttype": 42,
                     "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
                     "legend.fontsize": 7, "xtick.labelsize": 7, "ytick.labelsize": 7,
                     "lines.linewidth": 0.9, "lines.markersize": 3.2,
                     "axes.grid": True, "grid.color": "0.9", "grid.linewidth": 0.4,
                     "grid.linestyle": "-", "savefig.dpi": 600,
                     "xtick.minor.visible": False, "ytick.minor.visible": False})

# Paul Tol "muted" colors; each method also has its own marker and dash,
# so the curves stay distinct in grayscale print.
STYLE = {"RASP-Fog":      ("#332288", "o", "-"),
         "SA-FF":         ("#CC6677", "s", (0, (4, 1.5))),
         "RASP-Profile":  ("#999933", "v", (0, (1, 1))),
         "RASP-Reloc":    ("#882255", "D", (0, (4, 1.2, 1, 1.2))),
         "Static-Strong": ("#44AA99", "^", (0, (2, 1.2)))}

COLUMN_W = 3.5     # IEEE single-column width (in)


def line(ax, m, x, y, ci, marked=None, label=None):
    """Thin line through all points; hollow markers and thin 95% CI bars at the
    x values in `marked` (all points if None)."""
    c, mk, ls = STYLE[m]
    keep = [i for i, v in enumerate(x) if marked is None or v in marked]
    ax.plot(x, y, color=c, ls=ls, marker=mk, label=label or m, markerfacecolor="white",
            markeredgewidth=0.7, markevery=keep)
    ax.errorbar([x[i] for i in keep], [y[i] for i in keep], yerr=[ci[i] for i in keep],
                color=c, ls="none", elinewidth=0.5, capsize=1.2, capthick=0.5)


def legend(ax, loc, **kw):
    """Legend inside the axes, in a corner the curves leave empty."""
    opts = dict(frameon=True, fancybox=False, framealpha=1, edgecolor="0.3",
                handlelength=2.8, borderpad=0.4, labelspacing=0.25)
    opts.update(kw)
    leg = ax.legend(loc=loc, **opts)
    leg.get_frame().set_linewidth(0.4)
    return leg


def save(fig, out_dir, name):
    fig.tight_layout(pad=0.3)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(out_dir, f"{name}.{ext}"))
    plt.close(fig)
