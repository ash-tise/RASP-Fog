"""
hysteresis_test.py - number of profile changes vs the hysteresis holding interval tau_H.

Run it from the repository root:   python3 08_hysteresis_testing/hysteresis_test.py

RASP-Fog is run with tau_H = 0, 2, 4, 8, 16, 32 s on the same requests and the
same time-varying threat. Everything else follows ../04_random_testing/random_test.py
(Poisson arrivals, sessions with exponential durations, threat random walk,
resources released on completion, setup delay), with two changes:
  * node capacity x10, as in the arrival-rate and security CPU tests,
  * the threat is updated every THREAT_EVERY seconds.
The arrival rate is kept below saturation so that changes come from the threat,
not from a full network.

Writes hysteresis_results.csv and fig8_profile_changes.png (needs matplotlib).
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "04_random_testing"))
import rasp_core as core
import random_test as rt                  # traffic and threat generator

# ---------------------------------------------------------------- test settings
TAU_VALUES = [0, 2, 4, 8, 16, 32]         # hysteresis holding interval (s)
RATE = 4                                  # average arrivals per second
SEEDS = [1, 2, 3, 4, 5]
CAPACITY_SCALE = 10                       # same network as tests 06 and 07
core.STEPS = 300                          # seconds per run
rt.THREAT_EVERY = 5                       # threat update interval (s)
T95 = 2.776                               # t value for a 95% CI with 5 seeds

for n in core.NODES.values():
    for key in ("cpu", "mem", "bw"):
        n[key] *= CAPACITY_SCALE
FOG = [name for name in core.NODES if name != "Cloud"]
FOG_CPU = sum(core.NODES[name]["cpu"] for name in FOG)


# ---------------------------------------------------------------- one run
def run_once(tau_h, seed):
    policy = {"profile": "adaptive", "relocate": True, "tau_h": tau_h}
    schedule, arrivals = rt.make_world(RATE, seed)
    core.THREAT_SCHEDULE = schedule
    by_time = {}
    for a in arrivals:
        by_time.setdefault(a["t"], []).append(dict(a))

    active, log = [], []
    under = overcap = 0
    sec_cpu = fog_cpu = 0.0               # summed over seconds
    for t in range(core.STEPS):
        for req in [r for r in active if r["end"] <= t]:
            active.remove(req)
        for req in list(active):                           # Algorithm 2
            core.adapt(req, t, active, log, policy)
        for req in by_time.get(t, []):                     # Algorithm 1, with setup delay
            req["deadline"] -= rt.SETUP_MS
            core.admit(req, t, active, log, policy)
            req["deadline"] += rt.SETUP_MS
        for r in active:
            if r["k"] < core.required(r["sigma"], core.threat(t)):
                under += 1
            if r["node"] in FOG:
                sec_cpu += r["c"] * core.PROFILES[r["k"]]["dc"]
        for name, n in core.NODES.items():
            c, m, b = core.used(name, active)
            if name in FOG:
                fog_cpu += c
            if c > n["cpu"] + 1e-9 or m > n["mem"] + 1e-9 or b > n["bw"] + 1e-9:
                overcap += 1

    # a re-upgrade is an upgrade (or move) of a request that was downgraded before
    downgraded, reupgrades = set(), 0
    for _, event, req, _ in log:
        if event == "DOWNGRADE":
            downgraded.add(req["id"])
        elif event in ("UPGRADE", "MOVE") and req["id"] in downgraded:
            reupgrades += 1

    admitted = core.count(log, "ADMIT")
    return {
        "changes": core.profile_changes(log),
        "upgrades": core.count(log, "UPGRADE") + core.count(log, "MOVE"),
        "downgrades": core.count(log, "DOWNGRADE"),
        "reupgrades": reupgrades,
        "terminated": core.count(log, "TERMINATE"),
        "reject_pct": 100 * core.count(log, "REJECT") / max(1, len(arrivals)),
        "changes_per_req": core.profile_changes(log) / max(1, admitted),
        "security_cpu_pct": 100 * sec_cpu / core.STEPS / FOG_CPU,
        "fog_cpu_pct": 100 * fog_cpu / core.STEPS / FOG_CPU,
        "under_req_s": under,
        "overcap": overcap,
    }


def mean_ci(values):
    m = sum(values) / len(values)
    sd = (sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5
    return m, T95 * sd / len(values) ** 0.5


# ---------------------------------------------------------------- plot
def plot(rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    series = [("changes", "All profile changes", "#2a78d6", "o"),
              ("upgrades", "Upgrades (incl. relocations)", "#eb6834", "s"),
              ("downgrades", "Downgrades", "#1baf7a", "^")]
    fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=200)
    for key, label, color, marker in series:
        ax.errorbar([r["tau_h"] for r in rows], [r[key] for r in rows],
                    yerr=[r[key + "_ci"] for r in rows], label=label,
                    color=color, marker=marker, markersize=6, linewidth=2, capsize=3)
    ax.set_xlabel(r"Hysteresis holding interval $\tau_H$ (s)")
    ax.set_ylabel("Profile changes per run")
    ax.set_xticks(TAU_VALUES)
    ax.set_ylim(bottom=0)
    ax.grid(True, color="#e4e3df", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(path)


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    print(f"Hysteresis test: RASP-Fog, {RATE} req/s, {core.STEPS} s per run, threat updated "
          f"every {rt.THREAT_EVERY} s, capacity x{CAPACITY_SCALE}, seeds {SEEDS}\n")
    rows, first = [], None
    for tau_h in TAU_VALUES:
        runs = [run_once(tau_h, s) for s in SEEDS]
        first = first or runs                              # tau_H = 0, the reference
        for r, r0 in zip(runs, first):                     # paired by seed
            r["change_cut_pct"] = 100 * (1 - r["changes"] / r0["changes"])
            r["security_cpu_rise_pct"] = 100 * (r["security_cpu_pct"] / r0["security_cpu_pct"] - 1)
        row = {"tau_h": tau_h}
        for key in runs[0]:
            row[key], row[key + "_ci"] = mean_ci([r[key] for r in runs])
        rows.append(row)

    cols = [("changes", "changes"), ("upgrades", "upgrades"), ("downgrades", "downgr."),
            ("reupgrades", "re-upgr."), ("changes_per_req", "per req"),
            ("security_cpu_pct", "sec CPU %"), ("fog_cpu_pct", "fog CPU %"),
            ("reject_pct", "reject %"), ("terminated", "termin."), ("under_req_s", "under")]
    paired = [("change_cut_pct", "Fewer profile changes than tau_H = 0 (%)"),
              ("security_cpu_rise_pct", "More fog security CPU than tau_H = 0 (%)")]
    print("Per run, mean over seeds (95% CI for changes and security CPU)")
    print(f"  {'tau_H':>5}" + "".join(f"{h:>14}" for _, h in cols))
    for r in rows:
        cells = []
        for key, _ in cols:
            if key in ("changes", "security_cpu_pct"):
                cells.append(f"{r[key]:.1f} ± {r[key + '_ci']:.1f}" if key == "changes"
                             else f"{r[key]:.2f} ± {r[key + '_ci']:.2f}")
            else:
                cells.append(f"{r[key]:.2f}")
        print(f"  {r['tau_h']:>5}" + "".join(f"{c:>14}" for c in cells))
    for key, title in paired:
        print(f"\n{title}, paired by seed, mean ± 95% CI")
        for r in rows[1:]:
            print(f"  tau_H = {r['tau_h']:>2}: {r[key]:5.1f} ± {r[key + '_ci']:.1f}")

    with open(os.path.join(HERE, "hysteresis_results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("\nResults saved to hysteresis_results.csv")

    print("\nChecks (all tau_H, all seeds):")
    print(f"  [{'PASS' if all(r['under_req_s'] == 0 for r in rows) else 'FAIL'}] Never under-protected")
    print(f"  [{'PASS' if all(r['overcap'] == 0 for r in rows) else 'FAIL'}] No node ever over capacity")

    try:
        plot(rows, os.path.join(HERE, "fig8_profile_changes.png"))
        print("Figure saved to fig8_profile_changes.png")
    except ImportError:
        print("matplotlib not installed: figure skipped (pip install matplotlib)")
