# RASP-Fog Simulation

A discrete-time simulation of RASP-Fog, a risk- and SLA-aware scheme that jointly selects the processing node and security profile for each IoT request in a fog–cloud network.

Requirements: Python 3. `matplotlib` is needed only to save figures.

## Repository layout

```
rasp_core.py                          system model, Algorithms 1 and 2, policies
01_fillup_testing/fillup_test.py         functional test of RASP-Fog (no resource release)
02_baseline_testing/baseline_test.py     RASP-Fog vs baselines on the fill-up scenario
03_release_testing/release_test.py       fixed request durations, resources released on completion
04_random_testing/random_test.py         random traffic at five load levels, five seeds
05_efficiency_testing/efficiency_test.py security resource use, with 95% confidence intervals
06_arrival_rate_testing/arrival_rate_test.py secure completion at 20-400 req/s, fixed threat
07_security_cpu_testing/security_cpu_test.py security CPU utilization of the fog at 20-400 req/s
08_hysteresis_testing/hysteresis_test.py profile changes vs hysteresis interval tau_H
```

Each test folder has its own README describing its setup, output and results. All tests import `rasp_core.py` and may override its module-level settings before running (for example `core.STEPS = 120`). `efficiency_test.py` also reuses the traffic generator in `04_random_testing/random_test.py`, `security_cpu_test.py` reuses the settings and traffic generator in `06_arrival_rate_testing/arrival_rate_test.py`, and `hysteresis_test.py` reuses the traffic and threat generator in `04_random_testing/random_test.py`.

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
```

Tests 01-05 run in a few seconds; tests 06-08 take up to 30 seconds each.

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

## Policies

| Policy | Type | Description |
|---|---|---|
| RASP-Fog | Proposed | Joint node–profile selection, relocation, hysteresis |
| No-Hysteresis | Ablation | RASP-Fog with τ_H = 0 |
| No-Relocation | Ablation | RASP-Fog without relocation; a request whose upgrade does not fit stays on its current profile |
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

## Limitations

- Three fog nodes and a single ingress point, so each node has one fixed network delay.
- The threat level is the same for every request.
- Queueing is approximated rather than modeled as a real queue.
- Delay is checked at each decision, not per message within a session.
- Security overheads are light; a heavier-overhead scenario is planned.
