# Marrow Signals — statistical method spec

Replaces `compute_correlates` / `spearmanr` as the engine behind the Signals page.
Outcome: `overall`, integer 1–5 (v4), higher better. n-of-1, one model per user,
92–400 usable days. All effect sizes are **points on the 1–5 scale**.

Reference constants used throughout (from the mock, which matches realistic values):
`σ_y = 0.95` (day-to-day SD), `σ_resid = 0.77` (holdout RMSE of the full model),
`σ_noise = 0.63` (irreducible SD ≡ MAE 0.50), `n_usable = 92`.

---

## Part A — the case against Spearman-over-lags

### A1. The multiple-comparisons arithmetic

`STATIC_COLUMNS` has 55 entries. `_EXCLUDE_FROM_CORRELATES` removes 8 of them,
and the outcome removes 1 more → **46 static candidates**. Add the dynamic
families: `supp_*` (a real catalog is 15–25 keys), `tx_*_active` (3–8),
`sym_*` (8–15). Call it **~85–95 candidate columns**, which matches the ~100 in
the UX brief. `compute_correlates` loops `for lag in range(3)` over every one of
them:

> **m ≈ 255–285 hypothesis tests, zero correction, per page load.**

At n = 90 the two-sided 5% critical value for Spearman is

    |ρ|_crit = sqrt(t²/(t² + n−2)),  t = t_{0.975, 88} = 1.9873  →  |ρ|_crit = 0.207

(the familiar `1.96/√(n−1) = 0.208` agrees). Consequences, in order of severity:

| quantity | value |
|---|---|
| uncorrected critical \|ρ\| at n=90 | **0.207** |
| expected number of null features clearing it, m=285 | **14.2** |
| rows the table actually shows (15 pos + 15 neg) | **30** |
| Bonferroni critical \|ρ\| (α = 0.05/285, z = 3.752) | **0.398** |
| E[max \|ρ\|] over 285 pure-noise tests (20k sims) | **0.326** |
| 95th pct of that null max | **0.398** |

Read the last two rows together: **a dataset containing no signal whatsoever
produces a top-of-table |ρ| of about 0.33, and 0.40 one time in twenty.** Real
behavioural effects in this domain — the mock's own drivers, converted to
point-biserial — land at |ρ| = 0.20–0.38. The entire dynamic range of the true
signal sits *inside* the null's max distribution. The table cannot separate its
strongest true finding from its luckiest noise, and it prints the noise first,
because it sorts by exactly the statistic the noise maximises.

Reducing m for correlated tests does not rescue it: the three lags of one column
are highly dependent and `wx_temp_mean/min/max` are near-collinear, so the
*effective* m might be ~150. E[max |ρ|] at m=150 is 0.305 and the Bonferroni
threshold is 0.380 — a 6% improvement on a fatal number.

### A2. max-|ρ|-over-3-lags is biased upward, twice

`compute_correlates` keeps `best_rho` = the largest |ρ| across lags 0, 1, 2 and
reports it with no penalty. Two separate inflations:

1. **Selection over lags.** Testing 3 lags and keeping the max makes the
   per-feature false-positive rate `1 − 0.95³ = 0.1426`, not 0.05. A reported
   max-of-3 |ρ| = 0.21 carries a true p-value of **0.143**, not 0.05. To make
   the *feature* significant at 5% you need per-lag α = 0.0170, i.e.
   **|ρ| ≥ 0.253**. Across ~90 features that is 12.8 expected null features
   passing — which is where the 14 comes from in A1.

2. **Selection over n.** `spearmanr` is pairwise-complete, so n differs by lag
   (a lag-2 alignment drops 2 rows, and any feature with gaps drops more). SE(ρ)
   ∝ 1/√n, so *the lag with the fewest usable pairs has the widest sampling
   distribution and therefore the best chance of producing the max*. The
   selection rule systematically prefers the noisiest alignment. `best_n` is
   reported, but nothing uses it, and the ranking is done on ρ alone — so a
   ρ = 0.34 on n = 22 outranks a ρ = 0.30 on n = 88.

3. **Autocorrelation manufactures the lag structure.** `overall` is
   autocorrelated at φ ≈ 0.4–0.5. Any same-day contamination of size ρ₀
   automatically produces a lag-1 correlation of ≈ φρ₀ (0.50 → 0.23 at φ=0.45).
   So a mirror variable that correlates 0.50 same-day *also* appears as a
   ~0.23 "lag 1" finding — above the uncorrected threshold, and dressed in the
   one piece of evidence a user reads as causal ("it happened the day before").

### A3. The specific confounders in *this* dataset

All four are present in `feature_matrix.py` and none are adjusted for.

- **Slow trend.** The mock's own trends show `overall` drifting −0.3 over 30
  days. Any feature that also drifts picks up correlation from nothing but
  shared time: a `supp_*` started mid-window is a step function, and against a
  0.3-point (0.32 σ) drift a 50/50 step yields ρ ≈ 0.16 with no causal link
  whatsoever — half the top-of-table value. `tx_*_active` is *pure* step
  function and is therefore the worst offender in the whole matrix.
- **Day of week.** Alcohol, eating out, sleep duration, steps and `overall`
  itself all have weekly cycles. The mock's Saturday baseline (3.5) is above
  the overall mean (3.41). Because weekends are simultaneously the good-mood
  days and the drinking days, the day-of-week channel pushes alcohol's ρ
  *positive* while the true effect is negative — attenuating the measured
  association by ~40% and, at smaller true effects, flipping its sign.
- **`sick` as a common cause.** `sick` is a candidate feature, an allowed
  outcome, and never a covariate. At a realistic 8% of days and a −1.2-point hit
  (d = 1.26), `r(sick, overall) = 1.26 × √(0.08·0.92) = 0.343`. Every variable
  that moves on sick days inherits a share: with `r(sick, x) = 0.5` — steps,
  resting HR, HRV, sleep efficiency, appetite, photo count all clear that
  easily — the induced spurious `r(x, overall) = 0.171`, **half of the 0.33 that
  tops the table**. One unmodelled binary can generate the entire visible
  ranking.
- **Reverse causation from same-day self-report.** `_EXCLUDE_FROM_CORRELATES`
  excludes 8 columns, *none of them* `sym_*`, `stress`, `bloating`, `joint_pain`,
  or `neuro`. These are written into the same check-in, in the same minute, in
  the same mood, as `overall`. Their ρ is bounded only by how coupled the two
  answers are — 0.4 to 0.6 in practice, the mock's mirrors are −0.5 to −0.8
  points. So the current top-15-negative list is **structurally guaranteed** to
  be led by restatements of the outcome, and `sym_*` grows without limit as the
  user adds symptoms. The page gets worse the more diligently it is used.

### A4. Rank correlation is blind to the two effect shapes that matter here

ρ measures monotone association. The two shapes that dominate this domain are
not monotone-informative.

**Thresholds.** Simulated at n = 92, 200 replicates, using the mock's own sleep
bins with the *same* sub-6.5h penalty in each case:

| true shape | Spearman on continuous hours | threshold contrast |
|---|---|---|
| cliff at 6.5 h, flat above | 0.285 | 0.321 |
| smooth linear slope, same range | 0.314 | 0.266 |
| U-shape (oversleeping also bad) | **0.086** | 0.252 |

The cliff and the linear slope are indistinguishable by ρ (0.285 vs 0.314) but
imply *different behaviour*: "never drop below 6.5 h" versus "every extra hour
helps". ρ cannot tell the user which one they are in. And the U-shape — a real,
strong, actionable non-monotone effect — collapses to |ρ| = 0.086, **below the
uncorrected critical value**, so it is not merely mis-ranked, it is invisible.

**Interactions.** In the mock's 2×2 world (main effects −0.44 and −0.58, excess
−0.32 on the 11 both-days), the marginal correlations are ρ = −0.322 for
histamine and −0.378 for short sleep. Both are below the Bonferroni threshold of
0.393 and both are inside the noise-max distribution (E[max|ρ|] = 0.326). The
actual finding — **1.4 σ when the two coincide** — has no representation in a
correlation table at all. Its contribution to histamine's marginal number is
−0.32 × (11/29) = −0.12 points, buried inside the −0.44 and unrecoverable.

### A5. Sparse binary features are mis-estimated, then quietly discarded

For a binary exposure at prevalence p, the point-biserial correlation is
`r ≈ d·√(p(1−p))` where d is Cohen's d. `√(p(1−p))` is a pure exposure-balance
factor with nothing to do with the effect:

| exposure | p | √(p(1−p)) | ρ for a real 0.72-point effect (d=0.76) |
|---|---|---|---|
| supplement taken 8/90 days | 0.089 | 0.285 | **0.216** |
| alcohol 2u, 19/92 days | 0.207 | 0.405 | 0.307 |
| magnesium, 41/92 days | 0.446 | 0.497 | 0.377 |

The *same* 0.72-point effect reads as ρ = 0.22 or ρ = 0.38 depending only on how
often the user happened to take the thing. ρ ranks by exposure balance as much
as by effect. And 0.216 is under the Bonferroni threshold of 0.398 — a genuinely
large effect on a sparsely-taken supplement is **arithmetically incapable** of
reaching a corrected significance bar, while a mirror variable clears it
trivially. The ranking is upside down by construction.

`min_n = 10` then does damage in a different place than expected: `supp_*` is
`False` (not `None`) on entry days, so n counts *entry days*, ~90, and the
sparse supplement is **not** filtered — it is admitted with 8 informative days
and an unstable estimate that moves 0.03 in ρ per single day reclassified. What
`min_n` *does* silently drop is anything genuinely `None`-heavy: `hm_*` on the
26 of 118 unworn-watch days, a `sym_*` key added three weeks ago, dietary loads
on days without a confirmed photo. Those features vanish from the response with
no row, no flag, and no count — the user cannot tell "we looked and found
nothing" from "we could not look".

### A6. Bonus: `compute_treatment_response` has the same disease, worse

The delta is `mean(during) − mean(baseline)` over a fixed 30-day pre-window, with
**no interval, no trend adjustment, and no covariates**. People start treatments
when they feel worst, so the baseline window is *selected on a low*. If the
pre-window sits 0.5 σ below the user's own level, regression to the mean alone
predicts a +0.48-point "improvement" — larger than any real effect on the page.
The `after` window has the mirror-image problem. Any replacement must give this
panel a pre-registered comparison and an interval (§C).

---

## Part B — the replacement, in four layers

Scope decision first: **estimate on `schema_version >= 4` days only.** Legacy 1–3
entries stay in the trend chart but are excluded from Layers 1–4. Rescaling a
3-point scale onto a 5-point one invents resolution that was never recorded, and
92+ v4 days is enough. Report the excluded count in `model.limits`.

### Layer 1 — personal-baseline residualisation

**Model.** For each usable day t:

    ŷ_base(t) = L(t) + W(dow(t)) + T(t) + β_sick · sick(t)

- `L(t)` — **rolling personal level**: exponentially weighted mean of `overall`
  over days strictly before t, half-life 21 days (α = 1 − 2^(−1/21) ≈ 0.0325),
  computed on observed days only, initialised to the user's first-28-day mean.
- `W(d)` — **day-of-week offset**, 7 values, fitted on days strictly before t
  and **shrunk to zero**: `Ŵ(d) = n_d/(n_d + 10) · (mean_d − overall_mean)`.
  The k = 10 prior stops 7 free parameters from eating a 92-day dataset; at
  n_d = 13 (one weekday over 92 days) the offset is shrunk by 43%.
- `T(t)` — **slow trend**: the 56-day trailing linear slope of `overall`,
  extrapolated one day. Deliberately smooth: it must absorb season and life-phase
  drift without absorbing the exposures. Cap |T| at 0.02 points/day.
- `β_sick · sick(t)` — a single indicator, coefficient fitted on prior days.
  `sick` is the strongest single confounder in the matrix (§A3) and is *always*
  in the baseline, never in the driver list.
- Also in the baseline, never as drivers: `tx_*_active` as regime indicators
  (they are step functions collinear with `T`), and `photo_count`/
  `ingredient_count` as **logging-coverage** covariates (you photograph less on
  bad days; leaving them out lets diet features absorb the missingness).

**Residual.** `r(t) = overall(t) − ŷ_base(t)`. Every estimate in Layers 2–4 is
computed on `r`, not on `overall`. Report effects back in points (r is already in
points).

**No leakage.** Every component of `ŷ_base(t)` uses only days `< t`: trailing
EWMA, trailing slope, expanding-window shrunk weekday means, expanding-window
`β_sick`. So `r(t)` is a genuine **one-step-ahead** residual. Two payoffs: the
calibration strip in the UI is showing real out-of-sample error rather than an
in-sample fit, and `baselineMae` is a legitimate skill reference rather than a
number the baseline was tuned to beat. Cost: the first 28 days are warm-up and
are excluded from estimation (report as a limit).

**Failure mode.** If an exposure is *itself* slow-moving — a supplement started
once and never stopped, a treatment, a seasonal weather variable — `L` and `T`
absorb its effect and the driver estimate goes to zero. This is the correct
answer (the data genuinely cannot separate them) but it must be *said*: any
feature whose exposure series has ≥ 0.6 correlation with `T` is marked
`confounded-with-trend` and forced to `watching` with that reason shown, rather
than reported as a null.

### Layer 2 — the feature taxonomy the UI enforces

Three classes. **`mirror` is a hard exclusion from the driver list**, not a
demotion — it appears only in the "set aside" disclosure, with its raw number,
so the discipline is visible.

**`lever` — modifiable, and measured before or during the day**

| column family | note |
|---|---|
| `alcohol_units`, `had_alcohol` | dose and threshold both meaningful |
| `caffeine_servings`, `had_caffeine` | |
| `hot_shower` | |
| `histamine_load_sum`, `histamine_load_max` | |
| `fodmap_oligos_sum`, `fodmap_fructose_sum`, `fodmap_polyols_sum`, `fodmap_lactose_sum` | |
| `gluten_exposure`, `dairy_exposure` | |
| `manual_extra_dairy/fodmap/gluten/histamine` | lever, but conditional on photo coverage — pair with the coverage covariate |
| `hm_sleep_hours`, `hm_sleep_start`, `hm_sleep_end` | duration and timing are choosable |
| `hm_steps`, `hm_active_minutes` | **lag ≥ 1 only** — same-day activity is caused by the day |
| `supp_*` (all) | |
| `tx_*_active` (all) | lever in principle, but step-shaped → baseline term + §C treatment panel only, never a driver card |

**`context` — real, and worth modelling, but not actionable**

| column family | note |
|---|---|
| `wx_temp_mean/min/max`, `wx_humidity_mean`, `wx_pressure_mean`, `wx_pressure_delta` | |
| `wx_condition` | categorical → one-hot the top 3 conditions, rest to "other" |
| `hm_sleep_deep_min`, `hm_sleep_rem_min`, `hm_sleep_core_min`, `hm_sleep_awake_min`, `hm_sleep_deep_pct`, `hm_sleep_rem_pct`, `hm_sleep_efficiency` | sleep *architecture* — you cannot decide to get more deep sleep. This is the sharp line inside the `hm_sleep*` family: duration/timing = lever, architecture = context |
| `hm_hrv_mean`, `hm_hrv_std`, `hm_resting_hr`, `hm_spo2`, `hm_wrist_temp_deviation` | **context at lag ≥ 1 only** (see mirror below) |

**`mirror` — same-day, moves with the outcome rather than ahead of it**

| column family | note |
|---|---|
| `bloating`, `joint_pain`, `neuro`, `stress` | same check-in, same minute, same mood as `overall` |
| `sleep_quality` | same check-in; at lag ≥ 1 it may be used as a lever-proxy, at lag 0 it is a mirror |
| `sick` | mirror *and* common cause → baseline term (Layer 1), never a driver |
| `stool_status`, `bristol_type` | same-day symptom report; `bristol_type` is also non-monotone (3–4 optimal) so it must be binned, never correlated |
| `sym_*` (all) | mirror by construction; this family grows without bound as the user logs more |
| `hm_hrv_*`, `hm_resting_hr`, `hm_spo2`, `hm_wrist_temp_deviation` **at lag 0** | physiology responding to the day |
| `photo_count`, `ingredient_count` | *logging-behaviour* mirrors — fewer photos on bad days. Coverage covariates only |

**Not features at all**: `date`, `schema_version`, `period_of_day` (metadata
about when the check-in was filed — use as a data-quality covariate; a check-in
filed at 23:50 is a different measurement instrument from one filed at 09:00),
`overall` (the outcome).

**Failure mode.** The lever/context/mirror line is a *judgement about the world*,
not a statistic, so it is wrong in edge cases and cannot be detected as wrong
from data. The mitigation is that it is visible: the taxonomy label is on every
card, and a mirror's raw number is shown, so a user who disagrees can see exactly
what was set aside and why.

### Layer 3 — effect estimation with uncertainty

**Estimator: contrast of residual means on a binarised exposure.**

    θ̂ = mean(r | exposed) − mean(r | unexposed)          [points on the 1–5 scale]

Not ρ. This is a number with a unit the user can act on, it is unaffected by
exposure balance (§A5), it is the same quantity a randomised experiment would
estimate (§C), and it is exactly what the waterfall needs (§Layer 4).

**Binarisation rule, by shape:**

| `shape` | exposure definition | how the shape is chosen |
|---|---|---|
| `binary` | the flag itself | native (all `supp_*`, `gluten_exposure`, `dairy_exposure`, `had_*`, `manual_extra_*`) |
| `threshold` | `x ≥ c` (or `≤ c`) | c chosen **inside each CV fold** from a fixed candidate grid: the 20th/25th/33rd/50th/67th/75th/80th percentiles of x on the training days. Never chosen on the full sample — that is the tuned-threshold leak |
| `linear` | top tertile vs bottom tertile of x | reported as a tertile contrast, never as a slope; a "slope in points per unit" invites the monotonicity assumption ρ already failed at |
| `interaction` | `A ∧ B` vs `¬A ∧ ¬B` | 2×2 cell contrast; the reported `excess` is `(Both − Neither) − (A only − Neither) − (B only − Neither)` |

Shape is *declared per feature family*, not searched. Searching shapes per
feature reintroduces the selection problem the whole spec exists to remove:
sleep duration is `threshold` because there is a physiological floor;
supplements are `binary` because that is how they are logged; steps is
`threshold` at a low cut because the mechanism is "did not move at all",
not "moved more".

**Interval: moving-block bootstrap.**

- **B = 2000** resamples (enough that the 2.5/97.5 percentiles are stable to
  ±0.01 points; 500 is visibly jumpy at n=92, 10000 buys nothing).
- **Block length L = 7 days**, circular moving blocks over the date-ordered
  residual/exposure pairs. `n^(1/3) ≈ 4.5` is the textbook starting point at
  n = 92; round *up* to 7 so each block also carries one complete weekly cycle
  and any residual weekday structure the shrunk `W(d)` left behind.
- Interval = percentile [2.5, 97.5] of the 2000 θ̂*.
- Resample the **whole pipeline**: re-binarise inside each resample, so
  threshold-selection variance is inside the interval.

**Why not a t-interval.** The naive `SE = σ_r·√(1/n₁ + 1/n₂)` assumes independent
days. Residual autocorrelation is φ ≈ 0.4, and — worse — *exposures cluster*:
alcohol on weekends, sleep debt in runs, a heatwave, a supplement taken in
stretches. Both effects push the true SE above the naive one; for observational
(self-selected, clustered) exposure at φ ≈ 0.4 the SE inflation `√DEFF` is
**1.15–1.25**, i.e. DEFF ≈ 1.3–1.55, so a t-interval is **15–25% too narrow**.
Use `√DEFF = 1.2` (DEFF = 1.44) as the default — deliberately higher than the
1.3 used for *randomised* block designs in §C, because assigned exposure
clusters less than chosen exposure. Concretely, the mock's alcohol driver at
19/73 days has naive half-width 0.39 and correct half-width 0.47. Publish the ratio
`bootstrap SE / naive SE` as a diagnostic: **if it exceeds 1.5, the exposure is
too clustered to be separated from the trend** and the feature is forced to
`watching` with that reason shown.

**Stability: time-blocked cross-validation.**

Split the usable days into **K = 5 contiguous, date-ordered folds** (not random
folds — random folds put yesterday in train and today in test and leak the
autocorrelation). For each fold k: refit **everything** on the other four folds
— the Layer-1 baseline coefficients, the binarisation threshold, the effect —
then evaluate θ̂ₖ on the held-out fold.

    F = #{ k : sign(θ̂ₖ) = sign(θ̂_full)  AND  |θ̂ₖ| ≥ 0.5·|θ̂_full| }

**Exact tier rules.**

*Preconditions — fail any and the feature is `insufficient`, listed with its
reason, never tiered:*

- taxonomy class ≠ `mirror` (mirrors go to the set-aside list regardless)
- feature observed on ≥ 30 usable days
- exposed days ≥ 5, unexposed days ≥ 5
- exposed **runs** ≥ 2, where a run is a maximal consecutive stretch of exposed
  days. This is what stops one 15-day holiday from becoming an "effect"
- not flagged `confounded-with-trend` (Layer 1 failure mode)

*Then, with θ̂ the point effect, CI the 95% block-bootstrap interval, F the fold
count, X exposed days, R exposed runs:*

- **`established`** — `F ≥ 4` **and** CI excludes 0 **and** `X ≥ 15` **and**
  `R ≥ 4` **and** `|θ̂| ≥ 0.20` points **and** bootstrap/naive SE ratio ≤ 1.5
- **`emerging`** — `F ≥ 3` **and** `X ≥ 10` **and** `R ≥ 3` **and**
  (CI excludes 0 **or** the zero-side bound is within **0.10 points** of 0)
  **and** `|θ̂| ≥ 0.15` points
- **`watching`** — met the preconditions, missed the two rules above
- **`mirror`** — taxonomy class is `mirror`; overrides everything
- **interactions** additionally require `|excess| ≥ 0.25` points and
  co-exposed days ≥ 8, and are **capped at `emerging`** until co-exposed ≥ 20
  and the *excess* term's own CI excludes 0

The `|θ̂| ≥ 0.20` floor is roughly a third of the noise floor SD (0.63). Below
that, an effect is real-but-unusable: it cannot be perceived on any single day
and no realistic experiment can confirm it (§C).

**Why fold stability solves what a corrected p-value does not.** A p-value —
even Bonferroni-corrected — is computed on the same 92 days that chose the
feature, the lag, the shape, and the threshold. Its null distribution is the one
for a *pre-specified* test, and no such test was performed. Correcting for the
*number* of tests does not correct for the *selection of the estimator*: a
threshold tuned to fit one lucky 18-day stretch produces a small p-value on the
data that tuned it, always. Fold stability puts the entire selection pipeline
inside the resample. A feature that only looks strong because its threshold was
fitted to one stretch cannot reproduce in the other four folds, because those
folds re-choose the threshold from their own data. This is why the tier is
driven by **F**, not by the interval — the interval says "given this exposure
definition, how precise is the estimate"; F says "does the exposure definition
itself survive contact with unseen time".

**Calibrate the rule set, don't trust it.** Run a **circular-shift permutation
null**: shift each exposure series by a uniformly random offset (200 draws),
which destroys the exposure–outcome relationship while *preserving the
autocorrelation of both series*, then run the full pipeline. Require
`P(a null feature reaches established) ≤ 0.05` and
`P(reaches emerging) ≤ 0.20`. If exceeded, raise F and the `|θ̂|` floors until
satisfied. This converts the tier rules from a plausible heuristic into a rule
with a measured false-discovery rate, and it is the number to publish when
someone asks "how do you know the top of this list isn't noise now".

**Failure mode.** With K = 5 folds over 92 days, each fold holds ~18 days, so a
feature exposed on 11 days will have folds with 1–3 exposed days and θ̂ₖ that is
almost pure noise. F is then near-random and the feature lands in `watching`
correctly but *uninformatively* — the UI must say "not enough exposed days per
time block", not "no effect found". Sparse-but-real effects are exactly the ones
that need §C.

### Layer 4 — local attribution for "how was today"

**Exact additivity by construction.** The prediction is nothing but the baseline
plus centred driver terms:

    ŷ(t) = b(t) + Σⱼ cⱼ(t)
    b(t) = ŷ_base(t)                                  [Layer 1, the "typical day"]
    cⱼ(t) = θ̂ⱼ · ( eⱼ(t) − ēⱼ )

where `eⱼ(t) ∈ {0,1}` is the binarised exposure and `ēⱼ` its **training-set
mean**. Centring is what makes the waterfall readable: `b(t)` is the prediction
for a day with the user's *average* exposures, so `Σcⱼ = 0` on an average day
and each `cⱼ` reads as "how today differed from your normal". The identity
`b + Σc = ŷ` holds exactly because there is nothing else in the model — no
non-linearity, no link function, no ensemble. There is no need for SHAP or any
attribution approximation, and that is a design choice, not a limitation: the
model is additive *so that* the explanation is exact.

Two implementation traps the UI must handle:

1. **Interaction rows are real rows.** A day with both short sleep and high
   histamine gets three contributions: two main effects plus the excess term.
   Omitting the excess row makes the waterfall under-predict bad days by exactly
   the amount that made the interaction interesting.
2. **Round with largest remainder.** Displayed contributions must sum to the
   displayed total at the displayed precision. Round each `cⱼ` to 1 dp, compute
   the residual rounding error, and push it onto the largest-|c| row. Otherwise
   the user does the arithmetic, it does not close, and the page loses all
   credibility in one glance.

**Residual.** `r(t) = overall(t) − ŷ(t)`. It is not an error message; it is
"everything the model does not have": unlogged exposures, mis-scored meals,
an argument at work, and genuine measurement noise. Interpret it against the
noise floor, not against zero:

| |r| | reading |
|---|---|
| ≤ 0.63 (1 σ_noise) | nothing to see — this is what the scale's own noise looks like |
| 0.63 – 1.54 | normal miss |
| > 1.54 (2 × σ_resid) | **unexplained** |

**Unexplained-day flagging.** Flag day t as unexplained if all three hold:

1. `|r(t)| > 2 × σ_resid` (= 1.54 points at σ_resid = 0.77)
2. **full input coverage** on t — sleep data present, ≥ 1 confirmed photo,
   check-in complete. A day missing inputs is a *different* and much less
   interesting finding; surface those separately as "couldn't score", never
   mixed into the unexplained list
3. optionally `r(t) < 0` for the "unexplained bad days" list; keep the positive
   tail too, in a second list — unexplained *good* days are where undiscovered
   protective levers live

Then cluster: ≥ 2 flagged days inside a 7-day window is reported as one
**episode**, not as separate rows, because they are almost certainly one cause.

**Why these are the highest-value output in the system.** Every `established`
driver is already known and already acted on; its marginal information is
decaying with every day of new data. The residual is the only place a *new*
lever can be discovered, and the model is a purpose-built detector for it — it
has already removed level, weekday, trend, sickness, and every known driver, so
what remains is concentrated evidence of something unmeasured. The mock's own
numbers make the case: the model captures 61% of the closable gap, and the
missing 39% is not spread evenly — it is piled into a handful of days. Mining
three unexplained days into one new tracker adds a whole new signal to the
matrix; refining an existing 0.31-point estimate to 0.34 adds nothing anyone can
act on. So the correct product behaviour is to convert the unexplained list into
a *tracker proposal*: for each flagged day list what was not logged, and rank
candidate new trackers by how many flagged days they would have covered.

**Failure mode.** Systematic model bias masquerades as unexplained days. If the
baseline lags a genuine regime change (new job, new medication), a whole run of
days is flagged and the app blames the user's logging when the fault is `L(t)`'s
21-day half-life. Guard: if > 15% of days in any 14-day window are flagged,
suppress the unexplained list and show "the model is re-learning your baseline"
instead.

### Interaction search without testing all pairs

Testing every pair is `C(95,2) × 3 lags = 13,395` tests — a multiplicity problem
two orders of magnitude worse than the one we started with. Instead, a
**restricted, pre-declared candidate set**:

1. Only features already promoted to `established` or `emerging` are eligible.
   In practice that is 6–8 features.
2. Only pairs on a declared mechanism list: `sleep × any food axis`,
   `alcohol × any food axis`, `sleep × alcohol`, `weather × sleep`,
   `any lever × any lever within the same category`. Cross-category pairs with
   no proposed mechanism are not tested.
3. Only pairs with **≥ 8 co-exposed days** and ≥ 2 co-exposed runs.

`C(8,2) = 28` pairs → mechanism filter leaves ~14 → co-exposure filter leaves
**8–12 tests**, capped at **15**. Against 13,395 that is a 1000× reduction in
multiplicity, and the surviving tests are the ones a clinician would have
proposed anyway. Interactions carry the stricter bar from Layer 3 and are capped
at `emerging` until co-exposed days ≥ 20 — with 11 co-exposed days the excess
term's own interval is ±0.6 points and cannot support a strong claim.

### The noise floor

`overall` is a single-item self-report on a 5-point scale; a meaningful part of
its day-to-day variance is measurement, not state. Estimate the irreducible SD
from the autocorrelation structure — no extra data collection required.

Model `overall` as a smooth AR(1) state plus white measurement noise. Then
`ρ₁ = φλ` and `ρ₂ = φ²λ` where `λ = Var(state)/Var(y)`, so

    λ̂ = ρ₁² / ρ₂        σ̂_noise = σ_y · √(1 − λ̂)        noiseFloor(MAE) = σ̂_noise · √(2/π)

Worked: `ρ₁ = 0.40, ρ₂ = 0.22 → λ̂ = 0.727 → σ̂_noise = 0.95·√0.273 = 0.50`,
which is the SD; as an MAE that is 0.40. (If the intended floor is MAE 0.50, the
corresponding SD is 0.63 — see the DATA.js note in D1: the two units must not be
mixed.) Cross-check with a second, assumption-light estimator: pool the
within-cell SD of `overall` across cells defined by (weekday × identical
binarised exposure vector) that contain ≥ 3 days. Two independent estimates that
agree within 0.1 is enough; if they disagree, report the larger.

**Why every number on the page must be shown against it.** σ_noise = 0.63 means
a 0.31-point effect is **0.49 σ_noise** — on any single day it is completely
invisible, and the user *will not feel it*. If the page shows "+0.31 points"
without that context, the user will look for the effect in tomorrow, fail to
find it, and conclude the page is wrong. The floor is also the hard ceiling on
model quality: at MAE 0.50, 43.5% of the outcome's variance is unexplainable by
anything, so "MAE 0.61" is 61% of the closable gap and not a mediocre 0.61.
And for treatment response: a 0.4-point delta on 30 baseline vs 45 during days
has SE = `0.95·√(1/30+1/45) = 0.23` → **±0.45 at 95%** — indistinguishable from
zero. Every treatment delta must carry that interval, or the panel is a
random-number generator with a clinical label on it.

---

## Part C — n-of-1 experiments

### Why observation cannot promote a `watching` finding

Two independent reasons, and the second is the one that matters.

**1. Precision improves as √n, and that is not fast enough.** Take the mock's
dairy driver: 46 exposed / 46 unexposed, θ̂ = −0.19, half-width 0.378.

| total usable days | half-width | interval |
|---|---|---|
| 92 (today) | 0.378 | [−0.57, 0.19] |
| 184 (+3 months) | 0.267 | [−0.46, 0.08] |
| 368 (+9 months) | 0.189 | [−0.38, 0.00] |

**A further year of observation still does not clear zero.** "Keep logging and
we'll know eventually" is arithmetically false for any effect under ~0.3 points.
Telling the user to wait is telling them to wait forever.

**2. More observation converges on the wrong number.** Exposure is
self-selected. The user takes magnesium on evenings when they are organised;
"organised" correlates with a good day through a dozen channels the matrix does
not contain. Adding days shrinks the interval **around the confounded estimate**,
not around the causal one. Precision without identification is worse than
imprecision, because a tight interval around a biased number reads as certainty.
This is why `watching` cannot be promoted by patience: patience fixes variance,
and the problem is bias.

### The design that can

**Block-randomised alternation.**

- **Unit of randomisation: a 4-day block.** Long enough for a lag-1 exposure and
  any short carryover to express; short enough to accumulate many blocks. Days
  are not randomised individually — daily switching is unblindable, unliveable,
  and maximally exposed to carryover.
- **Randomise within pairs of blocks.** Take blocks two at a time; one is ON and
  one is OFF, order decided by a coin flip. This *guarantees* balance against
  the slow trend — the dominant confounder (§A3) — instead of hoping for it. A
  plain 2-weeks-on / 2-weeks-off design has exactly one switch point and is
  therefore perfectly confounded with any drift across that point; it is not an
  experiment, it is a before/after with extra steps.
- **Carryover.** Either wash out the first day of each block (analyse days 2–4)
  or fit a one-day carryover term. Dropping day 1 costs 25% of the sample, so
  inflate the required block count by 1/0.75.
- **Exclusions decided in advance**: sick days out, travel days out. Deciding
  after the fact is the same p-hacking the observational pipeline was rebuilt to
  avoid.
- **Analysis**: the same Layer-1 residual, the same contrast-of-means estimator,
  the same block bootstrap. The *only* thing the experiment changes is that
  exposure is now assigned rather than chosen — which is the entire point.
- **Blinding.** Honest limitation, stated in the UI: a sleep floor cannot be
  blinded at all, and a supplement can only be blinded with a matched placebo
  the app cannot supply. So the estimate is an upper bound that includes
  expectancy. Say so on the result card rather than pretending otherwise.

**Pre-registration** — written before the first block, shown read-only
afterwards, and diffed against the actual analysis on the results card. It fixes:
outcome (`overall`), estimand (mean difference in points), the exposure
definition, the analysis and its covariates, the exclusion rules, the number of
blocks, and the direction of the hypothesis. Why it matters mechanically: with
n, analysis and stopping rule fixed in advance, the interval means what it says.
Without it, the experiment inherits the exact defect that made the observational
p-values meaningless (§Layer 3). **No peeking**: a fixed block count, or an
alpha-spending boundary if interim looks are unavoidable. "It's trending, let's
run a bit longer" is the single most effective way to manufacture a false
positive in an n-of-1 trial.

### Power against the user's own noise floor

Two-sided α = 0.05, power 80%, `z_{0.975} + z_{0.80} = 1.960 + 0.842 = 2.802`,
`(z_α + z_β)² = 7.849`.

    n_per_arm = 2 · (z_α + z_β)² · σ² · DEFF / δ²

    MDE       = (z_α + z_β) · σ · √DEFF · √(1/n₁ + 1/n₂)

`σ` is the SD of the **analysed** quantity — the Layer-1 residual, σ_resid =
0.77 — not the raw 0.95, because the experiment is analysed on residuals.
`DEFF ≈ 1.3` is the design effect for 4-day block alternation at residual
autocorrelation φ ≈ 0.4.

**Worked: detecting δ = 0.4 points against SD 0.95 (and against 0.77).**

| σ | DEFF | n per arm | total days | 4-day blocks |
|---|---|---|---|---|
| 0.95 (raw) | 1.0 | 88.5 → 89 | **178** | 45 |
| 0.95 (raw) | 1.3 | 115.1 → 116 | **232** | 58 |
| 0.77 (residualised) | 1.0 | 58.2 → 59 | **118** | 30 |
| 0.77 (residualised) | 1.3 | 75.6 → 76 | **152** | 38 |

So the honest answer is **~150 days / 38 alternating blocks** to detect 0.4
points at 80% power — five months. Residualisation is worth 80 days of the
user's life (232 → 152), which is the strongest practical argument for Layer 1
that exists. Adjacent values, same σ = 0.77 / DEFF = 1.3: δ = 0.35 → 198 days;
δ = 0.45 → 120 days; δ = 0.30 → 270 days.

**The reverse calculation, which is the one the UI must show.** A 21-day pilot
(10 ON / 11 OFF) has

    MDE = 2.802 · 0.77 · √1.3 · √(1/10 + 1/11) = 1.07 points

**~1.1 points, not 0.35.** A 2-weeks-vs-2-weeks design (14/14) gives MDE = 0.93.
Any experiment card that claims a small detectable effect from a three-week run
is off by a factor of three, and a reader with a calculator will find it. Every
proposed experiment must display its own MDE, computed from the user's own
measured σ, next to its duration — and if the MDE exceeds the observed θ̂, the
card should say "this design is too short to settle it" rather than offering a
Start button.

---

## Part D — coherence audit of DATA.js

Verdict: the **`model` block is sound**, the **`sleep_x_histamine` 2×2 is
exemplary** (every one of its differences reconciles to the digit), and the rest
of the file has **31 defects** — one flat contradiction, one systematic CI
convention error across all eight drivers, one systematic strip error across all
eight, six dose tables that do not reproduce their own stated effect, one
double-counted bin, one missing waterfall row, one tier-rule violation, and
three experiment power claims that are off by ~3×.

### D1. `model` — consistent; two labels to fix

| check | result |
|---|---|
| `skill` = (0.78 − 0.61)/(0.78 − 0.50) | 0.607 → **0.61 ✓ exact** |
| `mae 0.61` → RMSE = 0.61/√(2/π) = 0.765 → R² = 1 − 0.765²/0.95² | **0.352 ≈ 0.34 ✓** |
| `holdoutR2 0.34` → MSE = 0.9025·0.66 = 0.596 → RMSE 0.772 → MAE | **0.616 ≈ 0.61 ✓** |
| `baselineMae 0.78` vs the best possible *constant* predictor | constant = **0.800** (fitted P(1..5) = .02/.16/.34/.36/.12 at mean 3.40, SD 0.959). A mean+weekday+trend baseline beating a constant by 0.02 is exactly the right size ✓ |
| `noiseFloor 0.50` (MAE) → σ_noise 0.627 → 43.5% of Var(y) irreducible; explainable var 0.510, captured 0.318 | variance-space skill **0.624** vs MAE-space **0.607** — both round to 0.61–0.62 ✓ |
| `daysUsable 92` = `daysTotal 118` − 26 (the sleep-gap limit) | **✓ consistent** |
| `windowStart`→`windowEnd` inclusive | 119 days, 118 logged ✓ |
| `alcohol ≥ 2 units on 19 days` vs `alcohol_2u.exposedDays 19` | **✓** |

Fixes:

| # | field | old → new |
|---|---|---|
| 1 | `model` (new field) | add **`r2Basis: 'variance'`** — R² 0.34 is referenced to the outcome's own variance. The skill-score-vs-baseline convention would give **0.39**, and the UI must not imply that reading |
| 2 | `model` (new fields) | add **`holdoutRmse: 0.77`** and **`noiseSd: 0.63`**. Every driver CI in the file is a function of σ_resid; the file currently states only MAEs, so no reader can check a single interval. `noiseFloor 0.50` is an **MAE**; the matching SD is 0.63. Do not mix the units |
| 3 | `model.limits[2]` | `"Meal photos confirmed on 104 of 118 days"` → **`"Meal photos confirmed on 104 of 118 days — 12 of the 14 gaps fall on days already lost to missing sleep data"`**. Otherwise `daysUsable: 92` requires the 14 photo-less days to be a subset of the 26 sleep-less days, unstated. (Alternative: `daysUsable: 92` → **90**) |

### D2. `today` — the waterfall closes, but on the wrong numbers

`baseline 3.5 + (−0.5 −0.4 −0.4 +0.3) = 2.5 = predicted` ✓ sums exactly.
`residual = 2.0 − 2.5 = −0.5` ✓. But the individual contributions are not
`θ̂ⱼ · (eⱼ − ēⱼ)` for any θ̂ in the file, and **the interaction row is missing**
even though today has *both* short sleep and high histamine — the file's own
headline finding does not appear on the day it fires.

Correct centred contributions (`ēⱼ` = exposedDays/92):

| row | θ̂ | ē | c = θ̂(1 − ē) | display |
|---|---|---|---|---|
| Slept 6.1 h | −0.58 | 0.293 | −0.410 | **−0.4** |
| Histamine load high | −0.44 | 0.315 | −0.301 | **−0.3** |
| **Short sleep × high histamine** (new) | −0.32 excess | 0.120 | −0.282 | **−0.3** |
| Pressure dropped 8 hPa | −0.39 | 0.239 | −0.297 | **−0.3** |
| Magnesium glycinate | +0.31 | 0.446 | +0.172 | **+0.2** |

Sum at 1 dp = **−1.1**, and `3.5 − 1.1 = 2.4` exactly — the largest-remainder
rounding rule from Layer 4 closes on the nose. Cross-check: the three
sleep/histamine rows total −0.993, which equals the raw Both-vs-Neither contrast
−1.34 plus the average day's own expected penalty (0.44·0.315 + 0.58·0.293 +
0.32·0.120 = 0.347). The parameterisation is not double-counting.

| # | field | old → new |
|---|---|---|
| 4 | `today.contributions` | insert a 3rd row: **`{ label: 'Short sleep + high histamine', detail: 'the two together, beyond each alone', value: -0.3, kind: 'lever', category: 'interaction', driverId: 'sleep_x_histamine' }`** |
| 5 | `today.contributions[*].value` | `−0.5, −0.4, −0.4, +0.3` → **`−0.4, −0.3, −0.3, +0.2`** (plus the new −0.3) |
| 6 | `today.predicted` | `2.5` → **`2.4`** |
| 7 | `today.residual` | `−0.5` → **`−0.4`**; UX brief §1.2 copy `"model was 0.5 low"` → **`"0.4 low"`** |
| 8 | `today.band` | `[1.8, 3.2]` → **`[1.4, 3.4]`**, and add **`bandLevel: 80`**. ±0.7 at RMSE 0.77 is only a **63%** interval — too narrow to carry an "Explained" verdict. ±1.0 = 1.282·0.77 ≈ 80%. (A 50% band would be ±0.52 → [1.9, 2.9], which puts today's actual 2.0 on the edge and reads as *un*explained) |
| 9 | `today.recent[2026-07-18].predicted` | `2.4` → **`3.9`**. **Flat contradiction**: `unexplained` states the same date as `predicted 3.9, gap −1.9`. This is the defect a reader spots first, because the two arrays are three screens apart and disagree by 1.5 points |
| 10 | `today.recent` MAE | as written the 14 pairs give **MAE 0.314, RMSE 0.407** — the calibration strip is *twice as accurate* as the `0.61` chip printed directly above it. Rewrite the `predicted` column to **3.8, 3.5, 3.9, 4.1, 3.9, 2.9, 3.9, 3.6, 3.7, 3.5, 4.2, 3.3, 3.6, 2.4** → MAE **0.607** ✓ (vs `mae 0.61`), RMSE **0.751** ✓ (vs the 0.77 implied by `holdoutR2 0.34`) |

### D3. Every driver: dose tables, effects, CIs, strips

**`daysUsable` consistency.** `exposedDays + unexposedDays = 92` for all eight ✓.
But the `dose` bin `n`s sum to 92 for seven of eight — **`alcohol_2u` sums to
103**, because `'0 u'` was given n = 73, which is the *unexposed total*, so the
11 one-unit days are counted twice.

**Effect vs dose bin means.** Weighted contrast of the dose bins, versus the
stated `effect`:

| driver | implied from bins | stated | Δ |
|---|---|---|---|
| `alcohol_2u` | −0.769 | −0.72 | 0.05 |
| `sleep_short` | **−0.824** | −0.58 | **0.24** |
| `histamine_high` | −0.412 | −0.44 | 0.03 |
| `sleep_x_histamine` (Both − Neither) | −1.340 | −1.34 | **0 ✓** |
| `magnesium` | +0.310 | +0.31 | **0 ✓** |
| `pressure_drop` | −0.423 | −0.39 | 0.03 |
| `steps_low` | −0.262 | −0.26 | **0 ✓** |
| `dairy` | −0.190 | −0.19 | **0 ✓** |

**Grand-mean consistency.** Every dose table spans the same 92 days, so all eight
weighted grand means must be equal and equal to the mean of `overall` on those
days. They range **3.363 (interaction) → 3.469 (alcohol)** — a spread of 0.106,
larger than three of the effects on the page.

**Interaction cross-check — this part is right and must be preserved.** The 2×2
marginals reconcile perfectly: histamine days = 18 + 11 = **29** ✓ =
`histamine_high.exposedDays`; short-sleep days = 16 + 11 = **27** ✓ =
`sleep_short.exposedDays`; Neither = 92 − 29 − 16 = **47** ✓. And
`(A only − Neither) = −0.58` ✓, `(B only − Neither) = −0.44` ✓,
`additiveExpected −1.02` ✓, `Both − Neither = −1.34` ✓, `excess −0.32` ✓.
The 2×2 is therefore the **anchor**: `sleep_short.effect −0.58` and
`histamine_high.effect −0.44` are *partner-absent* effects, not raw marginals
(the raw marginals implied by the 2×2 are −0.77 and −0.63). Declare that
convention in the file, and make each dose table the **baseline-adjusted** means
that reproduce its own stated effect, pinned to grand mean 3.41. Solving
`μ_E − μ_U = θ̂` and `(n_E μ_E + n_U μ_U)/92 = 3.41` gives:

| # | field | old → new |
|---|---|---|
| 11 | `DATA.js` header comment | add: **dose means are baseline-adjusted; for the two interacting drivers the quoted effect is the effect with the other factor absent** |
| 12 | `alcohol_2u.dose[0].n` | `73` → **`62`** (fixes the 103 → 92 double-count) |
| 13 | `alcohol_2u.dose` means | `'0 u' 3.62` → **`3.57`**, `'1 u' 3.55` → **`3.50`** (2 u 3.00 and 3+ u 2.57 are already correct) → contrast −0.718, grand 3.411 ✓ |
| 14 | `sleep_short.dose` means | `2.55, 2.94, 3.61, 3.68, 3.60` → **`2.74, 3.13, 3.56, 3.63, 3.55`** → contrast −0.580, grand 3.410 ✓. Preserves the cliff (0.43 step at 6.5 h) and the flat top |
| 15 | `histamine_high.dose` means | `Low 3.58` → **`3.57`**, `High 3.14` → **`3.11`** (Moderate 3.52 unchanged) → contrast −0.437, grand 3.409 ✓ |
| 16 | `sleep_x_histamine.dose` means | `3.71, 3.27, 3.13, 2.37` → **`3.76, 3.32, 3.18, 2.42`** — add 0.05 to all four. Every difference is preserved exactly (−0.44 / −0.58 / −1.34 / excess −0.32); the level rises from 3.363 to 3.413 ✓ |
| 17 | `pressure_drop.dose` means | `3.55, 3.49, 3.10` → **`3.53, 3.47, 3.11`** → contrast −0.393, grand 3.409 ✓ |
| 18 | `steps_low.dose` means | `3.21, 3.44, 3.52` → **`3.22, 3.45, 3.53`** → contrast −0.262, grand 3.414 ✓ |
| 19 | `magnesium.dose`, `dairy.dose` | **no change** — both already reconcile exactly and sit at grand mean 3.408 / 3.405 |

After 12–18, all eight grand means land in **3.405–3.414** ✓.

**Confidence intervals — eight different implied SDs.** Back-solving
`σ = hw / (1.96·√(1/n₁+1/n₂))` from the stated intervals:

| driver | n₁/n₂ | stated hw | implied σ |
|---|---|---|---|
| `sleep_short` | 27/65 | 0.28 | **0.624** |
| `alcohol_2u` | 19/73 | 0.33 | 0.654 |
| `magnesium` | 41/51 | 0.29 | 0.705 |
| `pressure_drop` | 22/70 | 0.35 | 0.731 |
| `steps_low` | 24/68 | 0.35 | 0.752 |
| `histamine_high` | 29/63 | 0.35 | 0.796 |
| `sleep_x_histamine` | 11/81 | 0.54 | 0.858 |
| `dairy` | 46/46 | 0.39 | **0.954** |

A 53% spread in the assumed noise, with no pattern — the intervals were written
by eye, not computed. Recompute all eight at **one** convention:
`hw = 1.96 · σ_resid · √DEFF · √(1/n₁ + 1/n₂)` with `σ_resid = 0.77` (the
model's own holdout RMSE, implied by `mae 0.61`) and `√DEFF = 1.2`
(DEFF = 1.44 — block-bootstrap inflation for autocorrelated, clustered
observational exposure), i.e. multiplier **1.96 × 0.77 × 1.2 = 1.811**:

| # | driver | `ci` old → new |
|---|---|---|
| 20 | `alcohol_2u` | `[−1.05, −0.39]` → **`[−1.19, −0.25]`** |
| 21 | `sleep_short` | `[−0.86, −0.30]` → **`[−1.00, −0.17]`** |
| 22 | `histamine_high` | `[−0.79, −0.09]` → **`[−0.85, −0.03]`** |
| 23 | `sleep_x_histamine` | `[−1.88, −0.80]` → **`[−1.92, −0.76]`** |
| 24 | `magnesium` | `[0.02, 0.60]` → **`[−0.07, 0.69]`** |
| 25 | `pressure_drop` | `[−0.74, −0.04]` → **`[−0.83, 0.05]`** |
| 26 | `steps_low` | `[−0.61, 0.09]` → **`[−0.69, 0.17]`** |
| — | `dairy` | `[−0.58, 0.20]` → `[−0.57, 0.19]` — **already correct**, the one interval computed on a defensible σ |

Two knock-on consequences, both survivable:

| # | field | old → new |
|---|---|---|
| 27 | `magnesium.plain` | `"The interval only just clears zero — real, but small."` → **`"The interval only just touches zero — real, but small."`** The corrected CI includes 0 by 0.07, which still satisfies the file's own `emerging` rule ("CI clear of zero **or barely touching**") and my Layer-3 rule (zero-side bound within 0.10). It will correctly show the `crosses zero` pill |
| 28 | `pressure_drop` | corrected CI `[−0.83, 0.05]` now touches zero. **Keep `tier: 'emerging'`** (zero-side bound 0.05 < 0.10) and let the card show the `crosses zero` pill. This is the honest state and it makes the tier explanation legible rather than undermining it |

**Tier rule violation.**

| # | field | old → new |
|---|---|---|
| 29 | `histamine_high.folds` | `4` → **`3`**. At 4/5 folds, CI excluding zero, and 29 exposed days it satisfies the file's own `established` definition ("≥4/5 folds, CI clear of zero, ≥15 exposed days") while being labelled `emerging`. Either drop the fold count or promote the tier — dropping to 3 is right, since the copy ("Worth an experiment") and the `shapeNote` both describe an unsettled finding. `sleep_x_histamine` at 4/5 folds is *correctly* `emerging`: its 11 exposed days fail the ≥15 rule |

**Day strips.** Two independent errors, both visible in the driver dialog the
brief calls "the honest counterweight to any modelled number".

*Length.* `strip.exposed` matches `exposedDays` for all eight ✓. `strip.unexposed`
matches `unexposedDays` for only two (`magnesium` 51 ✓, `dairy` 46 ✓); the other
six are truncated to **25** with no field saying so, while the brief labels that
row `Other days (73)`. Drawing 25 squares under a "(73)" label is a visible lie.

*Mean.* Every strip's mean must equal its dose-table mean. Currently every strip
shows **roughly double** the stated effect:

| # | driver | strip-implied effect | stated | exposed mean → target | unexposed mean → target | unexposed length → |
|---|---|---|---|---|---|---|
| 30a | `alcohol_2u` | −1.20 | −0.72 | 2.68 → **2.84** | 3.88 → **3.56** | 25 → **73** |
| 30b | `sleep_short` | −1.22 | −0.58 | 2.74 → **3.00** | 3.96 → **3.58** | 25 → **65** |
| 30c | `histamine_high` | −0.80 | −0.44 | 3.00 → **3.11** | 3.80 → **3.55** | 25 → **63** |
| 30d | `sleep_x_histamine` | −1.48 | −1.34 | 2.36 → **2.42** | 3.84 → **3.55** | 25 → **81** |
| 30e | `magnesium` | +0.58 | +0.31 | 3.78 → **3.58** | 3.20 → **3.27** | 51 ✓ |
| 30f | `pressure_drop` | −0.88 | −0.39 | 3.00 → **3.11** | 3.88 → **3.50** | 25 → **70** |
| 30g | `steps_low` | −0.56 | −0.26 | 3.13 → **3.22** | 3.68 → **3.48** | 25 → **68** |
| 30h | `dairy` | −0.24 | −0.19 | 3.22 → **3.32** | 3.46 → **3.51** | 46 ✓ |

Regeneration rule: integers in 1–5, length = the day count, mean within ±0.01 of
the target, and the value histogram consistent with the fitted `overall`
distribution shifted to that mean — do not put a 5 in a strip whose mean is 2.42.

**Minor driver fixes.**

| # | field | old → new |
|---|---|---|
| 31a | `steps_low.shape` | `'linear'` → **`'threshold'`**. The label ("Under 3,000 steps"), the dose bins and the effect are all a `<3k` contrast; nothing in the record is a slope. Under the Layer-3 rule a `linear` shape would have to be a bottom-vs-top-tertile contrast (n ≈ 31, effect −0.31), which is not what is stated |
| 31b | `histamine_high.plain` / `.shapeNote` | `"heaviest-histamine quarter"` / `"top quartile"` → **`"heaviest third"`** / **`"top third"`**. 29/92 = 31.5%, not 25% |
| 31c | `sleep_short.adjusted` | `['weekday','slow trend','sick days']` → add **`'alcohol'`**. Alcohol is adjusted for in the histamine and interaction models; short sleep and drinking co-occur at least as strongly, so omitting it there is inconsistent |

### D4. `experiments` — all three power claims are ~3× optimistic

MDE at 80% power, α = 0.05 two-sided, σ_resid = 0.77, DEFF = 1.3:

| stated design | days | actual MDE | claimed |
|---|---|---|---|
| magnesium, 21 days | 10/11 | **1.07** | 0.35 |
| dairy, 3 weeks | 10/11 | **1.07** | 0.40 |
| sleep floor, 2 wk vs 2 wk | 14/14 | **0.93** | 0.45 |

| # | field | old → new |
|---|---|---|
| 32 | `experiments.active[exp_mag].total` | `21` → **`152`** (38 four-day blocks — the length that actually detects 0.35–0.40 points) |
| 33 | `experiments.active[exp_mag].readout` | `"Too early to read. Powered to detect 0.35 points."` → **`"Too early to read. Powered to detect 0.35 points over the full 152 days. At day 11 the design can only see about 1.1 points."`** |
| 34 | `experiments.proposed[exp_dairy].design` | `"Alternate 4-day blocks, 3 weeks"` → **`"Alternate 4-day blocks, 38 blocks (152 days)"`** |
| 35 | `experiments.proposed[exp_dairy].power` | `"Detects 0.4 points against your 0.95-point day-to-day noise"` → **`"Detects 0.4 points at 80% power over 152 days, against your 0.63-point noise floor (0.95 raw day-to-day SD)."`** 0.95 is the *total* SD, not the noise floor — the copy conflates them, and it is the one number the whole power argument rests on |
| 36 | `experiments.proposed[exp_sleep].design` | `"Two weeks with an alarm-enforced floor vs two without"` → **`"Randomised 4-day blocks, 30 blocks (120 days)"`**. A single 2-on/2-off switch has exactly one changeover and is perfectly confounded with the slow trend |
| 37 | `experiments.proposed[exp_sleep].power` | `"Detects 0.45 points"` → **`"Detects 0.45 points over 120 days. Two weeks vs two weeks detects only about 0.9 points."`** |

### D5. `mirrors`, `unexplained`, `trends`

| # | field | old → new |
|---|---|---|
| 38 | UX brief §2.4 heading / `mirrors` | `"SET ASIDE — 4 same-day self-reports"` → **`"SET ASIDE — 4 same-day mirrors (3 self-reported, 1 device)"`**. `Resting HR (elevated)` is a device metric, not a self-report; its own note ("Moves with the day rather than ahead of it") is already correct — only the group label is wrong |
| 39 | `unexplainedPrompt.body` | `"All three landed on days with no afternoon meal logged."` → **`"Two of the three landed on days with no afternoon meal logged."`** Only `2026-07-06` says so; the other two notes say "Travel day?" and "Followed two unexplained days" |
| 40 | `trends[overall].avg7` | `3.1` → **`3.6`**. Trailing-7 of `today.recent` actuals (3,4,4,5,4,3,2) = **3.571**. Every other series in `trends` satisfies "last spark value == avg7"; `overall` is the only one that breaks, and it breaks against `today.recent` |
| 41 | `trends[overall].spark` tail | `…3.0, 3.2, 3.1` → **`…3.3, 3.4, 3.6`**, so the series still ends at `avg7` per the file's own convention |
| 42 | `trends[*].delta30` definition | keep `overall: −0.3`, but document that `delta30` = **rolling-7 now − rolling-7 30 days ago** (3.6 vs 3.9). The current backend computes `current − rolling_30d_ago`, which with `current: 2.0` would imply a 30-day-ago rolling average of 2.3 — contradicted by the spark, which starts at 3.4 |
| 43 | UX brief §2.1 count | `"6 levers · 1 context"` → **`"7 levers · 1 context"`**. Counting `kind` across the eight drivers: 7 levers (alcohol, sleep, histamine, interaction, magnesium, steps, dairy) and 1 context (pressure) |

Verified correct, no change needed: all four weekdays (`2026-07-25` and
`2026-07-18` Saturday, `2026-07-06` Monday, `2026-06-28` Sunday ✓); all three
`unexplained` gaps (`actual − predicted` ✓ to the digit) and all three exceed the
Layer-4 threshold of 2·σ_resid = 1.54 ✓; every `driverId` in
`today.contributions` resolves to a real driver id ✓; `meta.outcomeSd 0.95` and
`outcomeMean 3.41` are mutually consistent with an integer 1–5 distribution ✓.

