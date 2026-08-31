# Feature Matrix Column Dictionary

Schema version: **4** (`X-Feature-Schema-Version: 4`)

One row per calendar date in the requested range. A date with no entry still produces
a row — entry-sourced and dietary columns are `null` (not zero) for missing days.
Health metric and weather columns are independently `null` when those sources have no
data for the date.

---

## Date

| Column | Type | Source | Description | Nullable |
|--------|------|--------|-------------|----------|
| `date` | string (ISO 8601, `YYYY-MM-DD`) | — | Calendar date for the row | Never |

---

## Entry fields

Populated when the user submitted a check-in for that date. All `null` when no entry exists.

| Column | Type | Source | Description | Nullable |
|--------|------|--------|-------------|----------|
| `overall` | int (1–3) | `entries.overall` | Overall day score: 1=Very Poor, 2=Standard, 3=Very Good | Yes |
| `bloating` | int (0–3) | `entries.bloating` | Bloating severity: 0=None, 1=Mild, 2=Moderate, 3=Severe | Yes |
| `joint_pain` | int (0–3) | `entries.joint_pain` | Joint pain severity: 0=None, 1=Mild, 2=Moderate, 3=Severe | Yes |
| `neuro` | int (-1–1) | `entries.neuro` | Neurological state: -1=Worse, 0=Baseline, 1=Better | Yes |
| `sleep_quality` | int (1–3) | `entries.sleep_quality` | Subjective sleep quality: 1=Poor, 2=OK, 3=Good | Yes |
| `stress` | int (1–3) | `entries.stress` | Stress level: 1=Low, 2=Medium, 3=High | Yes |
| `diet_risk` | string | `entries.diet_risk` | User's dietary risk assessment for the day (free text category) | Yes |
| `sick` | bool | `entries.sick` | Whether the user reported being sick | Yes |
| `hot_shower` | bool | `entries.hot_shower` | Whether the user took a full-body hot shower | Yes |
| `stool_status` | string | `entries.stool_status` | Stool outcome: `normal`, `abnormal`, `none` | Yes |
| `bristol_type` | int (1–7) | `entries.bristol_type` | Bristol Stool Scale type (present when `stool_status=abnormal`) | Yes |
| `period_of_day` | string | `entries.period_of_day` | When the check-in was submitted: `morning`, `afternoon`, `evening`, `night` | Yes |
| `schema_version` | int | `entries.schema_version` | Entry schema version (1=legacy coarse stool, 2=bristol+status) | Yes |

---

## Health metric fields (`hm_` prefix)

Populated from Apple Health auto-export via `/api/v1/health-metrics/import`. All `null` when no metric record exists for the date.

| Column | Type | Source | Description | Nullable |
|--------|------|--------|-------------|----------|
| `hm_hrv_mean` | float (ms) | `health_metrics.hrv_mean` | Mean heart rate variability | Yes |
| `hm_hrv_std` | float (ms) | `health_metrics.hrv_std` | Standard deviation of HRV | Yes |
| `hm_resting_hr` | float (bpm) | `health_metrics.resting_hr` | Resting heart rate | Yes |
| `hm_sleep_hours` | float (h) | `health_metrics.sleep_hours` | Total sleep duration | Yes |
| `hm_sleep_deep_min` | float (min) | `health_metrics.sleep_deep_min` | Deep sleep duration | Yes |
| `hm_sleep_rem_min` | float (min) | `health_metrics.sleep_rem_min` | REM sleep duration | Yes |
| `hm_sleep_core_min` | float (min) | `health_metrics.sleep_core_min` | Core (light) sleep duration | Yes |
| `hm_sleep_awake_min` | float (min) | `health_metrics.sleep_awake_min` | Time awake during sleep window | Yes |
| `hm_sleep_deep_pct` | float (%) | `health_metrics.sleep_deep_pct` | Deep sleep as % of total sleep | Yes |
| `hm_sleep_rem_pct` | float (%) | `health_metrics.sleep_rem_pct` | REM sleep as % of total sleep | Yes |
| `hm_sleep_efficiency` | float (%) | `health_metrics.sleep_efficiency` | Sleep efficiency (time asleep / time in bed) | Yes |
| `hm_sleep_start` | string (ISO datetime) | `health_metrics.sleep_start` | Bedtime timestamp | Yes |
| `hm_sleep_end` | string (ISO datetime) | `health_metrics.sleep_end` | Wake time timestamp | Yes |
| `hm_steps` | int | `health_metrics.steps` | Step count | Yes |
| `hm_active_minutes` | float (kcal) | `health_metrics.active_minutes` | Active energy burned (stored as kcal despite the column name) | Yes |
| `hm_spo2` | float (%) | `health_metrics.spo2` | Blood oxygen saturation | Yes |
| `hm_wrist_temp_deviation` | float (°C) | `health_metrics.wrist_temp_deviation` | Wrist skin temperature deviation from baseline | Yes |

---

## Weather fields (`wx_` prefix)

Aggregated from the daily Open-Meteo snapshot stored on check-in. All `null` when no readings exist for the date.
`wx_pressure_delta` is additionally `null` when no readings exist for the prior day.

| Column | Type | Source | Description | Nullable |
|--------|------|--------|-------------|----------|
| `wx_temp_mean` | float (°C) | `weather_readings` | Mean temperature across hourly readings | Yes |
| `wx_temp_min` | float (°C) | `weather_readings` | Minimum temperature | Yes |
| `wx_temp_max` | float (°C) | `weather_readings` | Maximum temperature | Yes |
| `wx_humidity_mean` | float (%) | `weather_readings` | Mean relative humidity | Yes |
| `wx_pressure_mean` | float (hPa) | `weather_readings` | Mean atmospheric pressure | Yes |
| `wx_pressure_delta` | float (hPa) | `weather_readings` | Change in mean pressure vs prior day (positive = rising) | Yes |
| `wx_condition` | string | `weather_readings.weather_main` | Modal weather condition label for the day (e.g. `Clouds`, `Rain`, `Clear`) | Yes |

---

## Dietary load fields

Aggregated from confirmed photo analyses (`photo_analyses.status = 'confirmed'`) and their
visible ingredients (`photo_ingredients.visible = true`). All `null` when no entry exists for
the date. Zero when an entry exists but has no confirmed photos.

| Column | Type | Source | Description | Nullable |
|--------|------|--------|-------------|----------|
| `histamine_load_sum` | int | `photo_ingredients.histamine_score` | Sum of histamine scores across visible ingredients (0–N) | Yes |
| `histamine_load_max` | int | `photo_ingredients.histamine_score` | Maximum single-ingredient histamine score | Yes |
| `fodmap_oligos_sum` | int | `photo_ingredients.fodmap_oligos` | Sum of oligo FODMAP levels (high=2, moderate=1, none=0) | Yes |
| `fodmap_fructose_sum` | int | `photo_ingredients.fodmap_fructose` | Sum of fructose FODMAP levels | Yes |
| `fodmap_polyols_sum` | int | `photo_ingredients.fodmap_polyols` | Sum of polyol FODMAP levels | Yes |
| `fodmap_lactose_sum` | int | `photo_ingredients.fodmap_lactose` | Sum of lactose FODMAP levels | Yes |
| `gluten_exposure` | bool | `photo_ingredients.contains_gluten` | Any visible ingredient contains gluten | Yes |
| `dairy_exposure` | bool | `photo_ingredients.contains_dairy` | Any visible ingredient contains dairy | Yes |
| `photo_count` | int | `photo_analyses` | Number of confirmed photo analyses for the day | Yes |
| `ingredient_count` | int | `photo_ingredients` | Total visible ingredient count across confirmed photos | Yes |

---

## Supplement columns (`supp_` prefix, dynamic)

One boolean column per supplement that has ever been taken (i.e. `supplement_catalog.first_used_at IS NOT NULL`),
ordered alphabetically by key. The full column list is returned in the `columns` array of every response
so consumers can discover the schema without hardcoding it.

| Column pattern | Type | Source | Description | Nullable |
|----------------|------|--------|-------------|----------|
| `supp_{key}` | bool | `entries.supplements` (CSV field) | `true` if the supplement was taken on that date, `false` if not, `null` if no entry | Yes |

Example columns: `supp_allicin`, `supp_creatine`, `supp_dao`, `supp_fish_oil`, `supp_magnesium`, etc.

---

## Versioning

The `X-Feature-Schema-Version` response header carries the integer schema version.
When new static columns are added or semantics change, this version is incremented.
The `columns` array in the JSON response always reflects the exact column order for that
version, including dynamic supplement columns.
