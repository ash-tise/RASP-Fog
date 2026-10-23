# Security CPU test

Fog CPU spent on security overhead from 20 to 400 requests per second, at a fixed threat level, averaged over five seeds.

```
python3 07_security_cpu_testing/security_cpu_test.py
```

Writes `security_cpu_results.csv` and `fig3_security_cpu.png`. The figure needs `matplotlib`.

## Setup

Identical to the arrival-rate test in `06_arrival_rate_testing`: Poisson arrivals at 20–400 req/s, short tasks, node capacity × 10, threat fixed at θ = 2, 60 s runs with a 10 s warm-up, seeds 1–5, and the same three policies. The test imports its settings and traffic generator from `arrival_rate_test.py`, so both figures come from the same requests.

## Metrics

| Metric | Definition |
|---|---|
| Security CPU utilization | CPU reserved for security overhead on the fog nodes (c · Δc of the chosen profile, base demand excluded) ÷ total fog CPU, averaged over time after the warm-up |
| Total fog CPU utilization | CPU reserved on the fog nodes for base demand plus security ÷ total fog CPU, same averaging |

## Results (% of fog CPU, mean ± 95% CI)

| Rate (req/s) | RASP-Fog security | Static-Strong security | Static-Light security | RASP-Fog total | Static-Strong total |
|---|---|---|---|---|---|
| 20 | 1.22 ± 0.04 | 2.18 ± 0.08 | 0.54 ± 0.02 | 12.1 | 13.1 |
| 100 | 6.01 ± 0.16 | 10.70 ± 0.31 | 2.67 ± 0.08 | 59.5 | 64.2 |
| 150 | 8.92 ± 0.13 | 15.23 ± 0.16 | 4.02 ± 0.08 | 88.1 | 91.4 |
| 200 | 9.86 ± 0.04 | 16.10 ± 0.03 | 4.56 ± 0.02 | 96.1 | 96.6 |
| 300 | 10.34 ± 0.01 | 16.35 ± 0.01 | 4.67 ± 0.00 | 98.0 | 98.1 |
| 400 | 10.51 ± 0.04 | 16.43 ± 0.00 | 4.70 ± 0.00 | 98.6 | 98.6 |

The full table for all eleven rates is printed by the test and saved in the CSV.

- Below saturation, security CPU grows linearly with load for every policy. RASP-Fog uses about 44 % less than Static-Strong at every rate up to 100 req/s.
- The saving follows from profile selection. At θ = 2, sensor and camera requests need only q2 (10 % CPU overhead), so only health requests get q3 (20 %). Static-Strong applies q3 to every request.
- The fog is nearly full (above 96 % total CPU) from 200 req/s, so the curves flatten. At saturation, security takes 10.5 % of fog CPU under RASP-Fog against 16.4 % under Static-Strong. The extra 6 % is available for base demand, which is why RASP-Fog completes more requests securely in the arrival-rate test.
- Static-Light uses the least security CPU, but its q1 profile is below the required level of every request at θ = 2.
