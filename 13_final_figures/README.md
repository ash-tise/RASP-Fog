# 13 — Final NSFNET figures

The three figures for the final report, on the 14-node, 21-link NSFNET model in
`../rasp_nsfnet.py`. All numbers are means over 10 independent seeds, with 95%
t-intervals (t = 2.262, 9 d.o.f.). For a given seed, every method and every x value
sees the same request trace and the same threat trace.

```bash
python3 tests/test_rasp_nsfnet.py                                  # 10 unit tests
RATE_FIG2=24 RATE_FIG3=14 python3 13_final_figures/run_figures.py  # ~3 min on 11 cores
```

Every setting is written to `config.json`. One row per run is in `figN_raw.csv`, and
the mean and CI are in `figN_summary.csv`.

## Methods (one code path, four switches in `POLICIES`)

| Method | Profile | Relocation | τ_H | Placement |
|---|---|---|---|---|
| RASP-Fog | adaptive | yes | 8 s | min J |
| RASP-Reloc | adaptive | yes | 0 | min J |
| RASP-Profile | adaptive | no (terminate if local upgrade fails) | 0 | min J |
| SA-FF | adaptive | yes | 8 s | first feasible node: fewest hops from ingress, then node ID, cloud last |
| Static-Strong | always q3 | n/a | n/a | min J |

## Run settings

- 300 s of Poisson arrivals, 60 s warm-up excluded, and sessions run to completion. The adaptation epoch is 1 s.
- Threat: a per-region random walk over levels 1–3 with steps every 5 s. Step-up probability is `p_up`, and step-down is held at 0.3.
- Fig. 1: fixed threat θ = 2 in every region; arrival rate from 8 to 80 req/s.
- Fig. 2: 24 req/s, just past the Fig. 1 knee; `p_up` from 0 to 0.6. Sessions are exponential, with a class mean of 10–40 s.
- Fig. 3: RASP-Fog at 14 req/s (about 64% fog CPU), `p_up` = 0.2, τ_H ∈ {0, 2, 4, 8, 16, 32} s.

## Results

**Fig. 1 (workload).** Secure completion is 100% for every method up to 16 req/s. The knee is at about 20 req/s, where fog CPU reaches 87%. Past it, admission rejection drives the decline, and SLA violations stay at 0 because new placements are only made if every request already on the node still meets its deadline. RASP-Fog beats SA-FF by a small but significant margin above the knee: paired differences are +0.5 to +1.2 points (for example, +1.18 ± 0.28 at 32 req/s). RASP-Fog beats Static-Strong by 2–3 points at 24–48 req/s, for example 89.0 vs 86.7% at 32 req/s. Static-Strong uses about 1.7× the security-only fog CPU: 15.4% vs 9.0% at 32 req/s.

**Fig. 2 (threat increases, 24 req/s).** The denominator is admitted requests with at least one mandatory upgrade. At p_up = 0.6, RASP-Profile (no relocation) terminates 7.15 ± 0.29%, about 3× the methods that can relocate: RASP-Fog 2.34 ± 0.36, SA-FF 2.66 ± 0.29, RASP-Reloc 2.79 ± 0.28. RASP-Fog vs SA-FF is within noise at most points, and the paired difference is −0.1 to −0.3 points. Relocation succeeds for about 72–75% of attempts and adds about 36 ms (20 ms ψ plus longer paths). Admission rejection (5.1–6.5%) is reported separately in `fig2_summary.csv`. No admitted request missed its deadline (`sla_miss_pct` = 0). Note that `sla_violation_pct` in the CSVs counts terminations as violations, so it is not a pure deadline metric.

**Fig. 3 (hysteresis, RASP-Fog, 14 req/s).** Profile changes per 1,000 admitted sessions drop from 829 at τ_H = 0 to 579 at 8 s and 313 at 32 s. Security-only CPU rises from 6.99% to 8.09%, because requests hold stronger profiles longer. τ_H = 2 and 4 s differ little from 0, because the threat only changes every 5 s. Secure completion is 100% at every τ_H at this load.

## Not modelled

- Admission delay τ_adm is not modelled; it is 0 in the code.
- Protection is checked at the 1 s adaptation epochs. A threat rise between epochs is handled at the next epoch.
