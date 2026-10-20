"""
baseline_test.py - RASP-Fog vs simpler policies on the same fill-up test.

Run it with:   python3 baseline_test.py

Every policy gets exactly the same requests and the same threat changes
(the fill-up test: one arrival per second, nothing is ever freed).
The algorithm and the policies live in ../rasp_core.py.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import rasp_core as core


def summarize(name, policy):
    active, log, problems = core.run(policy)
    admitted = [x[2] for x in log if x[1] == "ADMIT"]
    under_ids = {r["id"] for r in admitted if r.get("under")}
    terminated = {x[2]["id"] for x in log if x[1] == "TERMINATE"}
    secure = [r for r in active if r["id"] not in under_ids]
    return {
        "Policy": name,
        "Admit": len(admitted),
        "Reject": core.count(log, "REJECT"),
        "Term": len(terminated),
        "Under": len(under_ids),
        "Under-s": sum(1 for p in problems if "under" in p),
        "Secure": len(secure),
        "Changes": core.profile_changes(log),
        "Moves": core.count(log, "MOVE"),
        "Delay": sum(r["delay"] for r in admitted) / max(1, len(admitted)),
        "Cloud": sum(1 for r in admitted if r["node"] == "Cloud" and r["id"] not in terminated),
    }


if __name__ == "__main__":
    print(f"Fill-up test: {core.STEPS} requests (one per second), nothing freed, "
          f"threat changes {core.THREAT_SCHEDULE}\n")
    rows = [summarize(name, p) for name, p in core.POLICIES.items()]
    cols = ["Policy", "Admit", "Reject", "Term", "Under", "Under-s",
            "Secure", "Changes", "Moves", "Delay", "Cloud"]
    print(f"{cols[0]:<14}" + "".join(f"{c:>9}" for c in cols[1:]))
    print("-" * (14 + 9 * (len(cols) - 1)))
    for r in rows:
        print(f"{r['Policy']:<14}" + "".join(
            f"{r[c]:>9.1f}" if c == "Delay" else f"{r[c]:>9}" for c in cols[1:]))
    print("""
Admit    requests accepted            Reject  requests turned away
Term     terminated after an attack   Under   requests that were ever under-protected
Under-s  request-seconds spent under-protected
Secure   requests still running at the end that were never under-protected
Changes  profile changes (upgrades, moves, downgrades)    Moves  node changes
Delay    average delay at admission (ms)                  Cloud  requests admitted to the cloud""")