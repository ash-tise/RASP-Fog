"""
security_cpu_test.py - security-related CPU utilization of the fog vs arrival rate.

Run it from the repository root:   python3 07_security_cpu_testing/security_cpu_test.py

Uses exactly the same settings, requests and policies as
../06_arrival_rate_testing/arrival_rate_test.py (fixed threat, short tasks,
capacity x10). Only the measurement is new:

  security CPU utilization = CPU reserved for security overhead on the fog nodes
                             (base demand excluded) / total fog CPU capacity,
  averaged over time after the warm-up.

The total fog CPU utilization (base + security) is recorded as well.

Writes security_cpu_results.csv and fig3_security_cpu.png (needs matplotlib).
"""
import csv
import heapq
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "06_arrival_rate_testing"))
import rasp_core as core
import arrival_rate_test as base          # applies the 06 settings to rasp_core

FOG_CPU = sum(core.NODES[name]["cpu"] for name in base.FOG)


def security_cpu(req):
    """CPU reserved for the request's security profile only (base demand excluded)."""
    return req["c"] * core.PROFILES[req["k"]]["dc"]


# ---------------------------------------------------------------- one run
def run_once(policy_name, rate, seed):
    policy = core.POLICIES[policy_name]
    arrivals = base.make_arrivals(rate, seed)
    base.USAGE.clear()
    base.USAGE.update({name: (0.0, 0.0, 0.0) for name in core.NODES})
    core.used = base.tracked_used

    active, log, running = [], [], []
    sec_now = total_now = 0.0               # fog CPU in use right now
    sec_area = total_area = 0.0             # integrals over time after the warm-up
    last_t = 0.0

    def advance(t):
        nonlocal last_t, sec_area, total_area
        start, end = max(last_t, base.WARMUP_S), min(t, base.RUN_S)
        if end > start:
            sec_area += sec_now * (end - start)
            total_area += total_now * (end - start)
        last_t = t

    def change(req, sign):
        nonlocal sec_now, total_now
        base.reserve(req, sign)
        if req["node"] in base.FOG:
            sec_now += sign * security_cpu(req)
            total_now += sign * core.demand(req, req["k"])[0]

    def release_until(t):
        while running and running[0][0] <= t:
            end, _, done = heapq.heappop(running)
            advance(end)
            active.remove(done)
            change(done, -1)

    for a in arrivals:
        req = dict(a)
        release_until(req["t"])
        advance(req["t"])
        req["deadline"] -= base.SETUP_MS
        core.admit(req, req["t"], active, log, policy)
        req["deadline"] += base.SETUP_MS
        if "node" in req:
            change(req, +1)
            heapq.heappush(running, (req["end"], req["id"], req))
    release_until(base.RUN_S)
    advance(base.RUN_S)

    core.used = base.core_used
    for name in core.NODES:                                # running totals are exact
        exact = core.used(name, active)
        assert all(abs(x - y) < 1e-6 for x, y in zip(exact, base.USAGE[name])), name

    span = base.RUN_S - base.WARMUP_S
    return {
        "security_cpu_pct": 100 * sec_area / span / FOG_CPU,
        "fog_cpu_pct": 100 * total_area / span / FOG_CPU,
    }


# ---------------------------------------------------------------- plot
def plot(rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"RASP-Fog": "#2a78d6", "Static-Strong": "#eb6834", "Static-Light": "#1baf7a"}
    markers = {"RASP-Fog": "o", "Static-Strong": "s", "Static-Light": "^"}
    fig, ax = plt.subplots(figsize=(6.4, 4.0), dpi=200)
    for name in base.POLICIES:
        pts = [r for r in rows if r["policy"] == name]
        ax.errorbar([r["rate"] for r in pts], [r["security_cpu_pct"] for r in pts],
                    yerr=[r["security_cpu_pct_ci"] for r in pts], label=name,
                    color=colors[name], marker=markers[name], markersize=6,
                    linewidth=2, capsize=3)
    ax.set_xlabel("Arrival rate (requests/s)")
    ax.set_ylabel("Security CPU utilization of the fog (%)")
    ax.set_xticks(range(0, max(base.RATES) + 1, 50))
    ax.set_ylim(bottom=0)
    ax.grid(True, color="#e4e3df", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(path)


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    print(f"Security CPU test: threat fixed at {base.THREAT}, {base.RUN_S} s per run "
          f"({base.WARMUP_S} s warm-up), capacity x{base.CAPACITY_SCALE}, seeds {base.SEEDS}\n")
    rows = []
    for rate in base.RATES:
        for name in base.POLICIES:
            runs = [run_once(name, rate, s) for s in base.SEEDS]
            row = {"rate": rate, "policy": name}
            for key in runs[0]:
                row[key], row[key + "_ci"] = base.mean_ci([r[key] for r in runs])
            rows.append(row)

    for key, title in [("security_cpu_pct", "Security CPU utilization of the fog (% of fog CPU)"),
                       ("fog_cpu_pct", "Total CPU utilization of the fog (% of fog CPU)")]:
        print(title)
        print(f"  {'rate':>5}" + "".join(f"{n:>22}" for n in base.POLICIES))
        for rate in base.RATES:
            cells = []
            for n in base.POLICIES:
                r = next(x for x in rows if x["rate"] == rate and x["policy"] == n)
                cells.append(f"{r[key]:.2f} ± {r[key + '_ci']:.2f}")
            print(f"  {rate:>5}" + "".join(f"{c:>22}" for c in cells))
        print()

    with open(os.path.join(HERE, "security_cpu_results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("Results saved to security_cpu_results.csv")

    try:
        plot(rows, os.path.join(HERE, "fig3_security_cpu.png"))
        print("Figure saved to fig3_security_cpu.png")
    except ImportError:
        print("matplotlib not installed: figure skipped (pip install matplotlib)")
