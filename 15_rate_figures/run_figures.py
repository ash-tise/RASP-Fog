"""
run_figures.py - the full arrival-rate sweep for the four figures.

Run from the repository root (traces must exist: make_traces.py):
    python3 15_rate_figures/run_figures.py

Runs every method in exp_config.METHODS at every rate in exp_config.RATES on every
seed in exp_config.SEEDS, all replaying the stored traces. Writes
    rate_raw.csv        one row per (method, rate, seed)
    rate_summary.csv    mean and 95% t half-width per (method, rate)
    rate_paired.csv     RASP-Fog minus each other method, paired by seed
Then draws the figures with plot_figures.py.
"""
import csv
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import exp_config as cfg

METRICS = ["secure_pct", "sec_term_pct", "mean_delay", "changes_per_1000",
           "rejected_pct", "terminated_pct", "sla_miss_pct", "fog_util_pct",
           "sec_cpu_pct", "cloud_pct", "mandatory_reqs", "moves", "arrivals", "admitted",
           "service_failure_pct", "reconfig_ms_per_req"]


def task(x):
    return cfg.run(*x)


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    missing = [s for s in cfg.SEEDS if not os.path.exists(cfg.trace_path(s))]
    if missing:
        sys.exit(f"missing traces for seeds {missing}: run make_traces.py first")
    # heaviest runs first so the pool stays busy at the end
    tasks = [(m, s, r) for r in sorted(cfg.RATES, reverse=True) for m in cfg.METHODS
             for s in cfg.SEEDS]
    t0 = time.time()
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(task, tasks, chunksize=1))
    print(f"{len(rows)} runs in {time.time() - t0:.0f} s")
    rows.sort(key=lambda r: (cfg.METHODS.index(r["method"]), r["rate"], r["seed"]))
    write_csv(os.path.join(cfg.HERE, "rate_raw.csv"), rows)

    by = {(r["method"], r["rate"], r["seed"]): r for r in rows}
    summary, paired = [], []
    for m in cfg.METHODS:
        for rate in cfg.RATES:
            s = {"method": m, "rate": rate}
            for k in METRICS:
                s[k], s[k + "_ci"], s["n"] = cfg.mean_ci([by[(m, rate, sd)][k] for sd in cfg.SEEDS])
            summary.append(s)
            if m != "RASP-Fog":
                p = {"vs": m, "rate": rate}
                for k in cfg.FIG_METRICS:
                    p[k], p[k + "_ci"], _ = cfg.mean_ci(
                        [by[("RASP-Fog", rate, sd)][k] - by[(m, rate, sd)][k] for sd in cfg.SEEDS])
                paired.append(p)
    write_csv(os.path.join(cfg.HERE, "rate_summary.csv"), summary)
    write_csv(os.path.join(cfg.HERE, "rate_paired.csv"), paired)
    subprocess.run([sys.executable, os.path.join(cfg.HERE, "plot_figures.py")], check=True)
