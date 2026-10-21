"""
efficiency_test.py - how many resources each policy spends on security,
with 95% confidence intervals.

Run it with:   python3 efficiency_test.py

Uses the same random traffic as ../random_testing/random_test.py (same rates,
seeds, durations, threat process and 5 ms setup delay). Every second it also
records how much CPU, memory and bandwidth active requests spend on their
security profile, on top of their base demand.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "random_testing"))
import rasp_core as core
import random_test as rt

T95 = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 8: 2.365, 10: 2.262}  # t-values
PM = "±"


def overhead(req):
    """Security overhead of one active request: extra CPU, memory, bandwidth."""
    p = core.PROFILES[req["k"]]
    return req["c"] * p["dc"], req["m"] * p["dm"], req["b"] * p["db"]


def run_tracked(policy, schedule, arrivals):
    """random_test.run_random plus per-second tracking of security overhead."""
    core.THREAT_SCHEDULE = schedule
    active, log = [], []
    sec_cpu = sec_mem = sec_bw = total_cpu = 0.0
    by_time = {}
    for a in arrivals:
        by_time.setdefault(a["t"], []).append(dict(a))    # fresh copy per policy
    for t in range(core.STEPS):
        for req in [r for r in active if r["end"] <= t]:   # completion: release resources
            active.remove(req)
            log.append((t, "COMPLETE", req, ""))
        for req in list(active):                            # Algorithm 2
            core.adapt(req, t, active, log, policy)
        for req in by_time.get(t, []):                      # Algorithm 1 with setup delay
            req["deadline"] -= rt.SETUP_MS
            core.admit(req, t, active, log, policy)
            req["deadline"] += rt.SETUP_MS
            if "delay" in req:
                req["delay"] += rt.SETUP_MS
        for r in active:                                    # record this second
            if r["k"] < core.required(r["sigma"], core.threat(t)):
                r["under"] = True
            dc, dm, db = overhead(r)
            sec_cpu, sec_mem, sec_bw = sec_cpu + dc, sec_mem + dm, sec_bw + db
            total_cpu += core.demand(r, r["k"])[0]
    admitted = [x[2] for x in log if x[1] == "ADMIT"]
    terminated = {x[2]["id"] for x in log if x[1] == "TERMINATE"}
    under = {r["id"] for r in admitted if r.get("under")}
    secure = sum(1 for r in admitted if r["id"] not in terminated | under)
    return {
        "secure_pct": 100 * secure / max(1, len(arrivals)),
        "sec_cpu": sec_cpu / core.STEPS,                    # CPU units on security, time average
        "sec_share": 100 * sec_cpu / max(1e-9, total_cpu),  # % of CPU in use spent on security
        "sec_cpu_per_secure": sec_cpu / max(1, secure),     # CPU unit-seconds per secure request
        "sec_mem": sec_mem / core.STEPS,
        "sec_bw": sec_bw / core.STEPS,
    }


def mean_ci(values):
    """Mean and half-width of the 95% confidence interval (t-distribution)."""
    n = len(values)
    m = sum(values) / n
    if n < 2:
        return m, 0.0
    sd = math.sqrt(sum((v - m) ** 2 for v in values) / (n - 1))
    return m, T95.get(n, 1.96) * sd / math.sqrt(n)


if __name__ == "__main__":
    print(f"Efficiency test: {core.STEPS} s per run, rates {rt.RATES} req/s, seeds {rt.SEEDS}, "
          f"setup delay {rt.SETUP_MS} ms. Values are mean {PM} 95% CI over seeds.\n")
    names = list(core.POLICIES)
    res = {}   # (rate, policy) -> one result per seed
    for rate in rt.RATES:
        for seed in rt.SEEDS:
            schedule, arrivals = rt.make_world(rate, seed)
            for name, policy in core.POLICIES.items():
                res.setdefault((rate, name), []).append(run_tracked(policy, schedule, arrivals))

    tables = [
        ("secure_pct", "Secure requests (% of arrivals)", 1),
        ("sec_cpu", "CPU spent on security (units in use, time average)", 2),
        ("sec_share", "Share of used CPU spent on security (%)", 1),
        ("sec_cpu_per_secure", "Security CPU per secure request (unit-seconds)", 2),
        ("sec_mem", "Memory spent on security (MB in use, time average)", 0),
        ("sec_bw", "Bandwidth spent on security (Mbps in use, time average)", 2),
    ]
    for key, title, dec in tables:
        print(title)
        print(f"  {'rate':>5}" + "".join(f"{n:>17}" for n in names))
        for rate in rt.RATES:
            cells = []
            for n in names:
                m, ci = mean_ci([r[key] for r in res[(rate, n)]])
                cells.append(f"{m:.{dec}f} {PM} {ci:.{dec}f}")
            print(f"  {rate:>5}" + "".join(f"{c:>17}" for c in cells))
        print()

    print("RASP-Fog minus Static-Strong, paired by seed (same requests and threat):")
    print(f"  {'rate':>5}{'secure (pts)':>20}{'security CPU (units)':>25}")
    for rate in rt.RATES:
        a, b = res[(rate, "RASP-Fog")], res[(rate, "Static-Strong")]
        ds, sci = mean_ci([x["secure_pct"] - y["secure_pct"] for x, y in zip(a, b)])
        dc, cci = mean_ci([x["sec_cpu"] - y["sec_cpu"] for x, y in zip(a, b)])
        s1 = f"{ds:+.2f} {PM} {sci:.2f}" + ("*" if abs(ds) > sci else " ")
        s2 = f"{dc:+.2f} {PM} {cci:.2f}" + ("*" if abs(dc) > cci else " ")
        print(f"  {rate:>5}{s1:>20}{s2:>25}")
    print("  * = the 95% interval excludes zero, so the difference is real at this sample size")
