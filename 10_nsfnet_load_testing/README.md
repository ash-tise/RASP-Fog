# NSFNET load test

Secure completion, rejections, dropped sessions and security CPU on NSFNET as the arrival rate approaches and passes saturation, under a dynamic regional threat.

```
python3 10_nsfnet_load_testing/nsfnet_load_test.py
```

Runs the 260 simulations in parallel, about 1.5 min on 4 cores. Figures need matplotlib.

## Setup

| Setting | Value |
|---|---|
| Model | `rasp_nsfnet.py` (see `09_nsfnet_testing`), deadline protection on |
| Arrival rates | 8, 12, 16, 18, 20, 22, 24, 26, 28, 30, 32, 36, 40 req/s |
| Run | 150 s of Poisson arrivals, first 30 s not counted, sessions run to completion |
| Threat | independent per region, every 5 s up one level with p = 0.2, down with p = 0.3 |
| Seeds | 1–5; mean with 95% t-interval |
| Policies | RASP-Fog, No-Relocation, Static-Strong, Static-Light |

For each seed the threat trace is the same at every rate, and within a run every policy sees the same sessions. A session counts as secure and on time if it is admitted, never under-protected, never pushed past its deadline, and not dropped.

## Results

| Rate (req/s) | RASP-Fog | No-Relocation | Static-Strong | Rejected, RASP-Fog | Dropped, RASP-Fog / No-Relocation | Security CPU, RASP-Fog / Static-Strong | Fog CPU, RASP-Fog |
|---|---|---|---|---|---|---|---|
| 16 | 100.0 | 99.98 | 100.0 | 0.0 | 0.00 / 0.02 | 7.9 / 11.8 | 67.0 |
| 20 | 99.1 | 98.9 | 98.3 | 0.7 | 0.18 / 0.47 | 9.7 / 14.2 | 82.2 |
| 24 | 95.4 | 95.0 | 93.9 | 4.2 | 0.43 / 1.21 | 10.5 / 15.1 | 89.3 |
| 28 | 92.0 | 91.6 | 90.3 | 7.6 | 0.44 / 1.10 | 10.7 / 15.3 | 91.5 |
| 32 | 88.8 | 88.1 | 87.4 | 10.7 | 0.43 / 1.21 | 10.8 / 15.4 | 92.2 |
| 40 | 83.7 | 83.5 | 81.8 | 15.8 | 0.56 / 1.23 | 10.9 / 15.4 | 92.4 |

All values in %. Static-Light completes about 7% of sessions securely at every rate, because it under-protects every health session and every session that sees a raised threat.

- Saturation starts near 20 req/s. Past it, fog CPU levels off at about 92% and rejections absorb the extra load.
- Security CPU follows the load and then flattens once the fog is full. RASP-Fog spends 30–33% less fog CPU on security than Static-Strong at every rate.
- RASP-Fog completes more sessions securely than Static-Strong from 20 req/s on. The paired difference is +0.9 to +2.2 points, and its 95% interval excludes zero at every rate from 20 to 40.
- Against No-Relocation the paired difference is +0.2 to +1.0 points, and its 95% interval excludes zero at 20, 26, 28, 30 and 32 req/s. RASP-Fog drops 55–65% fewer sessions mid-session.

## Output

`load_results.csv` (mean and 95% CI of every metric per policy and rate, including SLA violations, relocation overhead and fog-link and WAN utilization), `fig_nsfnet_secure_completion.png`, `fig_nsfnet_security_cpu.png`.
