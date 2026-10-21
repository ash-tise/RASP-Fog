# Baseline comparison

Runs all five policies on the fill-up scenario (48 requests, no resource release, same threat schedule).

```
python3 baseline_testing/baseline_test.py
```

## Metrics

| Column | Meaning |
|---|---|
| Admit / Reject | requests accepted / turned away |
| Term | requests terminated during an upgrade |
| Under | requests ever below q_req |
| Under-s | request-seconds spent below q_req |
| Secure | requests active at the end that were never under-protected |
| Changes | upgrades, relocations and downgrades |
| Delay | mean delay at admission (ms) |

## Results

| Policy | Admitted | Rejected | Terminated | Under | Under-s | Secure | Changes | Relocations |
|---|---|---|---|---|---|---|---|---|
| RASP-Fog | 35 | 13 | 2 | 0 | 0 | 33 | 54 | 1 |
| No-Hysteresis | 37 | 11 | 3 | 0 | 0 | 34 | 75 | 2 |
| No-Relocation | 33 | 15 | 0 | 18 | 196 | 15 | 34 | 0 |
| Static-Strong | 31 | 17 | 0 | 0 | 0 | 31 | 0 | 0 |
| Static-Light | 36 | 12 | 0 | 36 | 849 | 0 | 0 | 0 |

- Static-Light under-protects every request it admits during the attacks.
- Static-Strong admits 4 fewer requests than RASP-Fog because it uses q3 even at low threat.
- Without relocation, 18 requests stay under-protected.
- Hysteresis cuts profile changes by 28 % at the cost of one secure request.
