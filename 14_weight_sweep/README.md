# 14 — Cost-weight sweep

Does RASP-Fog do better with different weights in its cost J = λ_D·d̃ + λ_O·õ? Runs on the NSFNET model in `../rasp_nsfnet.py` with the run settings of `13_final_figures` (300 s, 60 s warm-up, deadline protection on, τ_H = 8 s). The defaults in `rasp_nsfnet.py` (λ_D = λ_O = 0.5, ω = 1/3 each) are not changed; weights are set per run.

```bash
python3 14_weight_sweep/sweep.py        # 740 runs
python3 14_weight_sweep/rate_check.py   # 200 runs, imports sweep.py
```

## Method

- **Swept:** λ_D ∈ {0, 0.25, 0.5, 0.75, 1} with λ_O = 1 − λ_D, and eight overhead weightings ω = (CPU, memory, bandwidth). At λ_D = 1 only the default ω is run, since ω has no effect there. That gives 33 combinations.
- **Scenarios:** 24 req/s (just past the knee in test 13) with either a fixed threat θ = 2 (`fixed_theta2`) or a regional random walk with p_up = 0.3 (`walk_p0.3`).
- **Tune, then evaluate:** every combination runs on tuning seeds 101–110. The best one per scenario (highest secure completion, ties broken by lower security CPU) is then rerun on evaluation seeds 1–10, the seeds used in test 13, next to the default weights, SA-FF and Static-Strong. Differences are paired by seed, with 95% t-intervals.
- **`rate_check.py`:** fixed θ = 2, default ω, RASP-Fog at λ_D ∈ {0.25, 0.4, 0.5} and SA-FF at 16–48 req/s, evaluation seeds. Checks whether the tuned λ_D still helps away from 24 req/s.

## Output

| File | Content |
|---|---|
| `tune_raw.csv`, `tune_summary.csv` | Every combination on the tuning seeds: per run, and mean ± CI |
| `eval_raw.csv`, `eval_summary.csv` | Default vs tuned weights vs SA-FF vs Static-Strong on the evaluation seeds; `*_vs_default` columns hold paired differences from default RASP-Fog |
| `rate_check_raw.csv` | One row per run of `rate_check.py`; the script prints the per-rate means |

No figures.

## Results

**Evaluation seeds, 24 req/s (mean ± 95% CI):**

| Scenario | Method | λ_D | ω | Secure (%) | Security CPU (%) | Rejected (%) | Fog CPU (%) | Cloud (%) | Mean delay (ms) |
|---|---|---|---|---|---|---|---|---|---|
| fixed θ = 2 | RASP-Fog default | 0.5 | 1/3 each | 94.55 ± 0.40 | 8.77 | 5.45 | 91.1 | 4.2 | 57.5 |
| | RASP-Fog tuned | 0 | 0.5/0/0.5 | 100.00 ± 0.00 | 6.27 | 0.00 | 63.2 | 26.6 | 65.2 |
| | SA-FF | 0.5 | 1/3 each | 94.10 ± 0.50 | 8.80 | 5.90 | 91.6 | 4.2 | 58.6 |
| | Static-Strong | 0.5 | 1/3 each | 92.50 ± 0.47 | 15.23 | 7.50 | 91.4 | 5.4 | 61.6 |
| walk p_up = 0.3 | RASP-Fog default | 0.5 | 1/3 each | 93.48 ± 0.52 | 11.67 | 5.88 | 91.1 | 4.6 | 58.8 |
| | RASP-Fog tuned | 0.25 | 0.6/0.2/0.2 | 99.99 ± 0.01 | 8.92 | 0.00 | 69.1 | 25.5 | 62.3 |
| | SA-FF | 0.5 | 1/3 each | 93.30 ± 0.60 | 11.70 | 5.97 | 91.5 | 4.7 | 59.2 |
| | Static-Strong | 0.5 | 1/3 each | 92.50 ± 0.47 | 15.23 | 7.50 | 91.4 | 5.4 | 61.6 |

Paired against default RASP-Fog, the tuned weights add +5.45 ± 0.40 points (fixed) and +6.50 ± 0.51 points (walk) of secure completion, and cut security CPU by 2.5–2.8 points. SA-FF is −0.46 ± 0.23 (fixed) and −0.19 ± 0.17 (walk), the second within noise.

**Tuning seeds.** λ_D drives the result. At λ_D = 0 every ω gives 98.7–100% secure completion, and at λ_D = 0.25 it gives 96.1–100%, depending on ω. Every combination with λ_D ≥ 0.5 stays at 93.0–94.8%.

**Across load (`rate_check.py`, fixed θ = 2, secure completion %):**

| Rate (req/s) | λ_D = 0.25 | λ_D = 0.4 | λ_D = 0.5 (default) | SA-FF | Cloud share at λ_D = 0.25 / 0.5 | Mean delay at λ_D = 0.25 / 0.5 (ms) |
|---|---|---|---|---|---|---|
| 16 | 100.00 | 100.00 | 100.00 | 99.99 | 30.6 / 0.0 | 60.3 / 33.5 |
| 24 | 100.00 | 94.72 | 94.55 | 94.10 | 23.2 / 4.2 | 57.7 / 57.5 |
| 32 | 95.38 | 89.29 | 89.01 | 87.83 | 16.8 / 10.3 | 65.9 / 65.1 |
| 40 | 85.72 | 82.99 | 82.68 | 81.61 | 13.7 / 11.9 | 67.8 / 67.7 |
| 48 | 77.73 | 76.52 | 76.44 | 75.48 | 11.9 / 11.3 | 67.7 / 68.1 |

- The overhead term õ divides each overhead by the node's free capacity, so the elastic cloud scores near zero on it. A low λ_D therefore pushes RASP-Fog to send a quarter or more of requests to the cloud before the fog fills. At 24 req/s fog CPU then stays near 63–69% instead of 91%, and nothing is rejected.
- The gain is largest just past the knee (+5.4 to +6.4 points at 24–32 req/s) and shrinks to about +1.3 points at 48 req/s, where the fog saturates anyway.
- The cost is delay at light load: at 16 req/s, λ_D = 0.25 nearly doubles mean delay (33.5 → 60.3 ms) for no completion gain. λ_D = 0.4 behaves like the default.
- The weight choice moves secure completion far more than the placement rule does (RASP-Fog vs SA-FF is under 1.2 points at every rate).
- Test 13 and the final report use the default weights, so their numbers are unaffected by this sweep.
