# Efficiency test

Measures the resources each policy spends on security profiles, with 95 % confidence intervals.

```
python3 efficiency_testing/efficiency_test.py
```

## Setup

Same traffic, seeds, threat process and setup delay as `random_testing/random_test.py`, which it imports. Every second the test records the CPU, memory and bandwidth that active requests use for their security profile on top of their base demand. Intervals use the t-distribution over 5 seeds. RASP-Fog and Static-Strong are also compared seed by seed, since each seed gives both identical traffic.

## Output

Tables (mean ± 95 % CI) for secure share, security CPU, security share of used CPU, security CPU per secure request, security memory and security bandwidth, followed by the paired RASP-Fog minus Static-Strong comparison.

## Results: RASP-Fog minus Static-Strong, paired by seed

| Rate (req/s) | Secure requests (% points) | Security CPU (units) |
|---|---|---|
| 0.5 | +0.26 ± 0.72 | −1.65 ± 0.79 * |
| 1.0 | +0.11 ± 1.95 | −3.00 ± 0.63 * |
| 1.5 | +1.04 ± 2.94 | −3.61 ± 0.66 * |
| 2.0 | +1.47 ± 3.40 | −3.80 ± 0.48 * |
| 2.5 | +1.68 ± 2.08 | −3.96 ± 0.37 * |

\* the 95 % interval excludes zero.

- RASP-Fog spends about 30 % less CPU, 31 % less memory and 33 % less bandwidth on security than Static-Strong at every load.
- The difference in secure share is not significant at this sample size.
- Static-Strong always spends 16.7 % of its used CPU on security; RASP-Fog spends about 12 %.
- No-Hysteresis uses about 3 % less security CPU than RASP-Fog because it downgrades sooner.
