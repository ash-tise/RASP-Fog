"""
attack_intensity_test.py - how mandatory upgrades trigger re-orchestration on
NSFNET as the attack gets more intense, near saturation.

Run it from the repository root:   python3 11_attack_intensity_testing/attack_intensity_test.py

Same model and helpers as 10_nsfnet_load_testing. The arrival rate is fixed near
saturation and the attack intensity p_up (the chance per region and 5 s step
that the threat level rises; it falls with chance 0.3) is swept. A higher p_up
keeps regions at threat 2-3 more of the time, so more running sessions need
upgrades. RASP-Fog upgrades in place or relocates; No-Relocation upgrades in
place or drops the session; Static-Strong never changes and is the reference.

Writes attack_results.csv, fig_attack_dropped.png and fig_attack_secure.png.
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "10_nsfnet_load_testing"))
import nsfnet_load_test as base
from nsfnet_load_test import nf

# ---------------------------------------------------------------- settings
RATE = 24                                     # req/s, near saturation (see 10)
P_UPS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
POLICIES = ["RASP-Fog", "No-Relocation", "Static-Strong"]
SEEDS = base.SEEDS


def mean_threat(p_up, seed):
    """Time-averaged threat level over the measured window, across regions."""
    sched = nf.random_threat(random.Random(100 + seed), base.DURATION + 300, p_up)
    total = 0.0
    for r in nf.REGIONS:
        nf.THREAT = sched
        node = nf.REGIONS[r][0]
        total += sum(nf.threat(t + 0.5, node) for t in range(base.WARMUP, base.DURATION))
    return total / (len(nf.REGIONS) * (base.DURATION - base.WARMUP))


def plot(rows):
    xlabel = "Attack intensity p_up (mean threat level)"
    threat = {r["p_up"]: r["mean_threat"] for r in rows}
    ticks = ([pu for pu in P_UPS], [f"{pu:.1f}\n({threat[pu]:.2f})" for pu in P_UPS])

    fig, ax = base.axes(xlabel, "Sessions dropped mid-session (%)")
    base.plot_series(ax, rows, "p_up", "dropped_pct", ["RASP-Fog", "No-Relocation"])
    ax.set_xticks(*ticks)
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_attack_dropped.png"))

    fig, ax = base.axes(xlabel, "Secure and on-time completion (%)")
    base.plot_series(ax, rows, "p_up", "secure_pct", POLICIES)
    ax.set_xticks(*ticks)
    ax.legend(frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_attack_secure.png"))


if __name__ == "__main__":
    print(f"Attack-intensity test: {RATE} req/s, p_up {P_UPS}, seeds {SEEDS}\n")
    tasks = [(p, RATE, s, pu, True) for pu in P_UPS for s in SEEDS for p in POLICIES]
    runs = base.run_grid(tasks)
    rows = base.summarize(runs, ("policy", "p_up"))
    threat = {pu: base.mean_ci([mean_threat(pu, s) for s in SEEDS])[0] for pu in P_UPS}
    for r in rows:
        r["mean_threat"] = threat[r["p_up"]]
    base.write_csv(rows, os.path.join(HERE, "attack_results.csv"))

    cols = [("secure_pct", "secure %"), ("rejected_pct", "rejected %"),
            ("dropped_pct", "dropped %"), ("upgrades", "upgrades"),
            ("failed_in_place", "failed in place"), ("moves", "relocations"),
            ("sec_cpu_pct", "security CPU %"), ("fog_util_pct", "fog CPU %")]
    for name in POLICIES:
        print(name)
        print(f"  {'p_up':>4} {'threat':>6} " + "".join(f"{label:>18}" for _, label in cols))
        for r in sorted((r for r in rows if r["policy"] == name), key=lambda r: r["p_up"]):
            print(f"  {r['p_up']:>4.1f} {r['mean_threat']:>6.2f} " + "".join(
                f"{r[k]:>11.2f} ± {r[k + '_ci']:<4.2f}" for k, _ in cols))
        print()

    by = {(r["policy"], r["p_up"], r["seed"]): r for r in runs}
    print("RASP-Fog vs No-Relocation, paired per seed (95% CI)")
    print(f"  {'p_up':>4} {'rescued by relocation (%)':>28} {'dropped, RASP - NoRel (pts)':>30} "
          f"{'secure, RASP - NoRel (pts)':>30}")
    for pu in P_UPS:
        rasp = [by[("RASP-Fog", pu, s)] for s in SEEDS]
        norel = [by[("No-Relocation", pu, s)] for s in SEEDS]
        rescued = sum(r["moves"] for r in rasp) / max(1, sum(r["failed_in_place"] for r in rasp))
        d = base.mean_ci([a["dropped_pct"] - b["dropped_pct"] for a, b in zip(rasp, norel)])
        sec = base.mean_ci([a["secure_pct"] - b["secure_pct"] for a, b in zip(rasp, norel)])
        print(f"  {pu:>4.1f} {100 * rescued:>28.1f} {d[0]:>+22.2f} ± {d[1]:<5.2f} "
              f"{sec[0]:>+22.2f} ± {sec[1]:<5.2f}")

    try:
        plot(rows)
        print("\nWrote attack_results.csv and the two figures.")
    except ImportError:
        print("\nWrote attack_results.csv (install matplotlib for the figures).")
