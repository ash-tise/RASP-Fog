"""
make_traces.py - pre-generate the request and threat trace for every seed.

Run from the repository root:
    python3 15_rate_figures/make_traces.py          # every seed in exp_config.SEEDS
    python3 15_rate_figures/make_traces.py 1 2 3    # just these seeds

Writes traces/seed_NNN.json.gz (one master Poisson trace at RATE_MAX with a
thinning mark per request, plus the regional threat schedule) and config.json
(every run and model setting). Generation is deterministic: the same seed always
gives the same file, so traces can be regenerated instead of committed.
"""
import gzip
import json
import os
import random
import sys

import exp_config as cfg
from exp_config import nf

COLUMNS = ["id", "kind", "t", "ingress", "sigma", "c", "m", "b", "deadline", "end", "u"]


def make_trace(seed):
    arrivals = nf.make_arrivals(random.Random(cfg.ARRIVAL_SEED(seed)), cfg.RATE_MAX, cfg.DURATION)
    mark = random.Random(cfg.THINNING_SEED(seed))
    rows = [[r[c] for c in COLUMNS[:-1]] + [mark.random()] for r in arrivals]
    threat = nf.random_threat(random.Random(cfg.THREAT_SEED(seed)), cfg.THREAT_HORIZON,
                              cfg.P_UP, p_down=cfg.P_DOWN, every=cfg.THREAT_EVERY)
    return {"meta": {"seed": seed, "rate_max": cfg.RATE_MAX, "duration": cfg.DURATION,
                     "p_up": cfg.P_UP, "p_down": cfg.P_DOWN, "threat_every": cfg.THREAT_EVERY,
                     "n_master": len(rows)},
            "columns": COLUMNS, "requests": rows, "threat": threat}


def config():
    return {
        "duration_s": cfg.DURATION, "warmup_s": cfg.WARMUP, "epoch_s": cfg.EPOCH,
        "tau_h_s": cfg.TAU_H, "threat_step_s": cfg.THREAT_EVERY, "threat_p_up": cfg.P_UP,
        "threat_p_down": cfg.P_DOWN, "threat_horizon_s": cfg.THREAT_HORIZON,
        "rate_max": cfg.RATE_MAX, "methods": cfg.METHODS, "rates": cfg.RATES,
        "seeds": cfg.SEEDS, "t95": cfg.t975(len(cfg.SEEDS) - 1),
        "seed_streams": {"arrivals": "Random(seed)", "thinning": "Random(5000 + seed)",
                         "threat": "Random(1000 + seed)"},
        "model": {
            "lambda_d": nf.LAMBDA_D, "lambda_o": nf.LAMBDA_O, "omega": nf.OMEGA,
            "links": nf.NSFNET_LINKS, "link_delay_ms": nf.LINK_DELAY_MS,
            "link_bw_mbps": nf.LINK_BW, "small_node": nf.SMALL, "large_node": nf.LARGE,
            "large_nodes": [j for j in nf.FOG if j % 2], "cloud_gateways": nf.CLOUD_GATEWAYS,
            "wan_delay_ms": nf.WAN_DELAY_MS, "wan_bw_mbps": nf.WAN_BW, "cloud_mu": nf.CLOUD_MU,
            "chi_ms": nf.CHI_MS, "max_util": nf.MAX_UTIL, "profiles": nf.PROFILES,
            "rho_ms_per_level": nf.RHO_PER_LEVEL, "psi_move_ms": nf.PSI_MOVE,
            "request_classes": nf.TYPES, "demand_spread": nf.SPREAD, "regions": nf.REGIONS,
            "protect_incumbents": True, "policies": {m: nf.POLICIES[m] for m in cfg.METHODS},
        },
    }


if __name__ == "__main__":
    seeds = [int(s) for s in sys.argv[1:]] or cfg.SEEDS
    os.makedirs(cfg.TRACE_DIR, exist_ok=True)
    for s in seeds:
        tr = make_trace(s)
        # mtime=0 keeps the .gz bytes identical across regenerations
        with open(cfg.trace_path(s), "wb") as raw, \
                gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as f:
            f.write(json.dumps(tr, separators=(",", ":")).encode())
        print(f"seed {s}: {tr['meta']['n_master']} master requests")
    with open(os.path.join(cfg.HERE, "config.json"), "w") as f:
        json.dump(config(), f, indent=1, default=str)
