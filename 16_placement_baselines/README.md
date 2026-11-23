# 16 — Placement baselines: latency-aware and load-aware

Does RASP-Fog's placement objective (min J) beat simpler placement rules once
the security adaptation is held fixed? Four methods, two capacity scenarios,
25 seeds, on `../rasp_nsfnet.py`.

```bash
python3 15_rate_figures/make_traces.py               # traces, if not already there
python3 16_placement_baselines/run_baselines.py      # 3,200 runs, ~25 min on 4 cores
python3 16_placement_baselines/plot_baselines.py     # redraw only
python3 tests/test_rasp_nsfnet.py                    # includes LA / LB / capacity tests
```

## Methods

All four share the same security adaptation: adaptive profile, local-first
mandatory upgrade, relocation if the upgrade does not fit, termination as a last
resort, downgrade after τ_H = 8 s. Only the node choice at admission and at
relocation differs.

| Method | Placement rule |
|---|---|
| RASP-Fog | min J = 0.5·d̃ + 0.5·õ over every feasible (node, profile) |
| SA-FF | first feasible node by hops from the ingress, then node ID, cloud last; min J among that node's profiles |
| LA (latency-aware) | min end-to-end delay d over every feasible (node, profile) |
| LB (load-aware) | fog node with the lowest projected CPU utilization after placement; cloud only if no fog node is feasible; min J among that node's profiles |

Feasibility (profile ≥ q_req, resources, deadline, incumbents still on time) is
the same for every method.

## Scenarios

| Scenario | Fog nodes | Cloud CPU | WAN uplinks | Knee |
|---|---|---|---|---|
| nominal | as in tests 13–15 | elastic | 1000 Mbps each | ~18 req/s |
| constrained | CPU, memory, interface bandwidth × 0.5 | 200 units (one large fog node) | 500 Mbps each | ~9 req/s |

The constrained settings were fixed before any result was seen. In a check run
the cloud CPU cap is reached from about 16 req/s on (peak 200 of 200 units) and
the WAN uplinks peak near 320 Mbps, so in that scenario the cloud CPU is the
binding cloud limit. In the nominal scenario the WAN uplinks saturate
(~1000 Mbps) in overload.

Same traces as `15_rate_figures` (25 seeds, identical request and threat trace
for every method, rate and scenario). The nominal RASP-Fog and SA-FF results
reproduce `15_rate_figures/rate_summary.csv` exactly (for example 93.69% and
93.55% secure completion at 24 req/s).

## Outputs

- `baselines_raw.csv`: one row per (scenario, method, rate, seed)
- `baselines_summary.csv`: mean and 95% t half-width (t = 2.064, 24 d.o.f.)
- `baselines_paired.csv`: RASP-Fog minus each baseline, paired by seed
- `base_<scenario>_secure`: (a) secure completion, (b) paired RASP-Fog gain
- `base_<scenario>_delay`: (a) mean end-to-end delay, (b) share placed in the cloud

## Results

Paired differences are RASP-Fog minus the baseline, ± 95% CI, in percentage
points (secure completion) or ms (delay). Below the knee every method completes
100% of sessions securely.

**Secure completion: RASP-Fog does not clearly beat any baseline.** The largest
gain anywhere is under 1 point.

| vs | Nominal (above the knee) | Constrained (above the knee) |
|---|---|---|
| SA-FF | −0.19 ± 0.06 at 19 req/s; +0.77 to +0.95 at 32–48 | −0.23 ± 0.07 at 9 req/s; +0.23 to +0.69 at 12–24 |
| LA | +0.26 to +0.89 at 22–48 | +0.31 to +0.53 at 11–20; +0.21 ± 0.28 (n.s.) at 24 |
| LB | +0.12 to +0.17 at 18–19; tied (inside the CI) at 20–28 and 48; +0.72 ± 0.20 at 32, +0.33 ± 0.23 at 40 | tied at 8–20; **LB ahead** at 24 req/s (−0.46 ± 0.25) |

**Delay.** LA is the fastest at every rate: RASP-Fog is 0.5–2.4 ms slower.
RASP-Fog is 0.4–4.2 ms faster than SA-FF below and around the knee, and tied
with it in overload in the nominal case (0.7–1.0 ms faster in the constrained
case). LB pays heavily for balancing: RASP-Fog is 14–20 ms faster at light load
and 1.4–4.7 ms faster in overload, in both scenarios.

**Cloud offloading.** All four methods send nearly the same share to the cloud
(within about 0.6 points at every rate). No method avoids or overuses the cloud
in a way that changes the outcome.

**Reading.** The placement rule moves secure completion by under 1 point in
both scenarios. RASP-Fog sits between LA (lower delay, slightly fewer secure
completions) and LB (about the same completions, much higher delay), so the
objective is a reasonable trade-off, but it is not a decisive placement win.
Constraining the fog and cloud does not widen the gap; against LB it narrows to
zero or reverses.
