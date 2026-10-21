"""
random_test.py - RASP-Fog and the baselines under random traffic at several loads.

Run it with:   python3 random_test.py

Same model and policies as ../rasp_core.py, plus:
  * random arrivals (Poisson, RATE requests per second on average),
  * random request types and random durations (exponential, mean per type),
  * a random threat level, updated every 10 s (up, down or unchanged),
  * resources released when a request finishes,
  * an orchestrator setup delay SETUP_MS added to every admission.
Each load level is run with several seeds. Within a seed, every policy sees
exactly the same requests and threat changes. Results are averaged over seeds.
"""
import csv
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import rasp_core as core

# ---------------------------------------------------------------- test settings
RATES = [0.5, 1.0, 1.5, 2.0, 2.5]          # average arrivals per second
SEEDS = [1, 2, 3, 4, 5]
core.STEPS = 300                          # seconds per run
MEAN_DURATION = {"sensor": 20, "camera": 30, "health": 10}   # seconds
THREAT_EVERY = 10                         # threat update interval (s)
P_UP, P_DOWN = 0.3, 0.3                   # chance the threat goes up / down at an update
SETUP_MS = 5                              # orchestrator round trip at admission (ms)


# ---------------------------------------------------------------- random world
def poisson(rng, mean):
    """Number of arrivals in one second (Knuth's method)."""
    limit, k, p = math.exp(-mean), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def make_world(rate, seed):
    """Random requests and threat changes, shared by every policy for this seed."""
    rng = random.Random(seed)
    schedule, level = [(0, 1)], 1
    for t in range(THREAT_EVERY, core.STEPS, THREAT_EVERY):
        r = rng.random()
        if r < P_UP and level < 3:
            level += 1
        elif r > 1 - P_DOWN and level > 1:
            level -= 1
        schedule.append((t, level))
    arrivals, rid = [], 0
    for t in range(core.STEPS):
        for _ in range(poisson(rng, rate)):
            rid += 1
            kind = rng.choice(list(core.TYPES))
            dur = max(1, round(rng.expovariate(1 / MEAN_DURATION[kind])))
            arrivals.append({"id": rid, "kind": kind, "t": t, "end": t + dur,
                             **core.TYPES[kind]})
    return schedule, arrivals


# ---------------------------------------------------------------- run with release
def run_random(policy, schedule, arrivals):
    core.THREAT_SCHEDULE = schedule
    active, log, problems = [], [], []
    by_time = {}
    for a in arrivals:
        by_time.setdefault(a["t"], []).append(dict(a))   # fresh copy per policy
    for t in range(core.STEPS):
        for req in [r for r in active if r["end"] <= t]:  # completion: release resources
            active.remove(req)
            log.append((t, "COMPLETE", req, ""))
        for req in list(active):                           # Algorithm 2
            core.adapt(req, t, active, log, policy)
        for req in by_time.get(t, []):                     # Algorithm 1, with setup delay:
            req["deadline"] -= SETUP_MS                    # the setup time uses up part of
            core.admit(req, t, active, log, policy)        # the deadline at admission
            req["deadline"] += SETUP_MS
            if "delay" in req:
                req["delay"] += SETUP_MS
        for r in active:
            if r["k"] < core.required(r["sigma"], core.threat(t)):
                r["under"] = True
                problems.append("under")
        for node, n in core.NODES.items():
            c, m, b = core.used(node, active)
            if c > n["cpu"] + 1e-9 or m > n["mem"] + 1e-9 or b > n["bw"] + 1e-9:
                problems.append("capacity")
    return log, problems


def measure(policy, rate, seed):
    schedule, arrivals = make_world(rate, seed)
    log, problems = run_random(policy, schedule, arrivals)
    admitted = [x[2] for x in log if x[1] == "ADMIT"]
    terminated = {x[2]["id"] for x in log if x[1] == "TERMINATE"}
    under = {r["id"] for r in admitted if r.get("under")}
    n = max(1, len(arrivals))
    return {
        "secure_pct": 100 * sum(1 for r in admitted if r["id"] not in terminated | under) / n,
        "reject_pct": 100 * core.count(log, "REJECT") / n,
        "under_pct": 100 * len(under) / n,
        "terminated": len(terminated),
        "moves": core.count(log, "MOVE"),
        "changes_per_req": core.profile_changes(log) / max(1, len(admitted)),
        "delay_ms": sum(r["delay"] for r in admitted) / max(1, len(admitted)),
        "overcap": problems.count("capacity"),
    }


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    print(f"Random test: {core.STEPS} s per run, rates {RATES} req/s, seeds {SEEDS}, "
          f"setup delay {SETUP_MS} ms\n")
    rows = []
    for rate in RATES:
        for name, policy in core.POLICIES.items():
            runs = [measure(policy, rate, s) for s in SEEDS]
            avg = {k: sum(r[k] for r in runs) / len(runs) for k in runs[0]}
            rows.append({"rate": rate, "policy": name, **avg})

    names = list(core.POLICIES)
    tables = [
        ("secure_pct", "Secure requests (% of all arrivals; higher is better)", "{:>15.1f}"),
        ("reject_pct", "Rejected (% of all arrivals)", "{:>15.1f}"),
        ("under_pct", "Ever under-protected (% of all arrivals)", "{:>15.1f}"),
        ("terminated", "Terminated (per run)", "{:>15.1f}"),
        ("moves", "Relocations (per run)", "{:>15.1f}"),
        ("changes_per_req", "Profile changes per admitted request", "{:>15.2f}"),
        ("delay_ms", "Average delay at admission (ms, incl. setup)", "{:>15.1f}"),
    ]
    for key, title, fmt in tables:
        print(title)
        print(f"  {'rate':>5}" + "".join(f"{n:>15}" for n in names))
        for rate in RATES:
            vals = [next(r[key] for r in rows if r["rate"] == rate and r["policy"] == n)
                    for n in names]
            print(f"  {rate:>5}" + "".join(fmt.format(v) for v in vals))
        print()

    out = os.path.join(HERE, "random_results.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("Averages saved to random_results.csv")

    rasp = [r for r in rows if r["policy"] == "RASP-Fog"]
    print("\nRASP-Fog checks (all rates, all seeds):")
    print(f"  [{'PASS' if all(r['under_pct'] == 0 for r in rasp) else 'FAIL'}] Never under-protected")
    print(f"  [{'PASS' if all(r['overcap'] == 0 for r in rows) else 'FAIL'}] No node ever over capacity")
