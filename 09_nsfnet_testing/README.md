# NSFNET test

Sanity test of RASP-Fog on the 14-node, 21-link NSFNET topology, implemented in `rasp_nsfnet.py` at the repository root.

```
python3 09_nsfnet_testing/nsfnet_test.py
```

Runs in about 5 s with plain Python 3.

## Network model (`rasp_nsfnet.py`)

| Component | Setting |
|---|---|
| Fog layer | NSFNET: 14 nodes (N1–N14), 21 bidirectional links |
| Link delay | NSFNET link lengths (300–4800 km) scaled linearly into 4–20 ms |
| Link bandwidth | 1000 Mbps per fog link |
| Fog nodes | odd nodes large (200 CPU units, 160 GB, 1000 Mbps interface, μ = 200), even nodes small (100, 80 GB, 500 Mbps, μ = 100) |
| Ingress | each request enters at its own fog node s_i, chosen uniformly |
| Routing | shortest path by delay; ν_ij is the delay of the path from s_i to node j |
| Cloud | elastic: unlimited CPU and memory, no queueing, μ = 200; reached through gateways N6 and N9 over a 100 ms, 1000 Mbps WAN uplink each |
| Queueing | χ = 2 ms × u / (1 − u), with u the node's CPU utilization after placement (2 ms at 50%, 18 ms at 90%, 98 ms at 98%) |
| Deadline protection | a placement is feasible only if every request already on the node still meets its deadline at the new utilization |
| Threat | one level per region (West N1–N4, Central N5–N8 and N10, East N9 and N11–N14); a scripted schedule or a random birth-death process updated every 5 s |
| Decision epochs | Algorithm 2 re-evaluates every active request once per second |

A request reserves CPU and memory at its processing node, and bandwidth at the node interface and on every link of its path, including the WAN uplink when it runs in the cloud. The bandwidth available to a candidate is the smallest of the node interface and every link on the path. During re-orchestration a request's own reservation is excluded before candidates are evaluated. Profiles, the cost J and Algorithms 1 and 2 are the same as in `rasp_core.py`. When a mandatory upgrade does not fit, policies that can relocate (RASP-Fog, RASP-Reloc, SA-FF, No-Hysteresis) move the request, and the others (RASP-Profile, No-Relocation) terminate it; no adaptive policy leaves a request under-protected. SA-FF places by first fit (fewest hops from the ingress, then node ID, cloud last) instead of minimum J. See `POLICIES` in `rasp_nsfnet.py`.

### Request classes

Each request's CPU, memory and bandwidth are drawn from 0.5–1.5 × the class value, its deadline uniformly from the class range, and its session length from an exponential distribution.

| Class | σ | CPU | Memory (MB) | Bandwidth (Mbps) | Deadline (ms) | Mean session (s) |
|---|---|---|---|---|---|---|
| Sensor | 1 | 1 | 256 | 5 | 200–500 | 20 |
| Health | 3 | 2 | 512 | 10 | 50–100 | 10 |
| Camera | 2 | 4 | 512 | 10 | 100–250 | 40 |
| Industrial | 2 | 5 | 1024 | 10 | 80–200 | 30 |

## Test

**Part 1** checks the topology: 14 nodes and 21 links, full connectivity, link delays within 4–20 ms, shortest paths equal to Floyd–Warshall, symmetric path delays, path delays equal to the sum of their links, cloud access only through a gateway, and every node in exactly one threat region.

**Part 2** runs every policy in `POLICIES` (eight) on the same 2826 sessions: Poisson arrivals at 24 req/s for 120 s, close to saturation, with uniform class and ingress node. The threat in every region rises to 3 at 40 s, dips for 4 s at 60 s (shorter than τ_H), and returns to 1 at 90 s. The run continues until every session ends. At every epoch the test recomputes all reservations from the active requests and compares them with the running totals and the node, link and WAN capacities.

## Results

| | RASP-Fog | RASP-Reloc | RASP-Profile | SA-FF | Static-Strong | No-Hysteresis | No-Relocation | Static-Light |
|---|---|---|---|---|---|---|---|---|
| Admitted | 2766 | 2762 | 2762 | 2757 | 2739 | 2762 | 2766 | 2802 |
| Rejected | 60 | 64 | 64 | 69 | 87 | 64 | 60 | 24 |
| Secure and on time | 2763 | 2755 | 2745 | 2755 | 2739 | 2755 | 2759 | 313 |
| Ever under-protected | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2489 |
| Pushed past deadline at runtime | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Upgrades in place | 446 | 774 | 792 | 427 | 0 | 774 | 448 | 0 |
| Relocations | 6 | 27 | 0 | 24 | 0 | 27 | 0 | 0 |
| Terminated mid-session | 3 | 7 | 17 | 2 | 0 | 7 | 7 | 0 |
| Downgrades | 342 | 868 | 867 | 338 | 0 | 868 | 342 | 0 |
| Admitted to the cloud | 37 | 32 | 25 | 39 | 44 | 32 | 35 | 7 |
| Processed away from ingress | 1620 | 1580 | 1548 | 960 | 1743 | 1580 | 1606 | 1612 |
| Mean delay at admission (ms) | 44.6 | 44.2 | 43.7 | 46.1 | 47.9 | 44.2 | 45.4 | 37.7 |
| Mean fog CPU utilization (%) | 75.8 | 75.3 | 75.3 | 76.0 | 78.3 | 75.3 | 76.1 | 73.4 |
| Fog CPU spent on security (%) | 10.3 | 9.6 | 9.6 | 10.3 | 13.0 | 9.6 | 10.3 | 3.5 |
| Peak fog-link utilization (%) | 71.6 | 64.4 | 57.6 | 45.0 | 60.4 | 64.4 | 65.6 | 51.8 |
| Peak WAN-uplink utilization (%) | 23.6 | 18.7 | 15.1 | 24.4 | 26.1 | 18.7 | 23.1 | 4.6 |

RASP-Reloc and No-Hysteresis share the same switches and give identical results. All 19 checks pass: no node, link or WAN uplink exceeds capacity, every admission and profile change meets its deadline when made, no admitted request is pushed past its deadline by later load, the adaptive policies never under-protect, no health request reaches the cloud, the attack triggers relocations, No-Relocation drops more sessions than RASP-Fog, and hysteresis reduces profile changes.

This is a correctness test, not an evaluation. Arrival-rate and attack-intensity sweeps follow in later folders. Unit tests for individual decisions (reservation and release, projected-utilization queueing, deadline protection, local-first upgrade, relocation, RASP-Profile termination, SA-FF order, hysteresis) are in `tests/test_rasp_nsfnet.py`.
