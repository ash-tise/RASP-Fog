# Fill-up test

Checks that RASP-Fog follows Algorithms 1 and 2 step by step.

```
python3 01_fillup_testing/fillup_test.py
```

## Setup

- 48 requests, one per second, in a fixed order: sensor, camera, health, …
- Reserved resources are never released, so load only increases.
- Threat level: 1, rising to 3 at t = 15, 21 and 38; a 3 s calm dip at t = 18 and a longer calm from t = 26.
- No randomness: every run prints the same log.

## Output

1. **Event log:** one line per decision (ADMIT, REJECT, UPGRADE, MOVE, TERMINATE, DOWNGRADE), with the delay split into processing and communication.
2. **Final occupancy:** CPU, memory and bandwidth reserved on each node.
3. **Totals:** event counts, first cloud placement and first rejection.
4. **Checks:** four PASS/FAIL lines.

## Results

| Time (s) | Behaviour |
|---|---|
| 0–14 | Requests fill Fog-1 first, then Fog-3 and Fog-2; delays grow with load. |
| 15 | Attack: 10 requests upgraded in place, 1 relocated because it no longer fit. |
| 16 | First request placed on the cloud. |
| 18–20 | 3 s calm dip: no downgrades (shorter than τ_H). |
| 20 | First rejection: a health request cannot meet 60 ms once the fog is full. |
| 34 | 18 requests downgraded after 8 s of calm. |
| 38 | Attack: 2 cameras terminated because q3 could not be met anywhere on time. |

Totals: 35 admitted, 13 rejected, 35 upgrades, 1 relocation, 2 terminations, 18 downgrades. All four checks pass: no under-protection, no capacity violation, upgrades on threat increase, and fewer profile changes with hysteresis (54 vs 75).
