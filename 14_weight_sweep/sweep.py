"""
sweep.py - does changing the objective weights help RASP-Fog?

Weights swept:
    lambda_D / lambda_O   delay vs overhead in J  (lambda_O = 1 - lambda_D)
    omega = (C, M, B)     weights inside the overhead term o_ijk

Method (to avoid tuning on the traces we report):
  1. Tune: run every weight combination on TUNE_SEEDS (101-110), which share no
     request or threat trace with the 10 evaluation seeds used for the figures.
  2. Pick the best combination per scenario by mean secure completion on the
     tuning seeds (ties: lower security CPU).
  3. Evaluate: rerun the picked weights, the default weights, SA-FF and
     Static-Strong on EVAL_SEEDS (1-10) and report paired differences.

The committed defaults in rasp_nsfnet.py are NOT changed; weights are set per run.

Run from the repository root:   python3 14_weight_sweep/sweep.py
"""
import csv
import itertools
import math
import os
import random
import statistics
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import rasp_nsfnet as nf

TUNE_SEEDS = list(range(101, 111))
EVAL_SEEDS = list(range(1, 11))
T95 = 2.262
DURATION, WARMUP = 300, 60
RATE = 24
SCENARIOS = {"fixed_theta2": ("fixed", 2), "walk_p0.3": ("walk", 0.3)}

LAMBDA_D = [0.0, 0.25, 0.5, 0.75, 1.0]
OMEGAS = [(1/3, 1/3, 1/3), (1, 0, 0), (0, 1, 0), (0, 0, 1),
          (0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5), (0.6, 0.2, 0.2)]
DEFAULT = (0.5, (1/3, 1/3, 1/3))
KEYS = ["secure_pct", "sec_cpu_pct", "rejected_pct", "sla_violation_pct", "sec_term_pct",
        "fog_util_pct", "mean_delay", "cloud_pct"]


def run_one(task):
    scen, method, lam_d, omega, seed = task
    kind, val = SCENARIOS[scen]
    nf.PROTECT, nf.TAU_H = True, 8
    nf.LAMBDA_D, nf.LAMBDA_O, nf.OMEGA = lam_d, 1 - lam_d, omega
    if kind == "fixed":
        nf.THREAT = nf.uniform_threat([(0, val)])
    else:
        nf.THREAT = nf.random_threat(random.Random(1000 + seed), DURATION + 600, val,
                                     p_down=0.3, every=5)
    arr = nf.make_arrivals(random.Random(seed), RATE, DURATION)
    m = nf.simulate(method, arr, DURATION, warmup=WARMUP)
    row = {"scenario": scen, "method": method, "lambda_d": lam_d,
           "omega": "/".join(f"{w:.2f}" for w in omega), "seed": seed}
    for k in KEYS:
        row[k] = 100 * m["cloud"] / max(1, m["arrivals"]) if k == "cloud_pct" else m[k]
    return row


def grid(tasks):
    with ProcessPoolExecutor() as pool:
        return list(pool.map(run_one, tasks, chunksize=2))


def mean_ci(vals):
    m = statistics.mean(vals)
    return m, (T95 * statistics.stdev(vals) / math.sqrt(len(vals)) if len(vals) > 1 else 0.0)


def write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
        w.writeheader()
        w.writerows(rows)


def main():
    combos = [(l, o) for l in LAMBDA_D for o in OMEGAS]
    # omega is irrelevant when lambda_O = 0: keep only one omega there
    combos = [(l, o) for l, o in combos if l < 1.0 or o == OMEGAS[0]]

    # 1. tuning
    tune_rows = grid([(s, "RASP-Fog", l, o, seed) for s in SCENARIOS
                      for l, o in combos for seed in TUNE_SEEDS])
    write(os.path.join(HERE, "tune_raw.csv"), tune_rows)
    tune_summary, best = [], {}
    for s in SCENARIOS:
        for l, o in combos:
            om = "/".join(f"{w:.2f}" for w in o)
            rs = [r for r in tune_rows if r["scenario"] == s and r["lambda_d"] == l and r["omega"] == om]
            row = {"scenario": s, "lambda_d": l, "omega": om}
            for k in KEYS:
                row[k], row[k + "_ci"] = mean_ci([r[k] for r in rs])
            tune_summary.append(row)
        cand = [r for r in tune_summary if r["scenario"] == s]
        b = max(cand, key=lambda r: (round(r["secure_pct"], 6), -r["sec_cpu_pct"]))
        best[s] = (b["lambda_d"], tuple(float(x) for x in b["omega"].split("/")))
    write(os.path.join(HERE, "tune_summary.csv"), tune_summary)

    # 2. evaluation on held-out seeds
    tasks = []
    for s in SCENARIOS:
        for label, method, (l, o) in (("RASP-Fog default", "RASP-Fog", DEFAULT),
                                      ("RASP-Fog tuned", "RASP-Fog", best[s]),
                                      ("SA-FF", "SA-FF", DEFAULT),
                                      ("Static-Strong", "Static-Strong", DEFAULT)):
            tasks += [(s, method, l, o, seed) for seed in EVAL_SEEDS]
    eval_rows = grid(tasks)
    labels = ["RASP-Fog default", "RASP-Fog tuned", "SA-FF", "Static-Strong"]
    for i, r in enumerate(eval_rows):
        r["label"] = labels[(i // len(EVAL_SEEDS)) % 4]
    write(os.path.join(HERE, "eval_raw.csv"), eval_rows)

    out = []
    for s in SCENARIOS:
        print(f"\n== {s} @ {RATE} req/s; tuned weights: lambda_D={best[s][0]}, "
              f"omega={tuple(round(w, 2) for w in best[s][1])}")
        by = {lab: {r["seed"]: r for r in eval_rows if r["scenario"] == s and r["label"] == lab}
              for lab in labels}
        for lab in labels:
            row = {"scenario": s, "label": lab, "lambda_d": by[lab][1]["lambda_d"],
                   "omega": by[lab][1]["omega"]}
            for k in KEYS:
                row[k], row[k + "_ci"] = mean_ci([r[k] for r in by[lab].values()])
                if lab != "RASP-Fog default":
                    row[k + "_vs_default"], row[k + "_vs_default_ci"] = mean_ci(
                        [by[lab][x][k] - by["RASP-Fog default"][x][k] for x in EVAL_SEEDS])
            out.append(row)
            print(f"  {lab:17s} secure {row['secure_pct']:.2f}±{row['secure_pct_ci']:.2f}  "
                  f"secCPU {row['sec_cpu_pct']:.2f}±{row['sec_cpu_pct_ci']:.2f}  "
                  f"term {row['sec_term_pct']:.2f}  delay {row['mean_delay']:.1f} ms"
                  + ("" if lab == "RASP-Fog default" else
                     f"   | vs default: secure {row['secure_pct_vs_default']:+.2f}"
                     f"±{row['secure_pct_vs_default_ci']:.2f}, secCPU "
                     f"{row['sec_cpu_pct_vs_default']:+.2f}±{row['sec_cpu_pct_vs_default_ci']:.2f}"))
    write(os.path.join(HERE, "eval_summary.csv"), out)


if __name__ == "__main__":
    main()
