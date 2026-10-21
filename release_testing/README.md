# Release test

Adds request completion: each request has a fixed duration and releases its resources when it ends, so load rises and falls.

```
python3 release_testing/release_test.py
```

## Setup

- 120 requests, one per second, same fixed order as the fill-up test.
- Durations: sensor 20 s, camera 30 s, health 10 s.
- Threat level rises to 3 at t = 30, 53 and 100, with a 3 s dip at t = 50.
- No randomness. `rasp_core.py` is unchanged; this script has its own run loop with a completion step.

## Output

A CPU-per-node timeline every 10 s for RASP-Fog, a comparison table for all policies, and four checks.

## Results

| Policy | Admitted | Rejected | Completed | Terminated | Under | Secure | Changes |
|---|---|---|---|---|---|---|---|
| RASP-Fog | 120 | 0 | 99 | 1 | 0 | 119 | 44 |
| No-Hysteresis | 120 | 0 | 99 | 2 | 0 | 118 | 78 |
| No-Relocation | 109 | 11 | 91 | 0 | 2 | 107 | 45 |
| Static-Strong | 120 | 0 | 100 | 0 | 0 | 120 | 0 |
| Static-Light | 118 | 2 | 98 | 0 | 111 | 7 | 0 |

- At this load the cloud never exceeds half its CPU, so Static-Strong pays nothing for q3 and matches RASP-Fog.
- RASP-Fog terminated one camera that could not be upgraded in time at t = 30.
- No relocations occur: every upgrade fits in place.
