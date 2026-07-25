# Signals permutation-null calibration

Recorded output from `scripts/signals_permutation_null.py`.

- **draws:** 200
- **bootstrap B per feature:** 400 (null harness; production B=2000)
- **seed:** 4242
- **feature evals:** 2000
- **P(established):** 0.022 (44 / 2000)
- **P(emerging):** 0.186 (373 / 2000)
- **required:** P(established) ≤ 0.05, P(emerging) ≤ 0.2
- **pass:** True

**Raised floors (permutation-null feedback):** `ESTABLISHED_F` 4→**5**, `|θ̂|` 0.20→**0.25** in `effects.py`. Emerging gates unchanged.

