# RASP-Fog Simulation

A discrete-time simulation of RASP-Fog, a Risk- and SLA-aware scheme that jointly selects the processing node and security profile for each IoT request in a fog–cloud network.

Requirements: Python 3

## Repository layout

```
rasp_core.py                         system model
fillup_testing/fillup_test.py        functional test of RASP-Fog
baseline_comparison/baseline_test.py RASP-Fog compared with baseline policies
```

All tests import `rasp_core.py`. A test may override any module-level setting before running, for example `core.STEPS = 60`.

## Usage

```
python3 fillup_testing/fillup_test.py
python3 baseline_comparison/baseline_test.py
```

## Model

| Component | Setting |
|---|---|
| Nodes | Three fog nodes (Fog-1: 20 CPU units, 2 ms; Fog-2: 10, 10 ms; Fog-3: 20, 14 ms) and one cloud node (40 units, 100 ms). Every node also has memory and bandwidth limits. |
| Requests | Sensor (σ = 1, δ = 300 ms), camera (σ = 2, δ = 150 ms), health (σ = 3, δ = 60 ms) |
| Security profiles | q1–q3. CPU and memory overhead of 5/10/20 %, bandwidth overhead of 0/5/10 %, and security latency of 1/3/5 ms. |
| Required protection | q_req = max(σ, θ), with threat level θ ∈ {1, 2, 3} |
| End-to-end delay | d = ν + χ + c/μ + L + ρ + ψ (communication + queueing + processing + security + profile switch + relocation) |
| Cost | J = λ_D·d̃ + λ_O·õ with min–max normalization and λ_D = λ_O = 0.5 |
| Hysteresis | τ_H = 8 s |

**Algorithm 1 (admission).** Each arriving request is evaluated against every (node, profile) pair. A pair is feasible when its profile meets q_req, it fits the node's resources, and it meets the deadline. The feasible pair with the lowest J is selected. If no pair is feasible, the request is rejected.

**Algorithm 2 (runtime adaptation).** When q_req rises above a request's current profile, RASP-Fog upgrades the request on its current node if possible. Otherwise it relocates the request to another node or the cloud, and terminates it as a last resort. A downgrade happens only on the current node, and only after the lower requirement has held for τ_H.

## Fill-up test

Each run lasts 48 s. One request arrives per second in a fixed order (sensor, camera, health), and reserved resources are never released, so load increases throughout. The threat level rises at t = 15, 21 and 38. A 3 s calm period at t = 18 tests hysteresis.

The test verifies four properties:
1. No request is ever under-protected.
2. No node exceeds its capacity.
3. A threat increase triggers upgrades or relocations.
4. Hysteresis reduces the number of profile changes.

## Baseline comparison

| Policy | Description |
|---|---|
| RASP-Fog | Joint node–profile selection, relocation, and hysteresis |
| No-Hysteresis | RASP-Fog with τ_H = 0 |
| No-Relocation | RASP-Fog without relocation. A request whose upgrade does not fit stays on its current profile. |
| Static-Strong | Always q3, no runtime adaptation |
| Static-Light | Always q1, no runtime adaptation |

Results for 48 requests:

| Policy | Admitted | Rejected | Terminated | Under-protected | Under-protected (s) | Secure | Profile changes | Relocations | Mean delay (ms) |
|---|---|---|---|---|---|---|---|---|---|
| RASP-Fog | 35 | 13 | 2 | 0 | 0 | 33 | 54 | 1 | 67.2 |
| No-Hysteresis | 37 | 11 | 3 | 0 | 0 | 34 | 75 | 2 | 63.6 |
| No-Relocation | 33 | 15 | 0 | 18 | 196 | 15 | 34 | 0 | 67.5 |
| Static-Strong | 31 | 17 | 0 | 0 | 0 | 31 | 0 | 0 | 70.8 |
| Static-Light | 36 | 12 | 0 | 36 | 849 | 0 | 0 | 0 | 67.0 |

- *Under-protected* counts requests that were ever below q_req.
- *Under-protected (s)* is the total time those requests spent below q_req.
- *Secure* counts requests still active at the end that were never under-protected.

**Observations**
- Static-Light admits a similar number of requests, but all of them are under-protected during the attack periods.
- Static-Strong is always secure but admits fewer requests than RASP-Fog (31 vs 35), because it uses the strongest profile even when the threat is low.
- Without relocation, 18 requests are left under-protected, and only 15 are secure at the end.
- Hysteresis cuts profile changes by 28 % (75 to 54), at the cost of one secure request compared with No-Hysteresis.

## Limitations

- All requests enter at a single ingress point, so each node has a single fixed communication delay.
- The threat level is the same for every request.
- Queueing delay is approximated as χ = 20 ms × CPU utilization.
- Results come from one fixed scenario without resource release. Further work covers request completion and varying load.
