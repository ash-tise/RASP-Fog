# Random test

Random traffic at five load levels, averaged over five seeds.

```
python3 04_random_testing/random_test.py
```

## Setup

| Setting | Value |
|---|---|
| Arrival rate | Poisson, 0.5 / 1.0 / 1.5 / 2.0 / 2.5 requests per second |
| Request type | uniform random |
| Duration | exponential, mean 20 s (sensor), 30 s (camera), 10 s (health) |
| Threat | updated every 10 s: up one level (p = 0.3), down one level (p = 0.3), or unchanged |
| Run length | 300 s |
| Seeds | 1–5; within a seed all policies see the same requests and threat changes |
| Setup delay | 5 ms orchestrator round trip, added at admission |

Averages are also written to `random_results.csv`.

## Results: secure requests (% of arrivals)

| Rate (req/s) | RASP-Fog | No-Hysteresis | No-Relocation | Static-Strong | Static-Light |
|---|---|---|---|---|---|
| 0.5 | 99.1 | 99.1 | 99.1 | 98.8 | 4.7 |
| 1.0 | 93.3 | 93.6 | 93.1 | 93.2 | 6.7 |
| 1.5 | 84.0 | 83.3 | 81.5 | 83.0 | 7.2 |
| 2.0 | 75.2 | 74.2 | 71.3 | 73.7 | 6.6 |
| 2.5 | 65.6 | 65.2 | 62.7 | 63.9 | 6.9 |

- RASP-Fog leads from 1.5 req/s by 1–2 points; the efficiency test shows this gap is not significant.
- No-Relocation leaves up to 2.8 % of requests under-protected.
- Hysteresis reduces profile changes per request by about 12–15 %.
- RASP-Fog is never under-protected and no node exceeds capacity in any of the 25 runs.
