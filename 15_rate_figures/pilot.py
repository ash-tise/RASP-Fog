"""
pilot.py - quick load scan used to place the arrival-rate sweep and size the seed count.

Run from the repository root (after make_traces.py has made seeds 1..PILOT_SEEDS):
    python3 15_rate_figures/pilot.py

Every method on a wide, even grid of rates with a few seeds, on the stored traces.
Prints per-rate means, and the seed count each figure metric needs for a 95%
half-width at or below its target. Writes pilot_raw.csv and pilot_summary.csv.
"""
import csv
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import exp_config as cfg

PILOT_SEEDS = list(range(1, 9))
PILOT_RATES = [4, 8, 12, 16, 18, 20, 22, 24, 28, 32, 40, 48, 64]
TARGET_HW = {"secure_pct": 0.5, "sec_term_pct": 1.0, "mean_delay": 1.0, "changes_per_1000": 25}


def task(x):
    return cfg.run(*x)


def write_csv(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    for s in PILOT_SEEDS:
        if not os.path.exists(cfg.trace_path(s)):
            sys.exit(f"missing {cfg.trace_path(s)}: run make_traces.py first")
    tasks = [(m, s, r) for r in sorted(PILOT_RATES, reverse=True) for m in cfg.METHODS
             for s in PILOT_SEEDS]
    with ProcessPoolExecutor() as pool:
        rows = list(pool.map(task, tasks, chunksize=1))
    write_csv(os.path.join(cfg.HERE, "pilot_raw.csv"), rows)

    keys = ["secure_pct", "rejected_pct", "sec_term_pct", "mean_delay", "changes_per_1000",
            "fog_util_pct", "cloud_pct", "sla_miss_pct"]
    summary, need = [], {}
    for m in cfg.METHODS:
        for r in sorted(PILOT_RATES):
            rs = [x for x in rows if x["method"] == m and x["rate"] == r]
            s = {"method": m, "rate": r, "n": len(rs)}
            for k in keys:
                mu, hw, _ = cfg.mean_ci([x[k] for x in rs])
                s[k], s[k + "_ci"] = mu, hw
                if k in TARGET_HW and not math.isnan(hw):
                    sd = hw * math.sqrt(len(rs)) / cfg.t975(len(rs) - 1)
                    n_req = math.ceil((1.96 * sd / TARGET_HW[k]) ** 2)
                    need.setdefault(k, []).append((n_req, m, r))
            summary.append(s)
    write_csv(os.path.join(cfg.HERE, "pilot_summary.csv"), summary)

    print(f"{'method':14s} {'rate':>4s} {'secure':>7s} {'reject':>7s} {'secTerm':>8s} "
          f"{'delay':>6s} {'chg/1k':>7s} {'fogCPU':>7s} {'cloud':>6s} {'late':>5s}")
    for s in summary:
        print(f"{s['method']:14s} {s['rate']:4d} {s['secure_pct']:7.2f} {s['rejected_pct']:7.2f} "
              f"{s['sec_term_pct']:8.2f} {s['mean_delay']:6.1f} {s['changes_per_1000']:7.0f} "
              f"{s['fog_util_pct']:7.1f} {s['cloud_pct']:6.1f} {s['sla_miss_pct']:5.2f}")
    print("\nseeds needed for the target 95% half-width (worst method/rate):")
    for k, v in need.items():
        n_req, m, r = max(v)
        print(f"  {k:18s} target +/-{TARGET_HW[k]}: {n_req} seeds (worst: {m} at {r} req/s)")
