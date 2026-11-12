"""rate_check.py - do the tuned weights hold away from the knee? Evaluation seeds,
fixed theta=2, omega default, lambda_D in {0.25, 0.4, 0.5 (default)}, plus SA-FF."""
import csv, os, sys, statistics as st, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sweep
from concurrent.futures import ProcessPoolExecutor
RATES = [16, 24, 32, 40, 48]
OM = (1/3, 1/3, 1/3)

def one(t):
    rate, method, lam, seed = t
    sweep.RATE = rate
    r = sweep.run_one(("fixed_theta2", method, lam, OM, seed)); r["rate"] = rate
    return r

if __name__ == "__main__":
    tasks = [(rate, m, lam, s) for rate in RATES
             for m, lam in (("RASP-Fog", 0.25), ("RASP-Fog", 0.4), ("RASP-Fog", 0.5), ("SA-FF", 0.5))
             for s in sweep.EVAL_SEEDS]
    with ProcessPoolExecutor() as p:
        rows = list(p.map(one, tasks, chunksize=2))
    with open(os.path.join(HERE, "rate_check_raw.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for rate in RATES:
        for m, lam in (("RASP-Fog", 0.25), ("RASP-Fog", 0.4), ("RASP-Fog", 0.5), ("SA-FF", 0.5)):
            rs = [r for r in rows if r["rate"] == rate and r["method"] == m and r["lambda_d"] == lam]
            f = lambda k: st.mean(r[k] for r in rs)
            ci = 2.262 * st.stdev(r["secure_pct"] for r in rs) / math.sqrt(len(rs))
            print(f"{rate:3d} {m:9s} lD={lam:<4} secure {f('secure_pct'):6.2f}±{ci:.2f}  secCPU {f('sec_cpu_pct'):5.2f}"
                  f"  cloud {f('cloud_pct'):5.1f}%  fogCPU {f('fog_util_pct'):5.1f}  delay {f('mean_delay'):5.1f}")
