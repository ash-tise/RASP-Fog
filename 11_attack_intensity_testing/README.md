# Attack-intensity test

How mandatory upgrades trigger re-orchestration on NSFNET as the attack intensifies, near saturation, and what relocation adds over upgrading in place only.

```
python3 11_attack_intensity_testing/attack_intensity_test.py
```

Runs the 105 simulations in parallel, about 40 s on 4 cores. Uses the helpers of `10_nsfnet_load_testing`.

## Setup

Same model, run length and seeds as `10_nsfnet_load_testing`, at a fixed 24 req/s. The attack intensity p_up, the chance per region and 5 s step that the threat rises one level, goes from 0 to 0.6; the threat falls one level with chance 0.3. On a mandatory upgrade, RASP-Fog upgrades in place or relocates the session, No-Relocation upgrades in place or drops it, and Static-Strong never changes.

## Results

| p_up (mean threat) | Upgrades | Failed in place, RASP-Fog | Relocated | Rescued | Dropped, RASP-Fog / No-Relocation (%) | Secure, RASP-Fog / No-Relocation / Static-Strong (%) | Security CPU, RASP-Fog (%) |
|---|---|---|---|---|---|---|---|
| 0.0 (1.00) | 0 | 0 | 0 | – | 0.00 / 0.00 | 96.0 / 96.0 / 93.9 | 8.3 |
| 0.1 (1.35) | 356 | 14.6 | 10.2 | 70% | 0.15 / 0.39 | 96.0 / 95.8 / 93.9 | 9.0 |
| 0.2 (1.74) | 770 | 43.4 | 31.2 | 72% | 0.43 / 1.21 | 95.4 / 95.0 / 93.9 | 10.5 |
| 0.3 (2.07) | 964 | 45.2 | 33.6 | 74% | 0.41 / 1.13 | 95.3 / 94.6 / 93.9 | 11.8 |
| 0.4 (2.28) | 1180 | 56.8 | 44.2 | 78% | 0.44 / 1.60 | 94.9 / 93.9 / 93.9 | 12.9 |
| 0.5 (2.42) | 1071 | 54.6 | 40.8 | 75% | 0.48 / 1.49 | 94.4 / 93.8 / 93.9 | 13.5 |
| 0.6 (2.49) | 1028 | 54.2 | 38.6 | 71% | 0.55 / 1.42 | 94.4 / 93.9 / 93.9 | 13.8 |

Counts are per run, mean over 5 seeds, for about 2900 measured sessions per run.

- About 5% of mandatory upgrades do not fit on the current node. RASP-Fog relocates 70–78% of them; No-Relocation drops them all, so it drops 2.6–3.6 times as many sessions. The paired reduction in dropped sessions is significant at every p_up > 0.
- Relocation costs one ψ = 20 ms migration per moved session, at most about 15 per 1000 sessions.
- Upgrades peak at p_up = 0.4. At higher intensity more sessions arrive under a high threat and are admitted at q3, so fewer need an upgrade later.
- As the threat rises RASP-Fog uses stronger profiles, its security CPU approaches Static-Strong's 15.1%, and its advantage in secure completion narrows from 2.1 to 0.5 points.

## Output

`attack_results.csv`, `fig_attack_dropped.png`, `fig_attack_secure.png`.
