"""
nsfnet_load_test.py - RASP-Fog on NSFNET as the arrival rate approaches and
passes saturation, under a dynamic regional threat.

Run it from the repository root:   python3 10_nsfnet_load_testing/nsfnet_load_test.py

Model: ../rasp_nsfnet.py (14 fog nodes, 21 links, random ingress, elastic cloud,
queueing that grows steeply with CPU utilization, four request classes,
sessions of 10-40 s, one threat level per region). For each seed the threat
trace is the same at every arrival rate, and within a run every policy sees the
same sessions. Results are the mean over SEEDS with a 95% t-interval.

Writes load_results.csv, fig_nsfnet_secure_completion.png and
fig_nsfnet_security_cpu.png (the figures need matplotlib).
The helpers here are reused by 11_attack_intensity_testing and 12_protection_testing.
"""
import csv
import os
import random
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
import rasp_nsfnet as nf

# ---------------------------------------------------------------- settings
RATES = [8, 12, 16, 18, 20, 22, 24, 26, 28, 30, 32, 36, 40]   # arrivals per second
SEEDS = [1, 2, 3, 4, 5]
POLICIES = ["RASP-Fog", "No-Relocation", "Static-Strong", "Static-Light"]
P_UP = 0.2                # threat: chance per region and 5 s step that the level rises
DURATION = 150            # seconds of arrivals; sessions then run to completion
WARMUP = 30               # sessions arriving before this are not counted
T95 = 2.776               # t value for a 95% CI with 5 seeds

KEYS = ["secure_pct", "rejected_pct", "dropped_pct", "sla_miss_pct", "upgrades",
        "moves", "terminated", "failed_in_place", "moves_per_1000", "sec_cpu_pct",
        "fog_util_pct", "cloud_pct", "peak_wan_pct"]


# ---------------------------------------------------------------- one run
def run_one(task):
    """task = (policy, rate, seed, p_up, protect). Returns the run's metrics."""
    policy, rate, seed, p_up, protect = task
    nf.PROTECT = protect
    nf.THREAT = nf.random_threat(random.Random(100 + seed), DURATION + 300, p_up)
    arrivals = nf.make_arrivals(random.Random(seed), rate, DURATION)
    m = nf.simulate(policy, arrivals, DURATION, warmup=WARMUP)
    n = max(1, m["arrivals"])
    return {
        "policy": policy, "rate": rate, "seed": seed, "p_up": p_up, "protect": protect,
        "sessions": m["arrivals"],
        "secure_pct": m["secure_pct"],
        "rejected_pct": 100 * m["rejected"] / n,
        "dropped_pct": 100 * m["terminated"] / n,
        "sla_miss_pct": m["sla_miss_pct"],
        "upgrades": m["upgrades"],
        "moves": m["moves"],
        "terminated": m["terminated"],
        "failed_in_place": m["moves"] + m["terminated"],
        "moves_per_1000": 1000 * m["moves"] / n,
        "sec_cpu_pct": m["sec_cpu_pct"],
        "fog_util_pct": m["fog_util_pct"],
        "cloud_pct": 100 * m["cloud"] / n,
        "peak_wan_pct": m["peak_wan_pct"],
    }


def run_grid(tasks):
    """Run every task, in parallel when possible, in a stable order."""
    with ProcessPoolExecutor() as pool:
        return list(pool.map(run_one, tasks, chunksize=1))


def mean_ci(values):
    m = sum(values) / len(values)
    if len(values) < 2:
        return m, 0.0
    sd = (sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5
    return m, T95 * sd / len(values) ** 0.5


def summarize(runs, group):
    """Mean and CI of every metric for each group (a tuple of field names)."""
    groups = {}
    for r in runs:
        groups.setdefault(tuple(r[g] for g in group), []).append(r)
    rows = []
    for key, rs in groups.items():
        row = dict(zip(group, key))
        for k in KEYS:
            row[k], row[k + "_ci"] = mean_ci([r[k] for r in rs])
        rows.append(row)
    return rows


def write_csv(rows, path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()})


# ---------------------------------------------------------------- plots
COLORS = {"RASP-Fog": "#2a78d6", "No-Relocation": "#8a5cc7",
          "Static-Strong": "#eb6834", "Static-Light": "#1baf7a"}
MARKERS = {"RASP-Fog": "o", "No-Relocation": "D", "Static-Strong": "s", "Static-Light": "^"}


def axes(xlabel, ylabel):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=200)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(True, color="#e4e3df", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    return fig, ax


def plot_series(ax, rows, x, y, policies):
    for name in policies:
        pts = sorted((r for r in rows if r["policy"] == name), key=lambda r: r[x])
        ax.errorbar([r[x] for r in pts], [r[y] for r in pts], yerr=[r[y + "_ci"] for r in pts],
                    label=name, color=COLORS[name], marker=MARKERS[name], markersize=5,
                    linewidth=2, capsize=3)


def plot(rows):
    fig, ax = axes("Arrival rate (requests/s)", "Secure and on-time completion (%)")
    plot_series(ax, rows, "rate", "secure_pct", ["RASP-Fog", "No-Relocation", "Static-Strong"])
    ax.legend(frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_nsfnet_secure_completion.png"))

    fig, ax = axes("Arrival rate (requests/s)", "Fog CPU spent on security (% of capacity)")
    # No-Relocation uses the same profiles as RASP-Fog, so its curve coincides; left out
    plot_series(ax, rows, "rate", "sec_cpu_pct", ["RASP-Fog", "Static-Strong", "Static-Light"])
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_nsfnet_security_cpu.png"))


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    print(f"NSFNET load test: rates {RATES} req/s, seeds {SEEDS}, threat p_up {P_UP}, "
          f"{DURATION} s of arrivals ({WARMUP} s warm-up)\n")
    tasks = [(p, rate, s, P_UP, True) for rate in RATES for s in SEEDS for p in POLICIES]
    runs = run_grid(tasks)
    rows = summarize(runs, ("policy", "rate"))
    write_csv(rows, os.path.join(HERE, "load_results.csv"))

    cols = [("secure_pct", "secure %"), ("rejected_pct", "rejected %"),
            ("dropped_pct", "dropped %"), ("moves_per_1000", "moves/1000"),
            ("sec_cpu_pct", "security CPU %"), ("fog_util_pct", "fog CPU %"),
            ("cloud_pct", "cloud %")]
    for name in POLICIES:
        print(name)
        print(f"  {'rate':>4} " + "".join(f"{label:>18}" for _, label in cols))
        for r in sorted((r for r in rows if r["policy"] == name), key=lambda r: r["rate"]):
            print(f"  {r['rate']:>4} " + "".join(
                f"{r[k]:>11.2f} ± {r[k + '_ci']:<4.2f}" for k, _ in cols))
        print()

    # paired differences, RASP-Fog minus each baseline, per seed
    by = {(r["policy"], r["rate"], r["seed"]): r for r in runs}
    print("Paired difference RASP-Fog - baseline in secure completion (points, 95% CI)")
    print(f"  {'rate':>4} " + "".join(f"{p:>20}" for p in POLICIES[1:3]))
    for rate in RATES:
        cells = []
        for p in POLICIES[1:3]:
            m, ci = mean_ci([by[("RASP-Fog", rate, s)]["secure_pct"] - by[(p, rate, s)]["secure_pct"]
                             for s in SEEDS])
            cells.append(f"{m:>+12.2f} ± {ci:<5.2f}")
        print(f"  {rate:>4} " + "".join(cells))

    try:
        plot(rows)
        print("\nWrote load_results.csv and the two figures.")
    except ImportError:
        print("\nWrote load_results.csv (install matplotlib for the figures).")
