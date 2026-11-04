"""
rasp_nsfnet.py - RASP-Fog on the 14-node, 21-link NSFNET topology.

Same algorithm as rasp_core.py (Algorithms 1 and 2), on a richer model:
  * 14 heterogeneous fog nodes connected by the 21 NSFNET links,
  * every request enters at its own ingress node s_i, and nu_ij is the
    shortest-path delay from s_i to node j (link delays 4-20 ms),
  * a request reserves bandwidth at the node interface and on every link of
    its path, so routes compete,
  * an elastic cloud behind two gateway nodes: unlimited CPU and memory, no
    queueing, reached over a 100 ms WAN uplink with limited bandwidth,
  * contention: the queueing delay chi grows as u / (1 - u) with the node's CPU
    utilization u, so delay rises steeply near saturation; a placement is only
    feasible if every request already on that node still meets its deadline,
  * heterogeneous requests: four classes with randomly varied demands, deadlines
    and session lengths,
  * a dynamic threat level per network region, so q_req changes during a
    session and forces upgrades that may not fit in place.

Usage:
    import random, rasp_nsfnet as nf
    nf.THREAT = nf.random_threat(random.Random(1), steps=200, p_up=0.2)  # or uniform_threat
    arrivals = nf.make_arrivals(random.Random(1), rate=20, duration=150)
    m = nf.simulate("RASP-Fog", arrivals, duration=150, warmup=30)
    print(m["secure_pct"], m["moves"], m["terminated"], m["sec_cpu_pct"])

Needs only plain Python 3.
"""
import heapq
import itertools

# ---------------------------------------------------------------- settings
TAU_H = 8           # hysteresis holding interval (s)
LAMBDA_D, LAMBDA_O = 0.5, 0.5   # cost weights in J
OMEGA = (1 / 3, 1 / 3, 1 / 3)   # overhead weights (cpu, mem, bw) in o_ijk

# NSFNET: 21 bidirectional links (node, node, length in km).
NSFNET_LINKS = [
    (1, 2, 2100), (1, 3, 3000), (1, 8, 4800), (2, 3, 1200), (2, 4, 1500),
    (3, 6, 3600), (4, 5, 1200), (4, 11, 3900), (5, 6, 2400), (5, 7, 1200),
    (6, 10, 2100), (6, 14, 3600), (7, 8, 1500), (8, 9, 1500), (9, 10, 1500),
    (9, 12, 600), (9, 13, 600), (11, 12, 1200), (11, 13, 1500), (12, 14, 600),
    (13, 14, 300),
]
FOG = list(range(1, 15))
LINK_DELAY_MS = (4, 20)         # link lengths are scaled linearly into this range
LINK_BW = 1000                  # Mbps per fog link

# Fog nodes alternate between two configurations: the parameter-table values
# (10/20 units, 8/16 GB, mu 100/200) scaled x10, with 1 Gbps-class interfaces.
SMALL = {"cpu": 100, "mem": 80000, "bw": 500, "mu": 100}
LARGE = {"cpu": 200, "mem": 160000, "bw": 1000, "mu": 200}

CLOUD = "Cloud"
CLOUD_GATEWAYS = [6, 9]         # the two degree-4 NSFNET nodes
WAN_DELAY_MS = 100              # gateway -> cloud
WAN_BW = 1000                   # Mbps per gateway uplink
CLOUD_MU = 200

PROTECT = True      # a placement may not push requests already on the node past their deadline
CHI_MS = 2          # queueing scale: chi = 2 ms at 50% CPU, 18 ms at 90%, 98 ms at 98%
MAX_UTIL = 0.99     # utilization in the queueing term is capped just below 1

# Security profiles q = 1..3. Overheads are % of the request's base demand.
PROFILES = {
    1: {"dc": 0.05, "dm": 0.05, "db": 0.00, "L": 1},
    2: {"dc": 0.10, "dm": 0.10, "db": 0.05, "L": 3},
    3: {"dc": 0.20, "dm": 0.20, "db": 0.10, "L": 5},
}
RHO_PER_LEVEL = 2   # profile-switch delay rho: 2 ms per level changed
PSI_MOVE = 20       # relocation delay psi when the node changes (ms)

# Request classes, from the parameter table: cpu c, memory m (MB), bandwidth b (Mbps),
# sensitivity sigma, deadline range (ms) and mean holding time (s).
# c, m and b of each request are drawn from [0.5, 1.5] x the class value.
TYPES = {
    "sensor":     {"sigma": 1, "c": 1, "m": 256,  "b": 5,  "deadline": (200, 500), "hold": 20},
    "health":     {"sigma": 3, "c": 2, "m": 512,  "b": 10, "deadline": (50, 100),  "hold": 10},
    "camera":     {"sigma": 2, "c": 4, "m": 512,  "b": 10, "deadline": (100, 250), "hold": 40},
    "industrial": {"sigma": 2, "c": 5, "m": 1024, "b": 10, "deadline": (80, 200),  "hold": 30},
}
SPREAD = 0.5

# Threat regions; a request's threat is the threat of its ingress region.
REGIONS = {"West": [1, 2, 3, 4], "Central": [5, 6, 7, 8, 10], "East": [9, 11, 12, 13, 14]}
REGION_OF = {j: r for r, nodes in REGIONS.items() for j in nodes}
THREAT = {r: [(0, 1)] for r in REGIONS}     # region -> [(start second, level)]

# Policies. No-Relocation upgrades in place or terminates; it never moves a request.
POLICIES = {
    "RASP-Fog":      {"profile": "adaptive", "relocate": True,  "tau_h": None},
    "No-Hysteresis": {"profile": "adaptive", "relocate": True,  "tau_h": 0},
    "No-Relocation": {"profile": "adaptive", "relocate": False, "tau_h": None},
    "Static-Strong": {"profile": 3},
    "Static-Light":  {"profile": 1},
}

INF = float("inf")


# ---------------------------------------------------------------- topology
def link_delay(km):
    lo_km = min(x[2] for x in NSFNET_LINKS)
    hi_km = max(x[2] for x in NSFNET_LINKS)
    lo, hi = LINK_DELAY_MS
    return lo + (km - lo_km) / (hi_km - lo_km) * (hi - lo)


def build_topology():
    """Fog nodes, links (as sorted node pairs) and the cloud's WAN links."""
    nodes = {}
    for j in FOG:
        nodes[j] = dict(LARGE if j % 2 else SMALL)       # odd nodes large, even small
    nodes[CLOUD] = {"cpu": INF, "mem": INF, "bw": INF, "mu": CLOUD_MU}
    links = {}
    for a, b, km in NSFNET_LINKS:
        links[(min(a, b), max(a, b))] = {"delay": link_delay(km), "bw": LINK_BW}
    for g in CLOUD_GATEWAYS:
        links[(g, CLOUD)] = {"delay": WAN_DELAY_MS, "bw": WAN_BW}
    return nodes, links


def link_key(a, b):
    if b == CLOUD:
        return (a, CLOUD)
    if a == CLOUD:
        return (b, CLOUD)
    return (min(a, b), max(a, b))


def shortest_paths(nodes, links):
    """Dijkstra by delay from every fog node. Returns {(s, j): (delay, [links])}."""
    adj = {n: [] for n in nodes}
    for (a, b), l in links.items():
        adj[a].append((b, l["delay"]))
        adj[b].append((a, l["delay"]))
    routes = {}
    for s in FOG:
        tie = itertools.count()                         # heap tie-breaker
        dist, prev, heap = {s: 0.0}, {}, [(0.0, next(tie), s)]
        while heap:
            d, _, u = heapq.heappop(heap)
            if d > dist[u] or u == CLOUD:               # the cloud is a leaf, never a transit
                continue
            for v, w in adj[u]:
                nd = d + w
                if nd < dist.get(v, INF) - 1e-12:
                    dist[v], prev[v] = nd, u
                    heapq.heappush(heap, (nd, next(tie), v))
        for j in nodes:
            path, v = [], j
            while v != s:
                path.append(link_key(prev[v], v))
                v = prev[v]
            routes[(s, j)] = (dist[j], path[::-1])
    return routes


# ---------------------------------------------------------------- network state
class Network:
    """Nodes, links, shortest-path routes and the resources reserved on each."""

    def __init__(self):
        self.nodes, self.links = build_topology()
        self.routes = shortest_paths(self.nodes, self.links)
        self.active, self.active_ids = [], set()
        self.node_used = {n: [0.0, 0.0, 0.0] for n in self.nodes}   # cpu, mem, bw
        self.link_used = {l: 0.0 for l in self.links}
        self.at = {n: {} for n in self.nodes}                       # node -> {id: req}
        self.room = {}              # node -> cached chi_room
        self.fog_cpu = 0.0          # CPU reserved on fog nodes
        self.fog_sec_cpu = 0.0      # the part of it spent on security overhead

    def reserve(self, req, sign=+1):
        """Add (sign=+1) or remove (sign=-1) req's reservation at its node and path."""
        dc, dm, db = demand(req, req["k"])
        u = self.node_used[req["node"]]
        u[0] += sign * dc
        u[1] += sign * dm
        u[2] += sign * db
        for l in self.routes[(req["ingress"], req["node"])][1]:
            self.link_used[l] += sign * db
        self.room.pop(req["node"], None)
        if sign > 0:
            self.at[req["node"]][req["id"]] = req
        else:
            self.at[req["node"]].pop(req["id"], None)
        if req["node"] != CLOUD:
            self.fog_cpu += sign * dc
            self.fog_sec_cpu += sign * (dc - req["c"])

    def place(self, req):
        self.active.append(req)
        self.active_ids.add(req["id"])
        self.reserve(req, +1)

    def release(self, req):
        self.active.remove(req)
        self.active_ids.discard(req["id"])
        self.reserve(req, -1)

    def available(self, req, node):
        """C, M, B available to req at node, its own reservation excluded, and the
        CPU reserved there by others. B is the tightest of the node interface and
        every link on the path."""
        uc, um, ub = self.node_used[node]
        path = self.routes[(req["ingress"], node)][1]
        link_use = {l: self.link_used[l] for l in path}
        if req["id"] in self.active_ids:                 # re-orchestration: skip own share
            dc, dm, db = demand(req, req["k"])
            if req["node"] == node:
                uc, um, ub = uc - dc, um - dm, ub - db
            for l in self.routes[(req["ingress"], req["node"])][1]:
                if l in link_use:
                    link_use[l] -= db
        n = self.nodes[node]
        av_b = n["bw"] - ub
        for l, used in link_use.items():
            av_b = min(av_b, self.links[l]["bw"] - used)
        return n["cpu"] - uc, n["mem"] - um, av_b, uc

    def chi_room(self, node):
        """Largest queueing delay the requests at node can absorb and still meet
        their deadlines."""
        if node not in self.room:
            self.room[node] = min((r["deadline"] - current_delay(r, self, chi=0)
                                   for r in self.at[node].values()), default=INF)
        return self.room[node]

    def utilization(self, node):
        if node == CLOUD:
            return 0.0
        return self.node_used[node][0] / self.nodes[node]["cpu"]

    def check(self):
        """Recompute every reservation from the active set and compare with the
        running totals and the capacities. Returns a list of problems."""
        problems = []
        node_used = {n: [0.0, 0.0, 0.0] for n in self.nodes}
        link_used = {l: 0.0 for l in self.links}
        for r in self.active:
            dc, dm, db = demand(r, r["k"])
            u = node_used[r["node"]]
            u[0], u[1], u[2] = u[0] + dc, u[1] + dm, u[2] + db
            for l in self.routes[(r["ingress"], r["node"])][1]:
                link_used[l] += db
        for n, cap in self.nodes.items():
            for i, key in enumerate(("cpu", "mem", "bw")):
                if abs(node_used[n][i] - self.node_used[n][i]) > 1e-6:
                    problems.append(f"node {n} {key}: running total out of sync")
                if node_used[n][i] > cap[key] + 1e-6:
                    problems.append(f"node {n} over {key} capacity")
        for l, cap in self.links.items():
            if abs(link_used[l] - self.link_used[l]) > 1e-6:
                problems.append(f"link {l}: running total out of sync")
            if link_used[l] > cap["bw"] + 1e-6:
                problems.append(f"link {l} over bandwidth capacity")
        return problems


# ---------------------------------------------------------------- requests and threat
def make_request(rng, rid, t, ingress=None, kind=None):
    """One heterogeneous request: random class, ingress, demands, deadline and holding time."""
    kind = kind or rng.choice(list(TYPES))
    cls = TYPES[kind]
    vary = lambda x: x * rng.uniform(1 - SPREAD, 1 + SPREAD)
    return {"id": rid, "kind": kind, "t": t,
            "ingress": ingress if ingress is not None else rng.choice(FOG),
            "sigma": cls["sigma"], "c": vary(cls["c"]), "m": vary(cls["m"]), "b": vary(cls["b"]),
            "deadline": rng.uniform(*cls["deadline"]),
            "end": t + rng.expovariate(1 / cls["hold"])}


def uniform_threat(schedule):
    """The same threat schedule [(start second, level), ...] in every region."""
    return {r: list(schedule) for r in REGIONS}


def random_threat(rng, steps, p_up, p_down=0.3, every=5, start=1):
    """Independent birth-death threat per region: every `every` s the level goes up
    one step with probability p_up, down with p_down, else stays (levels 1..3)."""
    out = {}
    for r in REGIONS:
        level, sched = start, [(0, start)]
        for t in range(every, steps, every):
            x = rng.random()
            if x < p_up and level < 3:
                level += 1
            elif x >= 1 - p_down and level > 1:
                level -= 1
            if level != sched[-1][1]:
                sched.append((t, level))
        out[r] = sched
    return out


def threat(t, ingress):
    level = 1
    for start, lvl in THREAT[REGION_OF[ingress]]:
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


# ---------------------------------------------------------------- delay
def processing_ms(c, mu, util):
    """Returns (queueing chi, processing c/mu) in ms. chi = CHI_MS * u / (1 - u) at
    the node's CPU utilization u: negligible at light load, steep near saturation."""
    util = min(util, MAX_UTIL)
    return CHI_MS * util / (1 - util), 1000 * c / mu


def evaluate(req, node, k, net, prev_node=None, prev_k=None):
    """Return the candidate (node, k) with its delays, or None if resources don't fit."""
    av_c, av_m, av_b, used_cpu = net.available(req, node)
    need_c, need_m, need_b = demand(req, k)
    if need_c > av_c or need_m > av_m or need_b > av_b:
        return None
    p = PROFILES[k]
    rho = RHO_PER_LEVEL * abs(k - prev_k) if prev_k else 0
    psi = PSI_MOVE if prev_node is not None and node != prev_node else 0
    nu = net.routes[(req["ingress"], node)][0]
    util = 0.0 if node == CLOUD else (used_cpu + need_c) / net.nodes[node]["cpu"]
    chi, base = processing_ms(req["c"], net.nodes[node]["mu"], util)
    if PROTECT and chi > net.chi_room(node) + 1e-9:    # would push co-located requests late
        return None
    processing = chi + base + p["L"] + rho
    communication = nu + psi
    wc, wm, wb = OMEGA
    o = (wc * req["c"] * p["dc"] / av_c + wm * req["m"] * p["dm"] / av_m
         + (wb * req["b"] * p["db"] / av_b if av_b > 0 else 0))
    return {"node": node, "k": k, "d": processing + communication,
            "proc": processing, "comm": communication, "nu": nu, "chi": chi, "o": o}


def current_delay(req, net, chi=None):
    """End-to-end delay of an active request at its node under the current load
    (no switching or relocation terms). chi overrides the queueing delay."""
    node = req["node"]
    q, base = processing_ms(req["c"], net.nodes[node]["mu"], net.utilization(node))
    return (net.routes[(req["ingress"], node)][0] + (q if chi is None else chi)
            + base + PROFILES[req["k"]]["L"])


def choose(cands):
    """Min-max normalize d and o over the feasible set, then pick min J."""
    def norm(key):
        lo, hi = min(c[key] for c in cands), max(c[key] for c in cands)
        return {id(c): (c[key] - lo) / (hi - lo) if hi > lo else 0 for c in cands}
    nd, no = norm("d"), norm("o")
    for c in cands:
        c["J"] = LAMBDA_D * nd[id(c)] + LAMBDA_O * no[id(c)]
    order = {n: i for i, n in enumerate(FOG + [CLOUD])}
    return min(cands, key=lambda c: (round(c["J"], 9), order[c["node"]], c["k"]))


def feasible(req, nodes, profiles, net, prev_node=None, prev_k=None):
    out = []
    for k in profiles:
        for node in nodes:
            c = evaluate(req, node, k, net, prev_node, prev_k)
            if c and c["d"] <= req["deadline"]:
                out.append(c)
    return out


# ---------------------------------------------------------------- Algorithm 1
def admit(req, t, net, log, policy):
    q_req = required(req["sigma"], threat(t, req["ingress"]))
    if policy["profile"] == "adaptive":
        profiles = [k for k in PROFILES if k >= q_req]
    else:
        profiles = [policy["profile"]]                   # static baselines
    cands = feasible(req, net.nodes, profiles, net)
    if not cands:
        log.append((t, "REJECT", req, f"needs q{q_req}, no node fits it on time"))
        return False
    best = choose(cands)
    req.update(node=best["node"], k=best["k"], history=[(t, q_req)], delay=best["d"])
    net.place(req)
    log.append((t, "ADMIT", req, f"in at N{req['ingress']}, needs q{q_req} -> "
                f"{name(best['node'])} q{best['k']}  delay {best['d']:.0f} ms "
                f"(nu {best['nu']:.0f}, queue {best['chi']:.0f}) / deadline {req['deadline']:.0f}"))
    return True


# ---------------------------------------------------------------- Algorithm 2
def adapt(req, t, net, log, policy):
    if policy["profile"] != "adaptive":                  # static baselines never change
        return
    tau_h = TAU_H if policy["tau_h"] is None else policy["tau_h"]
    q_req = required(req["sigma"], threat(t, req["ingress"]))
    req["history"].append((t, q_req))
    cur_node, cur_k = req["node"], req["k"]

    if cur_k < q_req:                                    # mandatory upgrade
        stronger = [k for k in PROFILES if k >= q_req]
        cands = feasible(req, [cur_node], stronger, net, cur_node, cur_k)
        event = "UPGRADE"
        if not cands and policy["relocate"]:             # current node can't: try others
            others = [n for n in net.nodes if n != cur_node]
            cands = feasible(req, others, stronger, net, cur_node, cur_k)
            event = "MOVE"
        if not cands:                                    # never kept under-protected
            net.release(req)
            log.append((t, "TERMINATE", req, f"needs q{q_req}, no feasible "
                        f"{'node' if policy['relocate'] else 'upgrade in place'}"))
            return
        best = choose(cands)
        net.reserve(req, -1)
        req.update(node=best["node"], k=best["k"], delay=best["d"])
        net.reserve(req, +1)
        log.append((t, event, req, f"q{cur_k} -> q{best['k']} at {name(best['node'])}"
                    f"  (delay {best['d']:.0f} ms)"))
        return

    # optional downgrade: same node only, and only if the weaker profile was enough
    # for the whole holding interval [t - tau_h, t]
    peak = max(q for s, q in req["history"] if s >= t - tau_h)
    weaker = [k for k in PROFILES if q_req <= k < cur_k and k >= peak]
    if not weaker:
        return
    cands = feasible(req, [cur_node], [cur_k] + weaker, net, cur_node, cur_k)
    if not cands:
        return
    best = choose(cands)
    if best["k"] != cur_k:
        net.reserve(req, -1)
        req.update(k=best["k"], delay=best["d"])
        net.reserve(req, +1)
        log.append((t, "DOWNGRADE", req, f"q{cur_k} -> q{best['k']} at {name(cur_node)}"))


# ---------------------------------------------------------------- simulation
DECISIONS = ("UPGRADE", "MOVE", "DOWNGRADE")


def make_arrivals(rng, rate, duration):
    """Poisson arrivals at `rate` req/s over [0, duration), as heterogeneous requests."""
    out, t = [], 0.0
    while True:
        t += rng.expovariate(rate)
        if t >= duration:
            return out
        out.append(make_request(rng, len(out) + 1, t))


def simulate(policy_name, arrivals, duration, warmup=0.0, epoch=1.0, check=False):
    """Event-driven run of one policy on a list of arrivals (not modified).

    Arrivals are admitted when they arrive, sessions release their resources when
    they end, and every `epoch` seconds Algorithm 2 re-evaluates every active
    request. After the last arrival the run continues until every session ends.
    A request misses its SLA at runtime if its end-to-end delay ever exceeds its
    deadline; that delay only grows when load is added to its node, so the
    requests on a node are re-checked whenever a request is placed there
    (with PROTECT on, placements are only made if this cannot happen).
    Metrics cover requests arriving in [warmup, duration); CPU is integrated over
    the same window. check=True also verifies capacities and running totals at
    every epoch and that every decision met its deadline when it was made."""
    policy = POLICIES[policy_name]
    net, log = Network(), []
    reqs = sorted((dict(a) for a in arrivals), key=lambda r: r["t"])
    departures, problems = [], []
    acc = {"cpu": 0.0, "sec": 0.0, "last": warmup, "late": 0, "peak_link": 0.0, "peak_wan": 0.0}

    def advance(now):                       # integrate fog CPU over [warmup, duration)
        a, b = acc["last"], min(now, duration)
        if b > a:
            acc["cpu"] += net.fog_cpu * (b - a)
            acc["sec"] += net.fog_sec_cpu * (b - a)
            acc["last"] = b

    def sla_check(node):
        if node == CLOUD:                   # no queueing in the cloud: delay never grows
            return
        for r in net.at[node].values():
            if current_delay(r, net) > r["deadline"] + 1e-9:
                r["sla_miss"] = True

    def protection_check(r, now):
        if r["k"] < required(r["sigma"], threat(now, r["ingress"])):
            r["under"] = True

    i, next_epoch = 0, 0.0
    while i < len(reqs) or departures:
        t_arr = reqs[i]["t"] if i < len(reqs) else INF
        t_dep = departures[0][0] if departures else INF
        now = min(t_arr, t_dep, next_epoch)
        advance(now)
        if t_dep == now:                                    # a session ends
            r = heapq.heappop(departures)[2]
            if r["id"] in net.active_ids:                   # not already terminated
                net.release(r)
        elif next_epoch == now:                             # decision epoch
            for r in list(net.active):                      # oldest first
                before = len(log)
                adapt(r, now, net, log, policy)
                if check:
                    acc["late"] += sum(1 for x in log[before:] if x[1] in DECISIONS
                                       and r["delay"] > r["deadline"] + 1e-9)
            for r in net.active:
                protection_check(r, now)
            for n in FOG:
                sla_check(n)
            for l, used in net.link_used.items():
                key = "peak_wan" if CLOUD in l else "peak_link"
                acc[key] = max(acc[key], used / net.links[l]["bw"])
            if check:
                problems += [f"t={now:.0f}: {p}" for p in net.check()]
            next_epoch += epoch
        else:                                               # an arrival
            r = reqs[i]
            i += 1
            if admit(r, now, net, log, policy):
                heapq.heappush(departures, (r["end"], r["id"], r))
                protection_check(r, now)
                sla_check(r["node"])
                if check and r["delay"] > r["deadline"] + 1e-9:
                    acc["late"] += 1

    measured = [r for r in reqs if r["t"] >= warmup]
    ids = {r["id"] for r in measured}
    events = [x for x in log if x[2]["id"] in ids]
    terminated = {x[2]["id"] for x in events if x[1] == "TERMINATE"}
    admitted = [r for r in measured if "node" in r]
    secure = [r for r in admitted if not r.get("under") and not r.get("sla_miss")
              and r["id"] not in terminated]
    n, span = max(1, len(measured)), max(1e-9, duration - warmup)
    fog_cap = sum(net.nodes[j]["cpu"] for j in FOG)
    moves = count(events, "MOVE")
    return {
        "arrivals": len(measured),
        "admitted": len(admitted),
        "rejected": count(events, "REJECT"),
        "secure": len(secure),
        "secure_pct": 100 * len(secure) / n,
        "sla_miss": sum(1 for r in admitted if r.get("sla_miss")),
        "sla_miss_pct": 100 * sum(1 for r in admitted if r.get("sla_miss")) / n,
        "under": sum(1 for r in admitted if r.get("under")),
        "terminated": len(terminated),
        "upgrades": count(events, "UPGRADE"),
        "moves": moves,
        "downgrades": count(events, "DOWNGRADE"),
        "changes": sum(1 for x in events if x[1] in DECISIONS),
        "relocation_ms": moves * PSI_MOVE,
        "cloud": sum(1 for r in admitted if r["node"] == CLOUD),
        "health_cloud": sum(1 for r in admitted if r["node"] == CLOUD and r["kind"] == "health"),
        "away": sum(1 for r in admitted if r["node"] != r["ingress"]),
        "mean_delay": sum(r["delay"] for r in admitted) / max(1, len(admitted)),
        "fog_util_pct": 100 * acc["cpu"] / (fog_cap * span),
        "sec_cpu_pct": 100 * acc["sec"] / (fog_cap * span),
        "peak_link_pct": 100 * acc["peak_link"],
        "peak_wan_pct": 100 * acc["peak_wan"],
        "late": acc["late"],
        "problems": problems,
        "log": log,
        "requests": reqs,
    }


# ---------------------------------------------------------------- helpers
def name(node):
    return node if node == CLOUD else f"N{node}"


def count(log, event):
    return sum(1 for x in log if x[1] == event)


def profile_changes(log):
    return sum(1 for x in log if x[1] in ("UPGRADE", "MOVE", "DOWNGRADE"))
