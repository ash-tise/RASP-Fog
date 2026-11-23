"""
baseline_config.py - settings for the placement-baseline comparison (test 16).

Reuses the run settings, traces, threat and statistics of ../15_rate_figures
(same 25 seeds, same request and threat trace per seed for every method, rate
and scenario). Only the methods, the capacity scenarios and the rate grids are
new here.

Methods (all share the same security adaptation: adaptive profile, relocation,
tau_H = 8 s; only the placement rule at admission and relocation differs):
    RASP-Fog  min J over every feasible (node, profile)              (proposed)
    SA-FF     first feasible node by hops from the ingress, cloud last
    LA        latency-aware: min end-to-end delay over every feasible (node, profile)
    LB        load-aware: fog node with the lowest projected CPU utilization
              after placement; cloud only if no fog node is feasible
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "15_rate_figures"))
import exp_config as base  # noqa: E402  (15_rate_figures/exp_config.py)

nf = base.nf
SEEDS = base.SEEDS
mean_ci = base.mean_ci
trace_path = base.trace_path

METHODS = ["RASP-Fog", "SA-FF", "LA", "LB"]

# Capacity scenarios. "nominal" is the model of tests 13-15 unchanged.
# "constrained" halves every fog node's CPU, memory and interface bandwidth, caps
# the cloud at 200 CPU units (one large fog node) and halves each WAN uplink to
# 500 Mbps. Fixed before any result was seen; in the pilot the cloud CPU cap is
# reached from about 16 req/s on, and the WAN uplinks stay below ~330 Mbps.
SCENARIOS = {
    "nominal":     {"fog_scale": 1.0, "cloud_cpu": float("inf"), "wan_bw": 1000},
    "constrained": {"fog_scale": 0.5, "cloud_cpu": 200,          "wan_bw": 500},
}

# Rate grids: dense through each scenario's knee (nominal ~18 req/s, constrained ~9).
RATES = {
    "nominal":     base.RATES,
    "constrained": [2, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 20, 24],
}

METRICS = ["secure_pct", "sec_term_pct", "mean_delay", "changes_per_1000",
           "rejected_pct", "terminated_pct", "sla_miss_pct", "fog_util_pct",
           "sec_cpu_pct", "cloud_pct", "mandatory_reqs", "moves", "arrivals", "admitted",
           "service_failure_pct", "reconfig_ms_per_req"]


def apply_scenario(name):
    s = SCENARIOS[name]
    nf.FOG_SCALE, nf.CLOUD_CPU, nf.WAN_BW = s["fog_scale"], s["cloud_cpu"], s["wan_bw"]


def run(scenario, method, seed, rate):
    apply_scenario(scenario)
    row = base.run(method, seed, rate)
    row["scenario"] = scenario
    return row
