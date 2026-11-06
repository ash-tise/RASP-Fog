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

An SLA violation is an admitted session that is later dropped or pushed past its
deadline; rejections at admission are counted separately.

Writes attack_results.csv and four figures: SLA violations, secure completion,
relocation overhead (rate and delay added per relocation) and resource utilization.
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


def style(ax, xlabel, ylabel, ticks):
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(*ticks)
    ax.grid(True, color="#e4e3df", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def plot(rows, runs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xlabel = "Attack intensity p_up (mean threat level)"
    threat = {r["p_up"]: r["mean_threat"] for r in rows}
    ticks = (P_UPS, [f"{pu:.1f}\n({threat[pu]:.2f})" for pu in P_UPS])

    # SLA violations: admitted sessions later dropped or pushed past their deadline
    fig, ax = base.axes(xlabel, "SLA violations (% of sessions)")
    base.plot_series(ax, rows, "p_up", "sla_violation_pct", POLICIES)
    ax.set_xticks(*ticks)
    ax.set_ylim(bottom=-0.05)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_attack_sla_violations.png"))

    # secure completion
    fig, ax = base.axes(xlabel, "Secure and on-time completion (%)")
    base.plot_series(ax, rows, "p_up", "secure_pct", POLICIES)
    ax.set_xticks(*ticks)
    ax.legend(frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_attack_secure.png"))

    # relocation overhead (RASP-Fog): how often, and what each relocation costs
    rasp = sorted((r for r in rows if r["policy"] == "RASP-Fog"), key=lambda r: r["p_up"])
    added = []                                    # pooled over seeds, weighted by moves
    for pu in P_UPS:
        rs = [r for r in runs if r["policy"] == "RASP-Fog" and r["p_up"] == pu]
        moves = sum(r["moves"] for r in rs)
        added.append(sum(r["moves"] * (r["reloc_added_ms"] - nf.PSI_MOVE) for r in rs) / moves
                     if moves else 0.0)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 3.8), dpi=200)
    a1.errorbar([r["p_up"] for r in rasp], [r["moves_per_1000"] for r in rasp],
                yerr=[r["moves_per_1000_ci"] for r in rasp], color=base.COLORS["RASP-Fog"],
                marker="o", markersize=5, linewidth=2, capsize=3)
    style(a1, xlabel, "Relocations per 1000 sessions", ticks)
    a1.set_ylim(bottom=0)
    a1.set_title("(a) Relocation rate", fontsize=10)
    a2.bar(P_UPS, [nf.PSI_MOVE if a else 0 for a in added], width=0.06,
           color="#2a78d6", label="Migration delay \u03c8")
    a2.bar(P_UPS, added, width=0.06, bottom=[nf.PSI_MOVE if a else 0 for a in added],
           color="#9cc3ee", label="Longer network path")
    style(a2, xlabel, "Delay added per relocated session (ms)", ticks)
    a2.set_title("(b) Cost of one relocation", fontsize=10)
    a2.set_ylim(0, 55)
    a2.legend(frameon=False, loc="upper center", ncol=2)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_attack_relocation.png"))

    # resource utilization (No-Relocation's CPU curves coincide with RASP-Fog's)
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(13.2, 3.9), dpi=200)
    short = "Attack intensity p_up (mean threat)"
    base.plot_series(a1, rows, "p_up", "fog_util_pct", POLICIES)
    style(a1, short, "Fog CPU utilization (%)", ticks)
    a1.set_ylim(80, 100)
    a1.set_title("(a) Fog CPU reserved", fontsize=10)
    a1.legend(frameon=False, loc="lower right")
    base.plot_series(a2, rows, "p_up", "sec_cpu_pct", POLICIES)
    style(a2, short, "Fog CPU spent on security (%)", ticks)
    a2.set_ylim(bottom=0)
    a2.set_title("(b) Security share of fog CPU", fontsize=10)
    base.plot_series(a3, rows, "p_up", "link_util_pct", POLICIES)
    style(a3, short, "Mean fog-link utilization (%)", ticks)
    a3.set_ylim(bottom=0)
    a3.set_title("(c) Fog-link bandwidth", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, "fig_attack_utilization.png"))


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
            ("sla_violation_pct", "SLA violations %"), ("upgrades", "upgrades"),
            ("failed_in_place", "failed in place"), ("moves", "relocations"),
            ("sec_cpu_pct", "security CPU %"), ("fog_util_pct", "fog CPU %"),
            ("link_util_pct", "fog link %"), ("wan_util_pct", "WAN %")]
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
          f"{'secure, RASP - NoRel (pts)':>30} {'delay added per relocation (ms)':>33}")
    for pu in P_UPS:
        rasp = [by[("RASP-Fog", pu, s)] for s in SEEDS]
        norel = [by[("No-Relocation", pu, s)] for s in SEEDS]
        rescued = sum(r["moves"] for r in rasp) / max(1, sum(r["failed_in_place"] for r in rasp))
        d = base.mean_ci([a["dropped_pct"] - b["dropped_pct"] for a, b in zip(rasp, norel)])
        sec = base.mean_ci([a["secure_pct"] - b["secure_pct"] for a, b in zip(rasp, norel)])
        moves = sum(r["moves"] for r in rasp)
        added = sum(r["moves"] * r["reloc_added_ms"] for r in rasp) / moves if moves else 0.0
        print(f"  {pu:>4.1f} {100 * rescued:>28.1f} {d[0]:>+22.2f} ± {d[1]:<5.2f} "
              f"{sec[0]:>+22.2f} ± {sec[1]:<5.2f} {added:>33.1f}")

    try:
        plot(rows, runs)
        print("\nWrote attack_results.csv and the four figures.")
    except ImportError:
        print("\nWrote attack_results.csv (install matplotlib for the figures).")
