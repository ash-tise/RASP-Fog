"""
run_figures.py - the three NSFNET figures for the final report.

Run from the repository root:
    python3 13_final_figures/run_figures.py            # all three figures
    python3 13_final_figures/run_figures.py fig1       # just one

Every method and every x value sees the same request trace and the same threat
trace for a given seed (common random numbers): arrivals come from
Random(seed) and the threat from Random(1000 + seed).

Outputs, in 13_final_figures/:
    config.json                 every setting used (also the parameter table source)
    figN_raw.csv                one row per (method, x, seed) run
    figN_summary.csv            mean and 95% t-interval half-width over seeds
    figN_*.png / .pdf           the figure
"""
import csv
import json
import math
import os
import random
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import rasp_nsfnet as nf

# ---------------------------------------------------------------- settings
SEEDS = list(range(1, 11))
T95 = 2.262                 # two-sided 95% t value, 9 degrees of freedom
DURATION = 300              # seconds of arrivals; sessions then run to completion
WARMUP = 60                 # sessions arriving before this are not measured
EPOCH = 1.0                 # adaptation epoch (s)
THREAT_EVERY = 5            # threat random walk step (s)
P_DOWN = 0.3                # threat step-down probability per step

FIG1 = {"methods": ["RASP-Fog", "SA-FF", "Static-Strong"],
        "rates": [8, 12, 16, 20, 24, 28, 32, 36, 40, 48, 56, 64, 80],
        "theta": 2}
FIG2 = {"methods": ["RASP-Fog", "RASP-Reloc", "RASP-Profile", "SA-FF"],
        "p_up": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        "rate": None}       # set after Fig. 1: just past the saturation knee
FIG3 = {"method": "RASP-Fog", "tau_h": [0, 2, 4, 8, 16, 32],
        "rate": None, "p_up": 0.2}

METRICS = ["secure_pct", "rejected_pct", "terminated_pct", "sla_violation_pct",
           "sla_miss_pct", "sec_cpu_pct", "fog_util_pct", "sec_term_pct",
           "mandatory_reqs", "reloc_tries", "reloc_success_pct", "moves",
           "reloc_added_ms", "changes_per_1000", "upgrades", "downgrades",
           "under", "cloud_pct", "mean_delay", "arrivals", "admitted"]


# ---------------------------------------------------------------- one run
def run_one(task):
    fig, method, x, seed, rate, threat, tau_h = task
    nf.PROTECT = True
    nf.TAU_H = tau_h
    if threat[0] == "fixed":
        nf.THREAT = nf.uniform_threat([(0, threat[1])])
    else:
        nf.THREAT = nf.random_threat(random.Random(1000 + seed), DURATION + 600,
                                     threat[1], p_down=P_DOWN, every=THREAT_EVERY)
    arrivals = nf.make_arrivals(random.Random(seed), rate, DURATION)
    m = nf.simulate(method, arrivals, DURATION, warmup=WARMUP, epoch=EPOCH)
    n = max(1, m["arrivals"])
    row = {"fig": fig, "method": method, "x": x, "seed": seed, "rate": rate,
           "tau_h": tau_h, "threat": f"{threat[0]}:{threat[1]}"}
    for k in METRICS:
        row[k] = m.get(k)
    row["cloud_pct"] = 100 * m["cloud"] / n
    row["reloc_added_ms"] = nf.PSI_MOVE + m["reloc_added_nu"] if m["moves"] else float("nan")
    return row


def run_grid(tasks):
    with ProcessPoolExecutor() as pool:
        return list(pool.map(run_one, tasks, chunksize=2))


def summarize(rows, keys=("method", "x")):
    groups = {}
    for r in rows:
        groups.setdefault(tuple(r[k] for k in keys), []).append(r)
    out = []
    for g, rs in groups.items():
        s = dict(zip(keys, g))
        s["n"] = len(rs)
        for k in METRICS:
            vals = [r[k] for r in rs if r[k] is not None and not
                    (isinstance(r[k], float) and math.isnan(r[k]))]
            s[k] = statistics.mean(vals) if vals else float("nan")
            s[k + "_ci"] = (T95 * statistics.stdev(vals) / math.sqrt(len(vals))
                            if len(vals) > 1 else float("nan"))
            s[k + "_n"] = len(vals)
        out.append(s)
    return out


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def series(summary, method, key):
    rs = sorted((s for s in summary if s["method"] == method), key=lambda s: s["x"])
    return [s["x"] for s in rs], [s[key] for s in rs], [s[key + "_ci"] for s in rs]


STYLE = {"RASP-Fog": ("#1f77b4", "o", "-"), "SA-FF": ("#ff7f0e", "s", "--"),
         "Static-Strong": ("#2ca02c", "^", ":"), "RASP-Reloc": ("#9467bd", "D", "-."),
         "RASP-Profile": ("#d62728", "v", "--")}


def plot(summary, methods, panels, xlabel, fname, title_x=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, len(panels), figsize=(4.2 * len(panels), 3.3))
    axes = [axes] if len(panels) == 1 else list(axes)
    for ax, (key, ylabel, tag) in zip(axes, panels):
        for m in methods:
            xs, ys, ci = series(summary, m, key)
            c, mk, ls = STYLE.get(m, ("k", "o", "-"))
            ax.errorbar(xs, ys, yerr=ci, color=c, marker=mk, ls=ls, ms=4, capsize=3,
                        lw=1.4, label=m)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if tag:
            ax.set_title(tag, fontsize=10)
        ax.grid(alpha=0.3)
    if len(methods) > 1:
        axes[0].legend(fontsize=8)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(HERE, f"{fname}.{ext}"), dpi=200)
    plt.close(fig)


# ---------------------------------------------------------------- figures
def fig1():
    tasks = [("fig1", m, r, s, r, ("fixed", FIG1["theta"]), nf.TAU_H)
             for m in FIG1["methods"] for r in FIG1["rates"] for s in SEEDS]
    rows = run_grid(tasks)
    summ = summarize(rows)
    write_csv(os.path.join(HERE, "fig1_raw.csv"), rows)
    write_csv(os.path.join(HERE, "fig1_summary.csv"), summ)
    plot(summ, FIG1["methods"],
         [("secure_pct", "Secure completion (%)", "(a)"),
          ("sec_cpu_pct", "Security-only fog CPU (%)", "(b)")],
         "Arrival rate (req/s)", "fig1_workload")
    return summ


def fig2():
    tasks = [("fig2", m, p, s, FIG2["rate"], ("walk", p), nf.TAU_H)
             for m in FIG2["methods"] for p in FIG2["p_up"] for s in SEEDS]
    rows = run_grid(tasks)
    summ = summarize(rows)
    write_csv(os.path.join(HERE, "fig2_raw.csv"), rows)
    write_csv(os.path.join(HERE, "fig2_summary.csv"), summ)
    plot(summ, FIG2["methods"],
         [("sec_term_pct", "Security-triggered termination (%)", None)],
         "Threat-increase probability", "fig2_threat")
    return summ


def fig3():
    tasks = [("fig3", FIG3["method"], tau, s, FIG3["rate"], ("walk", FIG3["p_up"]), tau)
             for tau in FIG3["tau_h"] for s in SEEDS]
    rows = run_grid(tasks)
    summ = summarize(rows)
    write_csv(os.path.join(HERE, "fig3_raw.csv"), rows)
    write_csv(os.path.join(HERE, "fig3_summary.csv"), summ)
    plot(summ, [FIG3["method"]],
         [("changes_per_1000", "Profile changes per 1,000 admitted", "(a)"),
          ("sec_cpu_pct", "Security-only fog CPU (%)", "(b)")],
         r"Hysteresis interval $\tau_H$ (s)", "fig3_hysteresis")
    return summ


def config():
    return {
        "seeds": SEEDS, "t95": T95, "duration_s": DURATION, "warmup_s": WARMUP,
        "epoch_s": EPOCH, "threat_step_s": THREAT_EVERY, "threat_p_down": P_DOWN,
        "fig1": FIG1, "fig2": FIG2, "fig3": FIG3,
        "model": {
            "tau_h_default_s": nf.TAU_H, "lambda_d": nf.LAMBDA_D, "lambda_o": nf.LAMBDA_O,
            "omega": nf.OMEGA, "links": nf.NSFNET_LINKS, "link_delay_ms": nf.LINK_DELAY_MS,
            "link_bw_mbps": nf.LINK_BW, "small_node": nf.SMALL, "large_node": nf.LARGE,
            "large_nodes": [j for j in nf.FOG if j % 2], "cloud_gateways": nf.CLOUD_GATEWAYS,
            "wan_delay_ms": nf.WAN_DELAY_MS, "wan_bw_mbps": nf.WAN_BW, "cloud_mu": nf.CLOUD_MU,
            "chi_ms": nf.CHI_MS, "max_util": nf.MAX_UTIL, "profiles": nf.PROFILES,
            "rho_ms_per_level": nf.RHO_PER_LEVEL, "psi_move_ms": nf.PSI_MOVE,
            "request_classes": nf.TYPES, "demand_spread": nf.SPREAD, "regions": nf.REGIONS,
            "protect_incumbents": nf.PROTECT, "policies": nf.POLICIES,
        },
    }


if __name__ == "__main__":
    which = sys.argv[1:] or ["fig1", "fig2", "fig3"]
    rate = float(os.environ.get("RATE_FIG2", "0")) or None
    FIG2["rate"] = rate
    FIG3["rate"] = float(os.environ.get("RATE_FIG3", "0")) or None
    if "fig1" in which:
        fig1()
    if "fig2" in which:
        assert FIG2["rate"], "set RATE_FIG2 (req/s) from the Fig. 1 knee"
        fig2()
    if "fig3" in which:
        assert FIG3["rate"], "set RATE_FIG3 (req/s) for moderate load"
        fig3()
    with open(os.path.join(HERE, "config.json"), "w") as f:
        json.dump(config(), f, indent=1, default=str)
    print("done:", ", ".join(which))
