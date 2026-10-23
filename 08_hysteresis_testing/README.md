# Hysteresis test

Number of profile changes made by RASP-Fog for hysteresis holding intervals τ_H = 0, 2, 4, 8, 16 and 32 s, on the same requests and the same time-varying threat, averaged over five seeds.

```
python3 08_hysteresis_testing/hysteresis_test.py
```

Writes `hysteresis_results.csv` and `fig8_profile_changes.png`. The figure needs `matplotlib`.

## Setup

| Setting | Value |
|---|---|
| Policy | RASP-Fog, with τ_H varied |
| Arrival rate | Poisson, 4 requests per second |
| Request type | uniform random |
| Duration | exponential, mean 20 s (sensor), 30 s (camera), 10 s (health) |
| Node capacity | CPU, memory and bandwidth of every node × 10, as in tests 06 and 07 |
| Threat | updated every 5 s: up one level (p = 0.3), down one level (p = 0.3), or unchanged |
| Run length | 300 s |
| Seeds | 1–5; within a seed every τ_H sees the same requests and threat changes |
| Setup delay | 5 ms orchestrator round trip, added at admission |

Traffic and threat come from the generator in `04_random_testing/random_test.py`. Requests are sessions rather than the short tasks of tests 06 and 07, because hysteresis only matters for requests that stay active through several threat changes. At this load the fog is about 45 % utilized and no request is rejected, so every profile change is caused by the threat.

A **profile change** is an upgrade, a relocation or a downgrade. A **re-upgrade** is an upgrade or relocation of a request that was downgraded earlier in its life.

## Results (per run, mean over seeds)

| τ_H (s) | All changes | Upgrades | Downgrades | Re-upgrades | Fewer changes than τ_H = 0 | More security CPU than τ_H = 0 |
|---|---|---|---|---|---|---|
| 0 | 780 ± 196 | 396 | 384 | 156 | – | – |
| 2 | 749 ± 194 | 396 | 353 | 156 | 4.0 ± 0.9 % | 1.8 ± 0.3 % |
| 4 | 721 ± 192 | 396 | 325 | 156 | 7.7 ± 2.0 % | 3.5 ± 0.7 % |
| 8 | 529 ± 94 | 329 | 200 | 79 | 31.2 ± 11.2 % | 6.2 ± 1.2 % |
| 16 | 368 ± 51 | 274 | 94 | 21 | 52.0 ± 7.1 % | 9.7 ± 1.6 % |
| 32 | 298 ± 51 | 260 | 38 | 6 | 61.3 ± 5.4 % | 13.2 ± 2.3 % |

The confidence intervals on the absolute counts are wide because each seed has a different threat path. The last two columns compare each τ_H with τ_H = 0 on the same seed, which removes that variation. No request is under-protected, terminated or rejected, and no node exceeds capacity, for any τ_H.

- Hysteresis cuts profile changes from 780 to 529 per run at τ_H = 8 s (−31 %) and to 298 at τ_H = 32 s (−61 %).
- The cut comes from removing flip-flops: a request downgraded during a short threat dip and upgraded again when the threat returns. Re-upgrades fall from 156 per run to 6 at τ_H = 32 s.
- τ_H below the 5 s threat update interval has little effect. Every threat dip lasts at least 5 s, so τ_H = 2 or 4 only delays the downgrade and never prevents the re-upgrade that follows. Only requests that finish during the delay avoid a change. The holding interval has to exceed the typical length of a threat dip to filter it.
- Upgrades are never delayed by hysteresis, so security is never weakened. The cost is that requests keep a stronger profile for longer after the threat drops, which raises the fog's security CPU by 6 % at τ_H = 8 s and 13 % at τ_H = 32 s.
- τ_H therefore trades fewer profile changes (less switching delay ρ, fewer reconfigurations) for more security overhead. Around 8–16 s gives most of the reduction for a modest overhead in this setting.
