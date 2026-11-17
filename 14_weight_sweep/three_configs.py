"""
three_configs.py - the three weight configurations asked for in review, run
against the baselines on the same seeds and traces.

Configs (lambda_O = 1 - lambda_D):
    A  original      lambda_D 0.50, omega (1/3, 1/3, 1/3)
    B  overhead-heavy lambda_D 0.25, omega (1/3, 1/3, 1/3)
    C  B + CPU-heavy  lambda_D 0.25, omega (0.6, 0.2, 0.2)

Every method (RASP-Fog and the baselines) runs under every config, because the
objective-placement baselines use the same cost J; SA-FF and Static-Strong use J
only to pick among their own candidates. Scenarios and run settings come from
sweep.py (300 s, 60 s warm-up, deadline protection on, tau_H = 8 s); rates
16, 24 and 32 req/s cover light load, the knee and overload. Seeds 1-10.

Run from the repository root:   python3 14_weight_sweep/three_configs.py
"""
import csv
import math
import os
import random
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import rasp_nsfnet as nf
import sweep

CONFIGS = {"A": (0.50, (1/3, 1/3, 1/3)),
           "B": (0.25, (1/3, 1/3, 1/3)),
           "C": (0.25, (0.6, 0.2, 0.2))}
METHODS = ["RASP-Fog", "SA-FF", "RASP-Profile", "RASP-Reloc", "Static-Strong"]
RATES = [16, 24, 32]
SEEDS = sweep.EVAL_SEEDS
KEYS = ["secure_pct", "service_failure_pct", "sla_miss_pct", "sec_term_pct", "rejected_pct",
        "sec_cpu_pct", "fog_util_pct", "cloud_pct", "mean_delay", "reconfig_ms_per_req",
        "changes_per_1000"]


def run_one(task):
    scen, rate, cfg, method, seed = task
    kind, val = sweep.SCENARIOS[scen]
    lam_d, omega = CONFIGS[cfg]
    nf.PROTECT, nf.TAU_H = True, 8
    nf.LAMBDA_D, nf.LAMBDA_O, nf.OMEGA = lam_d, 1 - lam_d, omega
    if kind == "fixed":
        nf.THREAT = nf.uniform_threat([(0, val)])
    else:
        nf.THREAT = nf.random_threat(random.Random(1000 + seed), sweep.DURATION + 600, val,
                                     p_down=0.3, every=5)
    arr = nf.make_arrivals(random.Random(seed), rate, sweep.DURATION)
    m = nf.simulate(method, arr, sweep.DURATION, warmup=sweep.WARMUP)
    row = {"scenario": scen, "rate": rate, "config": cfg, "method": method, "seed": seed}
    for k in KEYS:
        row[k] = 100 * m["cloud"] / max(1, m["arrivals"]) if k == "cloud_pct" else m[k]
    return row


def main():
    tasks = [(s, r, c, m, seed) for s in sweep.SCENARIOS for r in RATES for c in CONFIGS
             for m in METHODS for seed in SEEDS]
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(run_one, tasks, chunksize=2))
    sweep.write(os.path.join(HERE, "three_configs_raw.csv"), rows)

    by = {(r["scenario"], r["rate"], r["config"], r["method"], r["seed"]): r for r in rows}
    out = []
    for s in sweep.SCENARIOS:
        for rate in RATES:
            print(f"\n== {s} @ {rate} req/s")
            for c in CONFIGS:
                for m in METHODS:
                    row = {"scenario": s, "rate": rate, "config": c, "method": m}
                    for k in KEYS:
                        row[k], row[k + "_ci"] = sweep.mean_ci([by[(s, rate, c, m, x)][k] for x in SEEDS])
                        # paired difference vs RASP-Fog under config A, same seeds
                        row[k + "_vs_A"], row[k + "_vs_A_ci"] = sweep.mean_ci(
                            [by[(s, rate, c, m, x)][k] - by[(s, rate, "A", "RASP-Fog", x)][k]
                             for x in SEEDS])
                    out.append(row)
                    print(f"  {c} {m:13s} secure {row['secure_pct']:6.2f}±{row['secure_pct_ci']:.2f}"
                          f" (vs A/RASP {row['secure_pct_vs_A']:+.2f}±{row['secure_pct_vs_A_ci']:.2f})"
                          f"  fail {row['service_failure_pct']:.2f}  rej {row['rejected_pct']:.2f}"
                          f"  secCPU {row['sec_cpu_pct']:.2f}  cloud {row['cloud_pct']:.1f}"
                          f"  delay {row['mean_delay']:.1f}  reconf {row['reconfig_ms_per_req']:.2f}")
    sweep.write(os.path.join(HERE, "three_configs_summary.csv"), out)


if __name__ == "__main__":
    main()
