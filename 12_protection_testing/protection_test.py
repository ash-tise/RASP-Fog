"""
protection_test.py - sensitivity of the NSFNET results to deadline protection.

Run it from the repository root:   python3 12_protection_testing/protection_test.py

rasp_nsfnet.py only allows a placement (admission, upgrade or relocation) if
every request already on the node still meets its deadline at the new CPU
utilization (PROTECT = True). This test reruns the load sweep of
10_nsfnet_load_testing with that rule on and off. With it off, Algorithm 1 and
2 check only the request being placed, so later placements can push running
requests past their deadlines; those requests count as runtime SLA misses and
are not secure-and-on-time completions.

Writes protection_results.csv and fig_protection.png.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "10_nsfnet_load_testing"))
import nsfnet_load_test as base

# ---------------------------------------------------------------- settings
RATES = [12, 16, 20, 24, 28, 32, 36, 40]
POLICIES = ["RASP-Fog", "No-Relocation", "Static-Strong"]
SEEDS = base.SEEDS


def plot(rows):
    fig, ax = base.axes("Arrival rate (requests/s)", "Secure and on-time completion (%)")
    for protect, style, suffix in ((True, "-", "protected"), (False, "--", "unprotected")):
        sub = [r for r in rows if r["protect"] == protect]
        for name in ("RASP-Fog", "Static-Strong"):
            pts = sorted((r for r in sub if r["policy"] == name), key=lambda r: r["rate"])
            ax.errorbar([r["rate"] for r in pts], [r["secure_pct"] for r in pts],
                        yerr=[r["secure_pct_ci"] for r in pts], label=f"{name}, {suffix}",
                        color=base.COLORS[name], marker=base.MARKERS[name], markersize=5,
                        linewidth=2, linestyle=style, capsize=3)
    # error-bar legend handles drop the line style, so draw the key explicitly
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=base.COLORS[name], marker=base.MARKERS[name], markersize=5,
                      linewidth=2, linestyle=style, label=f"{name}, {suffix}")
               for style, suffix in (("-", "protected"), ("--", "unprotected"))
               for name in ("RASP-Fog", "Static-Strong")]
    ax.legend(handles=handles, frameon=False, loc="lower left", handlelength=3.5)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_protection.png"))


if __name__ == "__main__":
    print(f"Deadline-protection test: rates {RATES} req/s, seeds {SEEDS}, "
          f"threat p_up {base.P_UP}\n")
    tasks = [(p, rate, s, base.P_UP, protect) for protect in (True, False)
             for rate in RATES for s in SEEDS for p in POLICIES]
    runs = base.run_grid(tasks)
    rows = base.summarize(runs, ("protect", "policy", "rate"))
    base.write_csv(rows, os.path.join(HERE, "protection_results.csv"))

    cols = [("secure_pct", "secure %"), ("rejected_pct", "rejected %"),
            ("sla_miss_pct", "runtime SLA miss %"), ("dropped_pct", "dropped %"),
            ("moves", "relocations"), ("fog_util_pct", "fog CPU %")]
    for protect in (True, False):
        for name in POLICIES:
            print(f"{name}, protection {'on' if protect else 'off'}")
            print(f"  {'rate':>4} " + "".join(f"{label:>20}" for _, label in cols))
            for r in sorted((r for r in rows if r["protect"] == protect and r["policy"] == name),
                            key=lambda r: r["rate"]):
                print(f"  {r['rate']:>4} " + "".join(
                    f"{r[k]:>13.2f} ± {r[k + '_ci']:<4.2f}" for k, _ in cols))
            print()

    by = {(r["protect"], r["policy"], r["rate"], r["seed"]): r for r in runs}
    print("Paired difference RASP-Fog - baseline in secure completion (points, 95% CI)")
    print(f"  {'rate':>4} " + "".join(f"{p + (', on' if pr else ', off'):>22}"
                                      for pr in (True, False) for p in POLICIES[1:]))
    for rate in RATES:
        cells = []
        for pr in (True, False):
            for p in POLICIES[1:]:
                m, ci = base.mean_ci([by[(pr, "RASP-Fog", rate, s)]["secure_pct"]
                                      - by[(pr, p, rate, s)]["secure_pct"] for s in SEEDS])
                cells.append(f"{m:>+14.2f} ± {ci:<5.2f}")
        print(f"  {rate:>4} " + "".join(cells))

    try:
        plot(rows)
        print("\nWrote protection_results.csv and fig_protection.png.")
    except ImportError:
        print("\nWrote protection_results.csv (install matplotlib for the figure).")
