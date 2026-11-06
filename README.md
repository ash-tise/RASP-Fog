# RASP-Fog Simulation

A discrete-time simulation of RASP-Fog, a risk- and SLA-aware scheme that jointly selects the processing node and security profile for each IoT request in a fog–cloud network.

Requirements: Python 3. `matplotlib` is needed only to save figures.

## Repository layout

Two simulation models sit at the repository root, and each numbered folder holds one test script with its own README describing the setup, output and results.

### Models

| File | Description |
|---|---|
| `rasp_core.py` | Three fog nodes and a cloud: system model, Algorithms 1 and 2, policies |
| `rasp_nsfnet.py` | The same algorithms on the 14-node, 21-link NSFNET with an elastic cloud |

### Tests on `rasp_core.py`

| Folder | Script | Purpose |
|---|---|---|
| `01_fillup_testing` | `fillup_test.py` | Functional test of RASP-Fog, no resource release |
| `02_baseline_testing` | `baseline_test.py` | RASP-Fog vs the baselines on the fill-up scenario |
| `03_release_testing` | `release_test.py` | Fixed request durations, resources released on completion |
| `04_random_testing` | `random_test.py` | Random traffic at five load levels, five seeds |
| `05_efficiency_testing` | `efficiency_test.py` | Security resource use with 95% confidence intervals |
| `06_arrival_rate_testing` | `arrival_rate_test.py` | Secure completion at 20–400 req/s, fixed threat |
| `07_security_cpu_testing` | `security_cpu_test.py` | Fog security CPU at 20–400 req/s |
| `08_hysteresis_testing` | `hysteresis_test.py` | Profile changes vs the hysteresis interval τ_H |

### Tests on `rasp_nsfnet.py`

| Folder | Script | Purpose |
|---|---|---|
| `09_nsfnet_testing` | `nsfnet_test.py` | Topology, routing and capacity checks |
| `10_nsfnet_load_testing` | `nsfnet_load_test.py` | 8–40 req/s around saturation, dynamic regional threat |
| `11_attack_intensity_testing` | `attack_intensity_test.py` | Re-orchestration vs attack intensity, RASP-Fog vs No-Relocation |
| `12_protection_testing` | `protection_test.py` | Results with deadline protection on and off |

### Shared code

Tests may override a model's module-level settings before running (for example `core.STEPS = 120`). Some tests reuse code from an earlier one:

- `efficiency_test.py` and `hysteresis_test.py` use the traffic and threat generator in `04_random_testing/random_test.py`.
- `security_cpu_test.py` uses the settings and traffic generator in `06_arrival_rate_testing/arrival_rate_test.py`.
- `attack_intensity_test.py` and `protection_test.py` use the run and plotting helpers in `10_nsfnet_load_testing/nsfnet_load_test.py`.

## Usage

Run any test from the repository root:

```
python3 01_fillup_testing/fillup_test.py
python3 02_baseline_testing/baseline_test.py
python3 03_release_testing/release_test.py
python3 04_random_testing/random_test.py
python3 05_efficiency_testing/efficiency_test.py
python3 06_arrival_rate_testing/arrival_rate_test.py
python3 07_security_cpu_testing/security_cpu_test.py
python3 08_hysteresis_testing/hysteresis_test.py
python3 09_nsfnet_testing/nsfnet_test.py
python3 10_nsfnet_load_testing/nsfnet_load_test.py
python3 11_attack_intensity_testing/attack_intensity_test.py
python3 12_protection_testing/protection_test.py
```

Tests 01-05 and 09 run in a few seconds; tests 06-08 take up to 30 seconds each; tests 10-12 run their simulations in parallel and take 1-2 minutes each on 4 cores.

## Model

| Component | Setting |
|---|---|
| Nodes | Fog-1 (20 CPU units, 2 ms), Fog-2 (10, 10 ms), Fog-3 (20, 14 ms), Cloud (40, 100 ms). Every node also has memory and bandwidth limits. |
| Requests | Sensor (σ = 1, δ = 300 ms), camera (σ = 2, δ = 150 ms), health (σ = 3, δ = 60 ms). Each request is a session that holds its resources while active. |
| Security profiles | q1–q3: CPU and memory overhead 5/10/20 %, bandwidth overhead 0/5/10 %, security latency 1/3/5 ms |
| Required protection | q_req = max(σ, θ), threat level θ ∈ {1, 2, 3} |
| End-to-end delay | d = ν + χ + c/μ + L + ρ + ψ (network + queueing + processing + security + profile switch + relocation) |
| Queueing | χ = 20 ms × CPU utilization of the node |
| Cost | J = λ_D·d̃ + λ_O·õ, min–max normalized over feasible pairs, λ_D = λ_O = 0.5 |
| Hysteresis | τ_H = 8 s |

**Algorithm 1 (admission).** Each arriving request is evaluated against every (node, profile) pair. A pair is feasible when its profile meets q_req, it fits the node's free resources, and it meets the deadline. The feasible pair with the lowest J is selected; if none exists, the request is rejected.

**Algorithm 2 (runtime adaptation).** When q_req rises above a request's current profile, the request is upgraded on its current node if possible, otherwise relocated to another node or the cloud, and terminated as a last resort. A downgrade happens only on the current node, after the lower requirement has held for τ_H. When several requests need an upgrade at once, the oldest is handled first.

The orchestrator is logically centralized with a global view of node resources and threat state.

**NSFNET model (`rasp_nsfnet.py`, tests 09-12).** The same algorithms on the 14-node, 21-link NSFNET with random ingress nodes, shortest-path routing, per-link bandwidth reservation and an elastic cloud behind two gateways. Queueing grows as χ = 2 ms × u / (1 − u) with CPU utilization u, requests come from four heterogeneous classes with sessions of 10-40 s, each of three regions has its own dynamic threat level, and a placement is only feasible if every request already on the node still meets its deadline. See `09_nsfnet_testing/README.md`.

## Policies

| Policy | Type | Description |
|---|---|---|
| RASP-Fog | Proposed | Joint node–profile selection, relocation, hysteresis |
| No-Hysteresis | Ablation | RASP-Fog with τ_H = 0 |
| No-Relocation | Ablation | RASP-Fog without relocation; a request whose upgrade does not fit stays on its current profile (`rasp_core.py`) or is terminated (`rasp_nsfnet.py`) |
| Static-Strong | Baseline | Always q3, no runtime adaptation |
| Static-Light | Baseline | Always q1, no runtime adaptation |

## Summary of results

| Test | Main finding |
|---|---|
| Fill-up | Every branch of Algorithms 1 and 2 runs; no request is under-protected and no node exceeds capacity. |
| Baseline | RASP-Fog keeps 33 of 48 requests secure vs 31 for Static-Strong; without relocation only 15 stay secure. |
| Release | At moderate load Static-Strong matches RASP-Fog (120 vs 119 secure), since strong security is cheap here. |
| Random | RASP-Fog has the highest secure share from 1.5 req/s, 1–2 points above Static-Strong. |
| Efficiency | RASP-Fog spends about 30 % less CPU, memory and bandwidth on security than Static-Strong at every load (significant); the secure-share gap is not significant. |
| Arrival rate | At a fixed threat, the fog saturates from about 150 req/s; RASP-Fog completes about 3 points more requests securely than Static-Strong at 300-400 req/s (significant). |
| Security CPU | RASP-Fog uses about 44 % less fog CPU for security than Static-Strong below saturation, and 10.5 % vs 16.4 % of fog CPU at saturation. |
| Hysteresis | Raising τ_H from 0 to 8 s cuts profile changes by 31 % (61 % at 32 s) at the cost of 6 % (13 %) more security CPU; τ_H below the threat update interval has little effect. |
| NSFNET load | Saturation starts near 20 req/s; RASP-Fog completes 0.9-2.2 points more sessions securely than Static-Strong from 20 to 40 req/s (significant) with 30 % less security CPU, and drops about 60 % fewer sessions than No-Relocation. |
| Attack intensity | About 5 % of mandatory upgrades do not fit in place; RASP-Fog relocates 70-78 % of them, so No-Relocation has 2.6-3.6 times as many SLA violations (dropped sessions). Each relocation adds 35-42 ms to the moved session (20 ms migration plus a longer path). |
| Deadline protection | Without it, 11-19 % of sessions are pushed past their deadline near saturation, relocation rarely succeeds, and RASP-Fog's advantage disappears. |

## Key findings thus far

Significance is judged with paired 95% t-intervals over five seeds (tests 05-08 and 10-12): a difference is significant when its interval excludes zero.

1. **Same protection for less security cost.** RASP-Fog never leaves a request under-protected and spends about 30 % less on security than Static-Strong: CPU, memory and bandwidth in the three-node model (test 05) and 30-33 % of fog security CPU on NSFNET (test 10). Significant at every load in both models; this is the most robust result.
2. **Small, consistent completion gain near saturation.** RASP-Fog completes 0.9-2.2 points more sessions securely and on time than Static-Strong on NSFNET from 20 to 40 req/s (test 10), and about 3 points more at 300-400 req/s in the three-node model (test 06). Significant from saturation on; below saturation both complete nearly every session.
3. **Relocation keeps sessions alive during an attack.** About 5 % of mandatory upgrades do not fit on the current node. RASP-Fog relocates 70-78 % of them, so it has 55-70 % fewer SLA violations (sessions dropped mid-session) than No-Relocation (tests 10 and 11, significant at every attack intensity). The cost is small: at most about 15 relocations per 1000 sessions, each adding 35-42 ms to the moved session, and about 1 point more fog-link bandwidth. Its effect on overall secure completion is under 1 point and significant only at some loads.
4. **Hysteresis trades a little CPU for stability.** A holding interval of 8 s cuts profile changes by 31 ± 11 % at a cost of 6 % more security CPU; 32 s cuts them by 61 ± 5 % for 13 % more (test 08).
5. **Deadline protection matters more than any policy difference.** Without it, 11-19 % of sessions are pushed past their deadline near saturation, secure completion falls by 9-22 points for every policy, relocation rarely succeeds, and Static-Strong completes 2.1-2.6 points more than RASP-Fog at 24-32 req/s (test 12). Findings 2 and 3 hold only with protection on.
6. **Static-Light is cheap but insecure.** It completes only about 7 % of NSFNET sessions securely, since every health session and every session that sees a raised threat is under-protected.

The size of findings 1 and 2 depends on the assumed profile overheads (5/10/20 % CPU and memory); heavier overheads would widen the gaps but have not been tested.

## Limitations

The first two apply only to `rasp_core.py` (tests 01-08): the NSFNET model has 14 nodes, random ingress nodes and a threat level per region.

- Three fog nodes and a single ingress point, so each node has one fixed network delay.
- The threat level is the same for every request.
- Queueing is approximated rather than modeled as a real queue.
- Delay is checked at each decision, not per message within a session.
- Security overheads are light; a heavier-overhead scenario is planned.
