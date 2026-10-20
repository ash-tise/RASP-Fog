"""
release_test.py - RASP-Fog and the baselines with request completion.

Run it with:   python3 release_test.py

Same model and policies as ../rasp_core.py, with one difference: every
request has a fixed duration, and when it ends its CPU, memory and
bandwidth are released. Load now rises and falls instead of only filling up.
No randomness: arrivals are one per second in a fixed order.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import rasp_core as core

# ---------------------------------------------------------------- test settings
core.STEPS = 120
core.THREAT_SCHEDULE = [(0, 1), (30, 3), (50, 1), (53, 3), (70, 1), (100, 3)]
DURATION = {"sensor": 20, "camera": 30, "health": 10}   # seconds a request stays active


# ---------------------------------------------------------------- run with release
def run_with_release(policy):
    """core.run plus one step: requests whose time is up leave and free their resources."""
    active, log, problems, timeline = [], [], [], []
    for t in range(core.STEPS):
        for req in [r for r in active if r["end"] <= t]:  # completion: release resources
            active.remove(req)
            log.append((t, "COMPLETE", req, f"finished at {req['node']}"))
        for req in list(active):                           # Algorithm 2 for active requests
            core.adapt(req, t, active, log, policy)
        kind = core.ARRIVAL_ORDER[t % len(core.ARRIVAL_ORDER)]
        req = {"id": t + 1, "kind": kind, "end": t + DURATION[kind], **core.TYPES[kind]}
        core.admit(req, t, active, log, policy)            # Algorithm 1 for the new arrival

        for r in active:
            if r["k"] < core.required(r["sigma"], core.threat(t)):
                r["under"] = True
                problems.append(f"t={t}: request {r['id']} under-protected")
        for node, n in core.NODES.items():
            c, m, b = core.used(node, active)
            if c > n["cpu"] + 1e-9 or m > n["mem"] + 1e-9 or b > n["bw"] + 1e-9:
                problems.append(f"t={t}: {node} over capacity")
        timeline.append((t, {node: core.used(node, active)[0] for node in core.NODES}))
    return active, log, problems, timeline


def summarize(name, policy):
    active, log, problems, timeline = run_with_release(policy)
    admitted = [x[2] for x in log if x[1] == "ADMIT"]
    terminated = {x[2]["id"] for x in log if x[1] == "TERMINATE"}
    under = {r["id"] for r in admitted if r.get("under")}
    return {
        "Policy": name,
        "Admit": len(admitted),
        "Reject": core.count(log, "REJECT"),
        "Done": core.count(log, "COMPLETE"),
        "Term": len(terminated),
        "Under": len(under),
        "Under-s": sum(1 for p in problems if "under" in p),
        "Secure": sum(1 for r in admitted if r["id"] not in terminated | under),
        "Changes": core.profile_changes(log),
        "Moves": core.count(log, "MOVE"),
        "Delay": sum(r["delay"] for r in admitted) / max(1, len(admitted)),
        "Cloud": sum(1 for r in admitted if r["node"] == "Cloud"),
    }, log, problems, timeline


def print_timeline(timeline):
    print("CPU in use every 10 s (RASP-Fog). Capacity: "
          + ", ".join(f"{n} {v['cpu']}" for n, v in core.NODES.items()))
    print(f"  {'t':>3} {'threat':>6}" + "".join(f"{n:>8}" for n in core.NODES))
    for t, cpu in timeline[::10]:
        print(f"  {t:>3} {core.threat(t):>6}" + "".join(f"{cpu[n]:>8.1f}" for n in core.NODES))


if __name__ == "__main__":
    print(f"Release test: {core.STEPS} requests (one per second), durations {DURATION} s,\n"
          f"threat changes {core.THREAT_SCHEDULE}\n")

    results = {name: summarize(name, p) for name, p in core.POLICIES.items()}
    print_timeline(results["RASP-Fog"][3])

    cols = ["Policy", "Admit", "Reject", "Done", "Term", "Under", "Under-s",
            "Secure", "Changes", "Moves", "Delay", "Cloud"]
    print(f"\n{cols[0]:<14}" + "".join(f"{c:>8}" for c in cols[1:]))
    print("-" * (14 + 8 * (len(cols) - 1)))
    for row, *_ in results.values():
        print(f"{row['Policy']:<14}" + "".join(
            f"{row[c]:>8.1f}" if c == "Delay" else f"{row[c]:>8}" for c in cols[1:]))
    print("""
Done     requests that finished and released their resources
Secure   admitted, never under-protected and never terminated
(other columns as in the baseline comparison)""")

    row, log, problems, _ = results["RASP-Fog"]
    print("\nRASP-Fog checks:")
    checks = [
        ("Never under-protected", row["Under"] == 0),
        ("No node ever over capacity", not any("capacity" in p for p in problems)),
        ("Finished requests released their resources", row["Done"] > 0),
        ("Freed capacity was reused (fog admissions after the first completion)",
         any(x[1] == "ADMIT" and "Cloud" not in x[3] and
             x[0] > next(y[0] for y in log if y[1] == "COMPLETE") for x in log)),
    ]
    for text, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {text}")