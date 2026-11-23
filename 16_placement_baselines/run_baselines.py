"""
run_baselines.py - RASP-Fog vs SA-FF, latency-aware (LA) and load-aware (LB)
placement, under nominal and constrained fog/cloud capacity.

Run from the repository root (traces from 15_rate_figures/make_traces.py):
    python3 16_placement_baselines/run_baselines.py

Writes, in 16_placement_baselines/:
    baselines_raw.csv       one row per (scenario, method, rate, seed)
    baselines_summary.csv   mean and 95% t half-width per (scenario, method, rate)
    baselines_paired.csv    RASP-Fog minus each other method, paired by seed
then draws the figures with plot_baselines.py.
"""
import csv
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import baseline_config as cfg

PAIRED = ["secure_pct", "rejected_pct", "sec_term_pct", "mean_delay", "cloud_pct",
          "fog_util_pct"]


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
        sys.exit(f"missing traces for seeds {missing}: run 15_rate_figures/make_traces.py first")
    tasks = [(sc, m, s, r) for sc in cfg.SCENARIOS for r in sorted(cfg.RATES[sc], reverse=True)
             for m in cfg.METHODS for s in cfg.SEEDS]
    tasks.sort(key=lambda t: -t[3])                 # heaviest runs first
    t0 = time.time()
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(task, tasks, chunksize=1))
    print(f"{len(rows)} runs in {time.time() - t0:.0f} s")
    sc_order = list(cfg.SCENARIOS)
    rows.sort(key=lambda r: (sc_order.index(r["scenario"]), cfg.METHODS.index(r["method"]),
                             r["rate"], r["seed"]))
    write_csv(os.path.join(cfg.HERE, "baselines_raw.csv"),
              [{"scenario": r["scenario"], **{k: v for k, v in r.items() if k != "scenario"}}
               for r in rows])

    by = {(r["scenario"], r["method"], r["rate"], r["seed"]): r for r in rows}
    summary, paired = [], []
    for sc in cfg.SCENARIOS:
        for m in cfg.METHODS:
            for rate in cfg.RATES[sc]:
                s = {"scenario": sc, "method": m, "rate": rate}
                for k in cfg.METRICS:
                    s[k], s[k + "_ci"], s["n"] = cfg.mean_ci(
                        [by[(sc, m, rate, sd)][k] for sd in cfg.SEEDS])
                summary.append(s)
                if m != "RASP-Fog":
                    p = {"scenario": sc, "vs": m, "rate": rate}
                    for k in PAIRED:
                        p[k], p[k + "_ci"], _ = cfg.mean_ci(
                            [by[(sc, "RASP-Fog", rate, sd)][k] - by[(sc, m, rate, sd)][k]
                             for sd in cfg.SEEDS])
                    paired.append(p)
    write_csv(os.path.join(cfg.HERE, "baselines_summary.csv"), summary)
    write_csv(os.path.join(cfg.HERE, "baselines_paired.csv"), paired)
    subprocess.run([sys.executable, os.path.join(cfg.HERE, "plot_baselines.py")], check=False)
