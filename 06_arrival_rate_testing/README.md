# Arrival-rate test

Secure request completion from 20 to 400 requests per second, at a fixed threat level, averaged over five seeds.

```
python3 06_arrival_rate_testing/arrival_rate_test.py
```

Writes `arrival_rate_results.csv` and `fig1_secure_completion.png`. The figure needs `matplotlib`; without it the test still prints its tables and writes the CSV.

## Setup

| Setting | Value |
|---|---|
| Arrival rate | Poisson, 20 / 40 / 60 / 80 / 100 / 150 / 200 / 250 / 300 / 350 / 400 requests per second |
| Request type | uniform random |
| Holding time | exponential, mean 1.0 s (sensor), 1.5 s (camera), 0.5 s (health) |
| Node capacity | CPU, memory and bandwidth of every node × 10 (Fog-1 200 CPU units, Fog-2 100, Fog-3 200, Cloud 400) |
| Threat | fixed at θ = 2 |
| Run length | 60 s; requests arriving in the first 10 s are not counted |
| Seeds | 1–5; within a seed all policies see the same requests |
| Setup delay | 5 ms orchestrator round trip, added at admission |
| Policies | RASP-Fog, Static-Strong, Static-Light |

Requests are short tasks instead of the 10–30 s sessions of the earlier tests, and node capacity is scaled so the network saturates inside the tested range. All other model settings are unchanged from `rasp_core.py`.

With a fixed threat, a request's required profile never changes after admission, so Algorithm 2 never triggers. No-Hysteresis and No-Relocation then behave exactly like RASP-Fog and are not shown.

A request counts as a **secure completion** when it is admitted with at least its required profile, q_req = max(σ, θ). Shares are taken over all counted arrivals.

For speed, the test keeps a running total of the resources reserved on each node instead of summing all active requests at every check. The totals are compared with `rasp_core.used()` at the end of every run.

## Results: secure request completion (% of arrivals, mean ± 95% CI)

| Rate (req/s) | RASP-Fog | Static-Strong | Static-Light |
|---|---|---|---|
| 20–100 | 100.0 | 100.0 | 0.0 |
| 150 | 99.8 ± 0.1 | 99.4 ± 0.2 | 0.0 |
| 200 | 97.6 ± 0.3 | 96.8 ± 0.3 | 0.0 |
| 250 | 95.2 ± 0.6 | 94.1 ± 0.7 | 0.0 |
| 300 | 91.6 ± 0.6 | 88.4 ± 0.5 | 0.0 |
| 350 | 84.5 ± 0.8 | 81.3 ± 0.7 | 0.0 |
| 400 | 78.1 ± 0.8 | 75.4 ± 0.8 | 0.0 |

- Up to 100 req/s the fog has spare capacity and every RASP-Fog and Static-Strong request is admitted securely.
- From about 150 req/s the fog saturates and sensor and camera requests overflow to the cloud, which takes about 19 % of arrivals at 300 req/s. Health requests cannot use the cloud because its 100 ms network delay exceeds their 60 ms deadline, so they are the first to be rejected. From 300 req/s the busy cloud's queueing delay also pushes camera requests past their 150 ms deadline, and they start to be rejected too.
- RASP-Fog stays ahead of Static-Strong from 200 req/s, by about 3 points at 300–400 req/s, with non-overlapping confidence intervals. At θ = 2 it gives sensor and camera requests q2 (10 % overhead) instead of q3 (20 %), so each request reserves less and more requests fit before saturation.
- The gap is modest because the profile overheads are only 5–20 % of base demand. Heavier security overheads would widen it.
- Static-Light admits the most requests and has the lowest delay, but q1 is below the required profile of every request at θ = 2, so none of its requests is secure.
