"""
nsfnet_test.py - sanity test of RASP-Fog on the NSFNET topology.

Run it from the repository root:   python3 09_nsfnet_testing/nsfnet_test.py

Part 1 checks the topology and routing. Part 2 runs every policy on the same
random sessions near saturation under a scripted attack, and checks at every
decision epoch that node, link and WAN capacities hold and the running totals
are exact, that every decision met its deadline when it was made, that no
admitted request is pushed past its deadline by later load, and that the
adaptive policies never leave a request under-protected.
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import rasp_nsfnet as nf

# ---------------------------------------------------------------- test settings
SEED = 1
RATE = 24                   # arrivals per second (the fog is close to saturation here)
DURATION = 120              # seconds of arrivals; sessions then run to completion
# attack in every region at 40 s, a 4 s dip at 60 s (shorter than tau_H), calm at 90 s
SCHEDULE = [(0, 1), (40, 3), (60, 1), (64, 3), (90, 1)]
FOG = nf.FOG


# ---------------------------------------------------------------- part 1: topology
def floyd_warshall(net):
    d = {(a, b): (0 if a == b else nf.INF) for a in net.nodes for b in net.nodes}
    for (a, b), l in net.links.items():
        d[(a, b)] = d[(b, a)] = l["delay"]
    for m in FOG:                                         # the cloud is never a transit node
        for a in net.nodes:
            for b in net.nodes:
                if d[(a, m)] + d[(m, b)] < d[(a, b)]:
                    d[(a, b)] = d[(a, m)] + d[(m, b)]
    return d


def topology_checks(net):
    fog_links = [l for l in net.links if nf.CLOUD not in l]
    degree = {j: sum(j in l for l in fog_links) for j in FOG}
    fw = floyd_warshall(net)
    delays = [net.links[l]["delay"] for l in fog_links]

    print("Part 1: topology")
    print(f"  {'node':<5} {'config':<6} {'region':<8} {'cpu':>4} {'mem GB':>7} {'bw':>5} {'mu':>4} "
          f"{'degree':>7} {'farthest fog (ms)':>18} {'cloud (ms)':>11}")
    for j in FOG:
        n = net.nodes[j]
        far = max(net.routes[(j, x)][0] for x in FOG)
        print(f"  N{j:<4} {'large' if n == nf.LARGE else 'small':<6} {nf.REGION_OF[j]:<8} "
              f"{n['cpu']:>4} {n['mem'] // 1000:>7} {n['bw']:>5} {n['mu']:>4} {degree[j]:>7} "
              f"{far:>18.1f} {net.routes[(j, nf.CLOUD)][0]:>11.1f}")
    print(f"  links: {len(fog_links)} fog links, delay {min(delays):.1f}-{max(delays):.1f} ms, "
          f"{nf.LINK_BW} Mbps each; cloud gateways N{nf.CLOUD_GATEWAYS[0]} and "
          f"N{nf.CLOUD_GATEWAYS[1]}, {nf.WAN_DELAY_MS} ms, {nf.WAN_BW} Mbps each\n")

    return [
        ("14 fog nodes and 21 fog links", len(FOG) == 14 and len(fog_links) == 21),
        ("Every node reaches every other node and the cloud",
         all(net.routes[(a, b)][0] < nf.INF for a in FOG for b in net.nodes)),
        ("Link delays within 4-20 ms",
         all(4 - 1e-9 <= x <= 20 + 1e-9 for x in delays)),
        ("Shortest paths match Floyd-Warshall",
         all(abs(net.routes[(a, b)][0] - fw[(a, b)]) < 1e-9 for a in FOG for b in net.nodes)),
        ("Path delays are symmetric",
         all(abs(net.routes[(a, b)][0] - net.routes[(b, a)][0]) < 1e-9 for a in FOG for b in FOG)),
        ("Each path's delay equals the sum of its link delays",
         all(abs(net.routes[(a, b)][0] - sum(net.links[l]["delay"] for l in net.routes[(a, b)][1]))
             < 1e-9 for a in FOG for b in net.nodes)),
        ("Cloud reached only through a gateway, at >= 100 ms",
         all(net.routes[(a, nf.CLOUD)][1][-1][0] in nf.CLOUD_GATEWAYS
             and net.routes[(a, nf.CLOUD)][0] >= nf.WAN_DELAY_MS for a in FOG)),
        ("Every fog node belongs to exactly one threat region",
         sorted(j for nodes in nf.REGIONS.values() for j in nodes) == FOG),
    ]


# ---------------------------------------------------------------- main
if __name__ == "__main__":
    checks = topology_checks(nf.Network())

    print("  queueing delay chi by CPU utilization:  " + "  ".join(
        f"{u:.0%} {nf.processing_ms(1, 100, u)[0]:.0f} ms" for u in (0.5, 0.8, 0.9, 0.95, 0.98)))
    print()

    nf.THREAT = nf.uniform_threat(SCHEDULE)
    arrivals = nf.make_arrivals(random.Random(SEED), RATE, DURATION)
    kinds = {k: sum(1 for r in arrivals if r["kind"] == k) for k in nf.TYPES}
    print(f"Part 2: {len(arrivals)} sessions over {DURATION} s ({RATE} req/s, seed {SEED}), "
          f"random ingress; {kinds}")
    print(f"  threat in every region: {SCHEDULE}\n")
    results = {name: nf.simulate(name, arrivals, DURATION, check=True) for name in nf.POLICIES}

    rows = [("Admitted", "admitted"), ("Rejected", "rejected"),
            ("Secure and on time", "secure"), ("Ever under-protected", "under"),
            ("Pushed past deadline at runtime", "sla_miss"),
            ("Upgrades in place", "upgrades"), ("Relocations", "moves"),
            ("Terminated (dropped mid-session)", "terminated"), ("Downgrades", "downgrades"),
            ("Admitted to the cloud", "cloud"), ("Processed away from ingress", "away"),
            ("Mean delay at admission (ms)", "mean_delay"),
            ("Mean fog CPU utilization (%)", "fog_util_pct"),
            ("Fog CPU spent on security (%)", "sec_cpu_pct"),
            ("Peak fog-link utilization (%)", "peak_link_pct"),
            ("Peak WAN-uplink utilization (%)", "peak_wan_pct")]
    names = list(nf.POLICIES)
    print(f"  {'':<34}" + "".join(f"{n:>15}" for n in names))
    for label, key in rows:
        vals = [results[n][key] for n in names]
        fmt = "{:>15.1f}" if isinstance(vals[0], float) else "{:>15}"
        print(f"  {label:<34}" + "".join(fmt.format(v) for v in vals))

    rasp, norel = results["RASP-Fog"], results["No-Relocation"]
    print("\nRASP-Fog re-orchestration around the attack at t = 40 s (first 8 events):")
    for t, event, req, text in [x for x in rasp["log"] if x[0] == 40 and x[1] != "ADMIT"][:8]:
        print(f"  t={t:4.0f} {event:<9} #{req['id']:<5} {req['kind']:<10} {text}")

    checks += [
        ("No node, link or WAN uplink ever over capacity; running totals exact (all policies)",
         all(not r["problems"] for r in results.values())),
        ("Every admission and profile change met its deadline when made (all policies)",
         all(r["late"] == 0 for r in results.values())),
        ("No admitted request pushed past its deadline by later load (all policies)",
         all(r["sla_miss"] == 0 for r in results.values())),
        ("Adaptive policies never under-protect",
         all(results[n]["under"] == 0 for n in ("RASP-Fog", "No-Hysteresis", "No-Relocation"))),
        ("Static-Light under-protects during the attack", results["Static-Light"]["under"] > 0),
        ("No health request on the cloud (100 ms WAN >= 100 ms max deadline)",
         all(r["health_cloud"] == 0 for r in results.values())),
        ("Requests are processed away from their ingress node", rasp["away"] > 0),
        ("The attack caused relocations under RASP-Fog", rasp["moves"] > 0),
        ("No-Relocation drops more sessions than RASP-Fog", norel["terminated"] > rasp["terminated"]),
        ("Hysteresis cuts profile changes (RASP-Fog < No-Hysteresis)",
         rasp["changes"] < results["No-Hysteresis"]["changes"]),
        ("The cloud absorbs load when the fog is busy", rasp["cloud"] > 0),
    ]
    print("\nChecks:")
    for text, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {text}")
    for name in names:
        for p in results[name]["problems"][:3]:
            print(f"  problem ({name}): {p}")
