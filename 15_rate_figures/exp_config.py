"""
exp_config.py - the one shared setup for every arrival-rate figure in this folder.

Every figure script imports this module. Nothing here runs a simulation; it only
holds settings and the trace loader, so all figures use identical settings.

Model: ../rasp_nsfnet.py unchanged (14-node / 21-link NSFNET, two cloud gateways,
four request classes, three security profiles, nonlinear queueing, incumbents
protected). Its constants are written to config.json by make_traces.py.

Common random numbers: for a given seed, every method and every arrival rate
replays the same pre-generated trace from traces/ (see make_traces.py):
  * one master Poisson trace at RATE_MAX; the trace for rate r keeps the master
    requests whose thinning mark u < r / RATE_MAX. Thinning a Poisson process
    gives a Poisson process at rate r, and the trace at a lower rate is a subset
    of the trace at a higher rate, so curves move smoothly with load;
  * one regional threat trace (birth-death walk, levels 1..3) shared by every
    rate and method.
"""
import gzip
import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import rasp_nsfnet as nf  # noqa: E402

# ---------------------------------------------------------------- run settings
DURATION = 300          # s of arrivals; sessions then run to completion
WARMUP = 60             # sessions arriving before this are not measured
EPOCH = 1.0             # adaptation epoch (s)
TAU_H = 8               # hysteresis interval for RASP-Fog and SA-FF (model default)

# Dynamic threat, one independent walk per region (West, Central, East).
# p_up = p_down = 0.3 makes the walk's stationary distribution uniform over
# levels 1..3 (mean 2), the dynamic counterpart of the fixed theta = 2 used in
# 13_final_figures Fig. 1. Each rise forces mandatory upgrades on running
# sessions, which need extra CPU, memory and bandwidth on already loaded nodes
# (the resource contention); each fall allows downgrades after tau_H.
THREAT_EVERY = 5        # s between threat steps
P_UP = 0.3
P_DOWN = 0.3
THREAT_HORIZON = DURATION + 900   # covers the longest sessions after DURATION

# ---------------------------------------------------------------- traces
RATE_MAX = 64           # master trace rate (req/s); every swept rate must be <= this
TRACE_DIR = os.path.join(HERE, "traces")
ARRIVAL_SEED = lambda s: s            # noqa: E731  Random() seed for the master trace
THINNING_SEED = lambda s: 5000 + s    # noqa: E731  Random() seed for the thinning marks
THREAT_SEED = lambda s: 1000 + s      # noqa: E731  Random() seed for the threat walk

# ---------------------------------------------------------------- experiment grid
METHODS = ["RASP-Fog", "SA-FF", "RASP-Profile", "RASP-Reloc", "Static-Strong"]

# Filled in from the pilot (pilot.py, see README.md): coarse below saturation,
# 1 req/s steps through the knee, coarse again in overload.
RATES = [4, 8, 12, 14, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 28, 32, 40, 48]
SEEDS = list(range(1, 26))            # 25 seeds -> t(0.975, 24) = 2.064

# The four figure metrics (keys returned by nf.simulate, plus derived ones).
FIG_METRICS = {
    "secure_pct":       "Secure completion (%)",
    "sec_term_pct":     "Security-triggered termination (%)",
    "mean_delay":       "Mean end-to-end delay (ms)",
    "changes_per_1000": "Security-profile changes per 1,000 admitted",
}


# ---------------------------------------------------------------- statistics
# Two-sided 95% Student-t critical values, t(0.975, df). Exact to 3 decimals.
_T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
         8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
         15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
         21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056,
         27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042, 35: 2.030, 40: 2.021,
         50: 2.009, 60: 2.000}


def t975(df):
    if df in _T975:
        return _T975[df]
    keys = sorted(_T975)
    return _T975[max(k for k in keys if k <= df)] if df < keys[-1] else 1.960


def mean_ci(vals):
    """Mean and 95% t half-width over seeds (NaNs dropped)."""
    vals = [v for v in vals if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not vals:
        return float("nan"), float("nan"), 0
    if len(vals) == 1:
        return vals[0], float("nan"), 1
    return (statistics.mean(vals),
            t975(len(vals) - 1) * statistics.stdev(vals) / math.sqrt(len(vals)), len(vals))


# ---------------------------------------------------------------- trace I/O
def trace_path(seed):
    return os.path.join(TRACE_DIR, f"seed_{seed:03d}.json.gz")


def load_trace(seed, rate):
    """Arrivals for `rate` req/s and the threat schedule for `seed`, from disk.
    Returns (arrivals, threat) ready for nf.simulate / nf.THREAT."""
    if rate > RATE_MAX:
        raise ValueError(f"rate {rate} > RATE_MAX {RATE_MAX}; regenerate traces")
    with gzip.open(trace_path(seed), "rt") as f:
        tr = json.load(f)
    meta = tr["meta"]
    if meta["rate_max"] != RATE_MAX or meta["duration"] != DURATION:
        raise ValueError(f"{trace_path(seed)} was made with other settings; rerun make_traces.py")
    keep = rate / RATE_MAX
    cols = tr["columns"]
    arrivals = []
    for row in tr["requests"]:
        r = dict(zip(cols, row))
        if r.pop("u") < keep:
            arrivals.append(r)
    threat = {region: [tuple(x) for x in sched] for region, sched in tr["threat"].items()}
    return arrivals, threat


def apply_model_settings():
    """Put the shared model switches in place before each run (worker processes
    start from the module defaults; this pins them explicitly)."""
    nf.PROTECT = True
    nf.TAU_H = TAU_H


def run(method, seed, rate):
    """One simulation of `method` on the stored trace. Returns the metric row."""
    apply_model_settings()
    arrivals, threat = load_trace(seed, rate)
    nf.THREAT = threat
    m = nf.simulate(method, arrivals, DURATION, warmup=WARMUP, epoch=EPOCH)
    n = max(1, m["arrivals"])
    row = {"method": method, "rate": rate, "seed": seed}
    for k in ("secure_pct", "sec_term_pct", "mean_delay", "changes_per_1000",
              "rejected_pct", "terminated_pct", "sla_miss_pct", "fog_util_pct",
              "sec_cpu_pct", "mandatory_reqs", "moves", "upgrades", "downgrades",
              "arrivals", "admitted", "service_failure_pct", "reconfig_ms_per_req"):
        row[k] = m[k]
    row["cloud_pct"] = 100 * m["cloud"] / n
    return row
