# Deadline-protection test

Sensitivity of the NSFNET results to deadline protection: a placement (admission, upgrade or relocation) is allowed only if every request already on the node still meets its deadline at the new CPU utilization.

```
python3 12_protection_testing/protection_test.py
```

Runs the 240 simulations in parallel, about 1.5 min on 4 cores. Uses the helpers of `10_nsfnet_load_testing`.

## Setup

The load sweep of `10_nsfnet_load_testing` (rates 12–40 req/s, threat p_up = 0.2, seeds 1–5) with `PROTECT` on and off. With protection off, Algorithms 1 and 2 check only the deadline of the request being placed, so later placements can raise a node's queueing delay past the deadlines of requests already running there. Those requests count as runtime SLA misses. An SLA violation is an admitted session that is dropped or pushed past its deadline, so with protection on it is only the dropped sessions, and with protection off it also includes the runtime misses.

## Results

| Rate (req/s) | Secure, on: RASP-Fog / Static-Strong (%) | Secure, off: RASP-Fog / Static-Strong (%) | Runtime SLA misses, off: RASP-Fog (%) | Relocations, on / off |
|---|---|---|---|---|
| 20 | 99.1 / 98.3 | 96.1 / 94.2 | 3.1 | 13.0 / 2.0 |
| 24 | 95.4 / 93.9 | 82.5 / 84.7 | 12.5 | 31.2 / 5.6 |
| 28 | 92.0 / 90.3 | 74.7 / 77.1 | 15.8 | 38.8 / 7.0 |
| 32 | 88.8 / 87.4 | 69.7 / 72.2 | 16.6 | 45.6 / 8.0 |
| 40 | 83.7 / 81.8 | 62.2 / 61.2 | 17.3 | 58.0 / 9.8 |

- Without protection, 11–19% of sessions are pushed past their deadline from 24 req/s on, for every policy, and secure completion falls by 9–22 points.
- Nodes then run at the edge of their deadlines, so an upgrade that does not fit in place rarely fits anywhere else: relocations fall by about 80% and RASP-Fog and No-Relocation are indistinguishable.
- Without protection, Static-Strong beats RASP-Fog by 2.1–2.6 points at 24–32 req/s. Its larger reservations make it reject more at admission, which leaves less load to push running sessions late.
- RASP-Fog's advantage over both baselines therefore depends on deadline protection, which is part of the model used in 09–11.

## Output

`protection_results.csv`, `fig_protection.png`.
