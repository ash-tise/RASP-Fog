"""
arrival_rate_test.py - secure request completion vs arrival rate, at a fixed threat level.

Run it from the repository root:   python3 06_arrival_rate_testing/arrival_rate_test.py

Same model and policies as ../rasp_core.py, rescaled so the network saturates
inside the 20-300 req/s range:
  * requests are short tasks (exponential holding time, mean 0.5-1.5 s),
  * every node's CPU, memory and bandwidth are multiplied by CAPACITY_SCALE,
  * the threat level is fixed for the whole run,
  * resources are released when a request finishes,
  * an orchestrator setup delay SETUP_MS is added to every admission.
Within a seed, every policy sees exactly the same requests.

With a fixed threat, the required profile of a request never changes after
admission, so Algorithm 2 never triggers and No-Hysteresis / No-Relocation
behave exactly like RASP-Fog. They are left out of this test.

Writes arrival_rate_results.csv and fig1_secure_completion.png (needs matplotlib).
"""
import csv
import heapq
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import rasp_core as core

# ---------------------------------------------------------------- test settings
RATES = [20, 40, 60, 80, 100, 150, 200, 250, 300, 350, 400]  # average arrivals per second
SEEDS = [1, 2, 3, 4, 5]
POLICIES = ["RASP-Fog", "Static-Strong", "Static-Light"]
THREAT = 2                                # fixed threat level for the whole run
RUN_S = 60                                # seconds simulated per run
WARMUP_S = 10                             # arrivals before this are not counted
MEAN_HOLD = {"sensor": 1.0, "camera": 1.5, "health": 0.5}   # seconds
CAPACITY_SCALE = 10                       # multiplies every node's cpu, mem and bw
SETUP_MS = 5                              # orchestrator round trip at admission (ms)
T95 = 2.776                               # t value for a 95% CI with 5 seeds

core.THREAT_SCHEDULE = [(0, THREAT)]
for n in core.NODES.values():
    for key in ("cpu", "mem", "bw"):
        n[key] *= CAPACITY_SCALE
FOG = [name for name in core.NODES if name != "Cloud"]


# ---------------------------------------------------------------- resource totals
# core.used() re-adds every active request on each call, which is too slow at
# 300 req/s. The test keeps a running total per node instead; the totals are
# checked against core.used() at the end of every run.
USAGE = {}
core_used = core.used


def tracked_used(node, active, skip=None):
    c, m, b = USAGE[node]
    if skip is not None and skip.get("node") == node:
        dc, dm, db = core.demand(skip, skip["k"])
        c, m, b = c - dc, m - dm, b - db
    return c, m, b


def reserve(req, sign):
    dc, dm, db = core.demand(req, req["k"])
    c, m, b = USAGE[req["node"]]
    USAGE[req["node"]] = (c + sign * dc, m + sign * dm, b + sign * db)


# ---------------------------------------------------------------- random world
def make_arrivals(rate, seed):
    """Poisson arrivals with random types and holding times, shared by every policy."""
    rng = random.Random(seed)
    arrivals, t, rid = [], 0.0, 0
    while True:
        t += rng.expovariate(rate)
        if t >= RUN_S:
            return arrivals
        rid += 1
        kind = rng.choice(list(core.TYPES))
        hold = rng.expovariate(1 / MEAN_HOLD[kind])
        arrivals.append({"id": rid, "kind": kind, "t": t, "end": t + hold, **core.TYPES[kind]})


# ---------------------------------------------------------------- one run
def run_once(policy_name, rate, seed):
    policy = core.POLICIES[policy_name]
    arrivals = make_arrivals(rate, seed)
    USAGE.clear()
    USAGE.update({name: (0.0, 0.0, 0.0) for name in core.NODES})
    core.used = tracked_used

    active, log, running = [], [], []        # running: heap of (end, id, req)
    for a in arrivals:
        req = dict(a)
        while running and running[0][0] <= req["t"]:     # completions release resources
            _, _, done = heapq.heappop(running)
            active.remove(done)
            reserve(done, -1)
        req["deadline"] -= SETUP_MS                      # setup time uses up part of the deadline
        core.admit(req, req["t"], active, log, policy)
        req["deadline"] += SETUP_MS
        if "node" in req:
            req["delay"] += SETUP_MS
            reserve(req, +1)
            heapq.heappush(running, (req["end"], req["id"], req))
        for name, n in core.NODES.items():
            c, m, b = USAGE[name]
            if c > n["cpu"] + 1e-6 or m > n["mem"] + 1e-6 or b > n["bw"] + 1e-6:
                raise RuntimeError(f"{name} over capacity")

    core.used = core_used
    for name in core.NODES:                                # running totals are exact
        exact = core.used(name, active)
        assert all(abs(x - y) < 1e-6 for x, y in zip(exact, USAGE[name])), name

    counted = [r for r in log if r[2]["t"] >= WARMUP_S]
    admitted = [r[2] for r in counted if r[1] == "ADMIT"]
    n = max(1, sum(1 for a in arrivals if a["t"] >= WARMUP_S))
    secure = [r for r in admitted if r["k"] >= core.required(r["sigma"], THREAT)]
    return {
        "secure_pct": 100 * len(secure) / n,
        "reject_pct": 100 * sum(1 for r in counted if r[1] == "REJECT") / n,
        "under_pct": 100 * (len(admitted) - len(secure)) / n,
        "cloud_pct": 100 * sum(1 for r in admitted if r["node"] == "Cloud") / n,
        "delay_ms": sum(r["delay"] for r in admitted) / max(1, len(admitted)),
    }


def mean_ci(values):
    m = sum(values) / len(values)
    sd = (sum((v - m) ** 2 for v in values) / (len(values) - 1)) ** 0.5
    return m, T95 * sd / len(values) ** 0.5


# ---------------------------------------------------------------- plot
def plot(rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"RASP-Fog": "#2a78d6", "Static-Strong": "#eb6834", "Static-Light": "#1baf7a"}
    markers = {"RASP-Fog": "o", "Static-Strong": "s", "Static-Light": "^"}
    fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=200)
    for name in POLICIES:
        pts = [r for r in rows if r["policy"] == name]
        ax.errorbar([r["rate"] for r in pts], [r["secure_pct"] for r in pts],
                    yerr=[r["secure_pct_ci"] for r in pts], label=name,
                    color=colors[name], marker=markers[name], markersize=6,
                    linewidth=2, capsize=3)
    ax.set_xlabel("Arrival rate (requests/s)")
    ax.set_ylabel("Secure request completion (%)")
    ax.set_xticks(range(0, max(RATES) + 1, 50))
    ax.set_ylim(-3, 103)
    ax.grid(True, color="#e4e3df", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False, loc="center left")
    fig.tight_layout()
    fig.savefig(path)


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    print(f"Arrival-rate test: threat fixed at {THREAT}, {RUN_S} s per run "
          f"({WARMUP_S} s warm-up), capacity x{CAPACITY_SCALE}, seeds {SEEDS}\n")
    rows = []
    for rate in RATES:
        for name in POLICIES:
            runs = [run_once(name, rate, s) for s in SEEDS]
            row = {"rate": rate, "policy": name}
            for key in runs[0]:
                row[key], row[key + "_ci"] = mean_ci([r[key] for r in runs])
            rows.append(row)

    for key, title in [("secure_pct", "Secure request completion (% of arrivals)"),
                       ("reject_pct", "Rejected (% of arrivals)"),
                       ("cloud_pct", "Admitted to the cloud (% of arrivals)"),
                       ("delay_ms", "Average end-to-end delay of admitted requests (ms)")]:
        print(title)
        print(f"  {'rate':>5}" + "".join(f"{n:>22}" for n in POLICIES))
        for rate in RATES:
            cells = []
            for n in POLICIES:
                r = next(x for x in rows if x["rate"] == rate and x["policy"] == n)
                cells.append(f"{r[key]:.1f} ± {r[key + '_ci']:.1f}")
            print(f"  {rate:>5}" + "".join(f"{c:>22}" for c in cells))
        print()

    with open(os.path.join(HERE, "arrival_rate_results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("Results saved to arrival_rate_results.csv")

    try:
        plot(rows, os.path.join(HERE, "fig1_secure_completion.png"))
        print("Figure saved to fig1_secure_completion.png")
    except ImportError:
        print("matplotlib not installed: figure skipped (pip install matplotlib)")
