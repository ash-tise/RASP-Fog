"""
fillup_sim.py - a basic "fill-up" test of RASP-Fog, following the paper.

Run it with:   python3 fillup_sim.py
Needs only plain Python 3 (no extra packages, no randomness).

The test:
  * 3 fog nodes + 1 cloud (the cloud is just one more candidate node).
  * One request arrives every second, in a fixed order: sensor, camera, health, ...
  * Resources are RESERVED and NEVER FREED. The network slowly fills up,
    and we watch what RASP-Fog does as it runs out of room
    (good node -> other fog nodes -> cloud -> reject).
  * The threat level changes during the run, so active requests must be
    upgraded in place, moved, or terminated (Algorithm 2), and
    downgraded only after the lower level has held for TAU_H (hysteresis).
"""

# ---------------------------------------------------------------- settings
STEPS = 48          # seconds to simulate (one arrival per second)
TAU_H = 8           # hysteresis holding interval (s)
LAMBDA_D, LAMBDA_O = 0.5, 0.5   # cost weights in J

# Threat level theta(t) on the scale 1..3, as (start second, level).
THREAT_SCHEDULE = [(0, 1), (15, 3), (18, 1), (21, 3), (26, 1), (38, 3)]

# Nodes. cpu in normalized units, mem in MB, bw in Mbps,
# mu = processing rate (units per second), nu = communication delay (ms)
# from the ingress (where all requests enter) to that node.
NODES = {
    "Fog-1": {"cpu": 20, "mem": 16000, "bw": 20, "mu": 200, "nu": 2},
    "Fog-2": {"cpu": 10, "mem": 8000,  "bw": 10, "mu": 100, "nu": 10},
    "Fog-3": {"cpu": 20, "mem": 16000, "bw": 20, "mu": 200, "nu": 14},
    "Cloud": {"cpu": 40, "mem": 64000, "bw": 100, "mu": 200, "nu": 100},
}
QUEUE_MS = 20       # queueing delay chi = QUEUE_MS x CPU utilization of the node

# Security profiles q = 1..3. Overheads are % of the request's base demand.
PROFILES = {
    1: {"dc": 0.05, "dm": 0.05, "db": 0.00, "L": 1},
    2: {"dc": 0.10, "dm": 0.10, "db": 0.05, "L": 3},
    3: {"dc": 0.20, "dm": 0.20, "db": 0.10, "L": 5},
}
RHO_PER_LEVEL = 2   # profile-switch delay rho: 2 ms per level changed
PSI_MOVE = 20       # relocation delay psi when the node changes (ms)

# Request types: sensitivity sigma, deadline (ms), cpu c, memory m (MB), bandwidth b (Mbps)
TYPES = {
    "sensor": {"sigma": 1, "deadline": 300, "c": 1, "m": 256, "b": 1},
    "camera": {"sigma": 2, "deadline": 150, "c": 4, "m": 512, "b": 3},
    "health": {"sigma": 3, "deadline": 60,  "c": 2, "m": 256, "b": 1},
}
ARRIVAL_ORDER = ["sensor", "camera", "health"]


# ---------------------------------------------------------------- model
def threat(t):
    level = 1
    for start, lvl in THREAT_SCHEDULE:
        if t >= start:
            level = lvl
    return level


def required(sigma, theta):
    """Security policy phi = max(sigma, theta)."""
    return max(sigma, theta)


def demand(req, k):
    """Resources reserved by request req with profile k (base + overhead)."""
    p = PROFILES[k]
    return (req["c"] * (1 + p["dc"]), req["m"] * (1 + p["dm"]), req["b"] * (1 + p["db"]))


def used(node, active, skip=None):
    """CPU, memory, bandwidth reserved on node by active requests (except skip)."""
    c = m = b = 0.0
    for r in active:
        if r["node"] == node and r is not skip:
            dc, dm, db = demand(r, r["k"])
            c, m, b = c + dc, m + dm, b + db
    return c, m, b


def evaluate(req, node, k, active, prev_node=None, prev_k=None):
    """Return the candidate (node, k) with its delays, or None if resources don't fit."""
    n = NODES[node]
    uc, um, ub = used(node, active, skip=req)          # own reservation excluded
    av_c, av_m, av_b = n["cpu"] - uc, n["mem"] - um, n["bw"] - ub
    need_c, need_m, need_b = demand(req, k)
    if need_c > av_c or need_m > av_m or need_b > av_b:
        return None
    p = PROFILES[k]
    rho = RHO_PER_LEVEL * abs(k - prev_k) if prev_k else 0
    psi = PSI_MOVE if prev_node and node != prev_node else 0
    chi = QUEUE_MS * uc / n["cpu"]
    processing = chi + 1000 * req["c"] / n["mu"] + p["L"] + rho
    communication = n["nu"] + psi
    # normalized overhead o_ijk with weights 1/3 each
    o = (req["c"] * p["dc"] / av_c + req["m"] * p["dm"] / av_m + req["b"] * p["db"] / av_b) / 3
    return {"node": node, "k": k, "d": processing + communication,
            "proc": processing, "comm": communication, "o": o}


def choose(cands):
    """Min-max normalize d and o over the feasible set, then pick min J."""
    def norm(key):
        lo, hi = min(c[key] for c in cands), max(c[key] for c in cands)
        return {id(c): (c[key] - lo) / (hi - lo) if hi > lo else 0 for c in cands}
    nd, no = norm("d"), norm("o")
    for c in cands:
        c["J"] = LAMBDA_D * nd[id(c)] + LAMBDA_O * no[id(c)]
    # deterministic tie-break: node order, then weaker profile
    order = list(NODES)
    return min(cands, key=lambda c: (round(c["J"], 9), order.index(c["node"]), c["k"]))


def feasible(req, nodes, profiles, active, prev_node=None, prev_k=None):
    out = []
    for k in profiles:
        for node in nodes:
            c = evaluate(req, node, k, active, prev_node, prev_k)
            if c and c["d"] <= req["deadline"]:
                out.append(c)
    return out


# ---------------------------------------------------------------- Algorithm 1
def admit(req, t, active, log):
    q_req = required(req["sigma"], threat(t))
    cands = feasible(req, NODES, [k for k in PROFILES if k >= q_req], active)
    if not cands:
        log.append((t, "REJECT", req, f"needs q{q_req}, no node fits it on time"))
        return
    best = choose(cands)
    req.update(node=best["node"], k=best["k"], history=[(t, q_req)])
    active.append(req)
    log.append((t, "ADMIT", req, f"needs q{q_req} -> {best['node']} q{best['k']}  "
                f"delay {best['d']:.0f} ms (proc {best['proc']:.0f} + comm {best['comm']:.0f}) "
                f"/ deadline {req['deadline']}"))


# ---------------------------------------------------------------- Algorithm 2
def adapt(req, t, active, log, tau_h):
    q_req = required(req["sigma"], threat(t))
    req["history"].append((t, q_req))
    cur_node, cur_k = req["node"], req["k"]

    if cur_k < q_req:                       # mandatory upgrade
        stronger = [k for k in PROFILES if k >= q_req]
        cands = feasible(req, [cur_node], stronger, active, cur_node, cur_k)
        event = "UPGRADE"
        if not cands:                                    # current node can't: try others
            others = [n for n in NODES if n != cur_node]
            cands = feasible(req, others, stronger, active, cur_node, cur_k)
            event = "MOVE"
        if not cands:
            active.remove(req)
            log.append((t, "TERMINATE", req, f"needs q{q_req}, no node can give it on time"))
            return
        best = choose(cands)
        req.update(node=best["node"], k=best["k"])
        log.append((t, event, req, f"q{cur_k} -> q{best['k']} at {best['node']}"
                    f"  (delay {best['d']:.0f} ms)"))
        return

    # optional downgrade: same node only, and only if the weaker profile was enough
    # for the whole holding interval [t - TAU_H, t]
    peak = max(q for s, q in req["history"] if s >= t - tau_h)
    weaker = [k for k in PROFILES if q_req <= k < cur_k and k >= peak]
    cands = feasible(req, [cur_node], [cur_k] + weaker, active, cur_node, cur_k)
    if not cands:
        return
    best = choose(cands)
    if best["k"] != cur_k:
        req["k"] = best["k"]
        log.append((t, "DOWNGRADE", req, f"q{cur_k} -> q{best['k']} at {cur_node}"))


# ---------------------------------------------------------------- run
def run(tau_h):
    active, log, problems = [], [], []
    for t in range(STEPS):
        for req in list(active):                         # Algorithm 2 for active requests
            adapt(req, t, active, log, tau_h)
        kind = ARRIVAL_ORDER[t % len(ARRIVAL_ORDER)]     # one new arrival (Algorithm 1)
        admit({"id": t + 1, "kind": kind, **TYPES[kind]}, t, active, log)

        # checks that must hold at the end of every second
        for r in active:
            if r["k"] < required(r["sigma"], threat(t)):
                problems.append(f"t={t}: request {r['id']} under-protected")
        for node, n in NODES.items():
            c, m, b = used(node, active)
            if c > n["cpu"] + 1e-9 or m > n["mem"] + 1e-9 or b > n["bw"] + 1e-9:
                problems.append(f"t={t}: {node} over capacity")
    return active, log, problems


def print_report(active, log, problems):
    print("Event log (t = second, #id = request number)")
    last_theta = None
    for t, event, req, text in log:
        if threat(t) != last_theta:
            last_theta = threat(t)
            print(f"  ---- threat level is now {last_theta} ----")
        print(f"  t={t:2d} {event:<9} #{req['id']:<2} {req['kind']:<6} {text}")

    print("\nWhere the requests are at the end (reserved, never freed):")
    for node, n in NODES.items():
        c, m, b = used(node, active)
        count = sum(r["node"] == node for r in active)
        print(f"  {node:<6} {count:2d} requests   CPU {c:5.1f}/{n['cpu']:<3}  "
              f"mem {m:6.0f}/{n['mem']:<6}  bw {b:5.1f}/{n['bw']}")

    count = lambda e: sum(1 for x in log if x[1] == e)
    print("\nTotals: " + ", ".join(f"{e} {count(e)}" for e in
          ["ADMIT", "REJECT", "UPGRADE", "MOVE", "TERMINATE", "DOWNGRADE"]))

    first = lambda pred: next((x[0] for x in log if pred(x)), None)
    print(f"First request on the cloud: t={first(lambda x: x[1] == 'ADMIT' and 'Cloud' in x[3])}")
    print(f"First rejection (the 'failure' point): t={first(lambda x: x[1] == 'REJECT')}")

    _, log0, _ = run(0)
    changes = lambda lg: sum(1 for x in lg if x[1] in ("UPGRADE", "MOVE", "DOWNGRADE"))
    print(f"\nProfile changes with hysteresis (tau_H={TAU_H} s): {changes(log)}"
          f"   without (tau_H=0): {changes(log0)}")

    print("\nChecks:")
    checks = [
        ("Never under-protected", not any("under" in p for p in problems)),
        ("No node ever over capacity", not any("capacity" in p for p in problems)),
        ("Threat spike caused upgrades or moves",
         count("UPGRADE") + count("MOVE") > 0),
        ("Hysteresis reduced profile changes", changes(log) < changes(log0)),
    ]
    for text, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {text}")
    for p in problems[:5]:
        print("  problem:", p)


if __name__ == "__main__":
    print_report(*run(TAU_H))