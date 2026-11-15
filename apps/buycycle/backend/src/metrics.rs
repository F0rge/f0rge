//! Legacy-comparable semantics, expressed once for API responses and collection candidates.
use crate::contracts::{Kind, Listing, NextUp, PricePoint};
use chrono::{DateTime, Duration, NaiveDate, TimeZone, Utc};
use chrono_tz::Europe::Luxembourg;
use regex::Regex;
use serde_json::Value;
use std::collections::{BTreeMap, HashMap, HashSet};
use std::sync::LazyLock;

const STOPB: &str = "road gravel bike bicycle disc disk di2 etap axs ultegra dura ace dura-ace 105 grx sram shimano campagnolo rival force red apex tiagra sora claris super record chorus centaur ekar potenza edition team limited the and with carbon alu aluminium aluminum frameset complete new mechanical hydraulic hrd ltd 1x 2x 11 12 speed 12s 11s rim custom size cm";
const STOPW: &str = "complete wheels wheel wheelset wheelsets laufradsatz laufräder laufrad set pair paire de roues ruote coppia par ruedas disc disk disco brake brakes rim rims carbon carbone carbono alloy aluminium aluminum alu tubeless tubular clincher tle tl cl centerlock center centre lock 6-bolt 6 bolt 700c 700 28 29 27.5 650b 26 zoll inch mm thru axle ta qr shimano sram hg xdr xd 11s 12s 11 12 speed road gravel mtb new with and for the front rear tyres tires tyre tire freehub hub hubs body only";
static YEAR: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\b(19|20)\d\d\b").unwrap());
static MILLIMETRES: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(\d+)\s*mm\b").unwrap());
static WORDS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[a-z0-9.+-]+").unwrap());
static BIKE_STOP: LazyLock<HashSet<&str>> = LazyLock::new(|| STOPB.split_whitespace().collect());
static WHEEL_STOP: LazyLock<HashSet<&str>> = LazyLock::new(|| STOPW.split_whitespace().collect());
pub fn model_key(kind: &Kind, name: &str, brand: &str) -> String {
    normalized_model(kind, name, &brand_patterns(brand))
}
fn brand_patterns(brand: &str) -> Vec<Regex> {
    brand
        .to_lowercase()
        .split_whitespace()
        .map(|word| {
            Regex::new(&format!(
                r"(?P<a>^|[^a-z0-9]){}(?P<b>[^a-z0-9]|$)",
                regex::escape(word)
            ))
            .expect("escaped brand")
        })
        .collect()
}
fn normalized_model(kind: &Kind, name: &str, patterns: &[Regex]) -> String {
    let mut name = format!(" {} ", name.to_lowercase());
    for re in patterns {
        // A consumed separator can hide an adjacent repeated brand in one pass.
        // Iterate to match Python's zero-width boundary replacement semantics.
        while re.is_match(&name) {
            name = re.replace_all(&name, "${a} ${b}").into_owned();
        }
    }
    name = YEAR.replace_all(&name, " ").into_owned();
    name = MILLIMETRES.replace_all(&name, "$1").into_owned();
    let stop = if *kind == Kind::Wheels {
        &*WHEEL_STOP
    } else {
        &*BIKE_STOP
    };
    WORDS
        .find_iter(&name)
        .map(|x| x.as_str())
        .filter(|x| !stop.contains(x) && !x.trim_matches(['.', '-', '+']).is_empty())
        .take(if *kind == Kind::Wheels { 3 } else { 2 })
        .collect::<Vec<_>>()
        .join(" ")
}
pub fn round(value: f64, places: i32) -> f64 {
    let factor = 10_f64.powi(places);
    (value * factor).round_ties_even() / factor
}
fn median(values: &[f64]) -> Option<f64> {
    if values.is_empty() {
        return None;
    }
    let mut v = values.to_vec();
    v.sort_by(f64::total_cmp);
    Some(if v.len().is_multiple_of(2) {
        (v[v.len() / 2 - 1] + v[v.len() / 2]) / 2.0
    } else {
        v[v.len() / 2]
    })
}
fn day(value: &str) -> Option<NaiveDate> {
    NaiveDate::parse_from_str(value.get(..10)?, "%Y-%m-%d").ok()
}
fn midnight(value: &str) -> Option<f64> {
    let d = day(value)?.and_hms_opt(0, 0, 0)?;
    Some(Luxembourg.from_local_datetime(&d).earliest()?.timestamp() as f64)
}
pub fn string(row: &Value, key: &str) -> String {
    row.get(key)
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_owned()
}
pub fn number(row: &Value, key: &str) -> Option<f64> {
    row.get(key)
        .and_then(Value::as_f64)
        .filter(|v| v.is_finite())
}
fn optional(row: &Value, key: &str) -> Option<String> {
    row.get(key)
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty())
        .map(str::to_owned)
}
fn country_km(country: &str) -> Option<f64> {
    Some(match country {
        "Luxembourg" => 0.,
        "Belgium" => 210.,
        "France" => 380.,
        "Germany" => 350.,
        "Netherlands" => 380.,
        "Switzerland" => 420.,
        "Austria" => 800.,
        "Italy" => 900.,
        "Spain" => 1500.,
        "Portugal" => 2000.,
        "Czech Republic" => 730.,
        "Poland" => 1100.,
        "Slovenia" => 1000.,
        "Slovakia" => 1100.,
        "Denmark" => 900.,
        "Ireland" => 1300.,
        "United Kingdom" => 750.,
        "Hungary" => 1200.,
        "Croatia" => 1200.,
        "Sweden" => 1500.,
        "Finland" => 2300.,
        "Greece" => 2500.,
        "Romania" => 1900.,
        "Bulgaria" => 2100.,
        "Norway" => 1500.,
        "Estonia" => 2000.,
        "Latvia" => 1800.,
        "Lithuania" => 1500.,
        _ => return None,
    })
}
#[derive(Clone)]
struct Row<'a> {
    raw: &'a Value,
    detail: &'a Value,
    id: &'a str,
    year: Option<f64>,
    group: String,
    model: String,
    brake: String,
    material: String,
    days: f64,
}
fn comparable(a: &Row<'_>, b: &Row<'_>, kind: &Kind) -> bool {
    a.id != b.id
        && (*kind == Kind::Wheels || a.year.zip(b.year).is_none_or(|(x, y)| (x - y).abs() <= 1.))
}
fn days_listed(raw: &Value, now: DateTime<Utc>) -> f64 {
    let start = number(raw, "activated_at")
        .filter(|v| *v != 0.)
        .or_else(|| midnight(&string(raw, "first_seen")))
        .unwrap_or(now.timestamp() as f64);
    let end = optional(raw, "gone_at")
        .as_deref()
        .and_then(midnight)
        .unwrap_or(now.timestamp() as f64);
    (end - start) / 86400.
}
struct HistoryIndex(HashMap<String, Vec<PricePoint>>);
impl HistoryIndex {
    fn push(&mut self, row: &Value) {
        if let Some(price) = number(row, "price") {
            self.0
                .entry(string(row, "id"))
                .or_default()
                .push(PricePoint {
                    day: string(row, "day"),
                    price,
                });
        }
    }
    fn finish(mut self) -> Self {
        for points in self.0.values_mut() {
            points.sort_by(|a, b| a.day.cmp(&b.day));
        }
        self
    }
    fn values(rows: &[Value]) -> Self {
        let mut index = Self(HashMap::new());
        for row in rows {
            index.push(row);
        }
        index.finish()
    }
    fn raw(rows: Vec<Box<serde_json::value::RawValue>>) -> Self {
        let mut index = Self(HashMap::new());
        for row in rows {
            // RawValue is validated JSON from PostgreSQL or serde. Materialize
            // exactly one row, then release it instead of building a full tree.
            let row = serde_json::from_str(row.get()).expect("validated history JSON");
            index.push(&row);
        }
        index.finish()
    }
}

/// All observations are retained; output includes disappeared rows for history and explicit UI filtering.
pub fn build(
    kind: Kind,
    raw_rows: Vec<Value>,
    details: Vec<Value>,
    history: Vec<Value>,
    countries: Vec<Value>,
    now: DateTime<Utc>,
) -> Vec<Listing> {
    let indexed = HistoryIndex::values(&history);
    drop(history);
    build_indexed(kind, &raw_rows, &details, &indexed, &countries, now)
}

pub fn build_raw(
    kind: Kind,
    raw_rows: Vec<Value>,
    details: Vec<Value>,
    history: Vec<Box<serde_json::value::RawValue>>,
    countries: Vec<Value>,
    now: DateTime<Utc>,
) -> Vec<Listing> {
    let indexed = HistoryIndex::raw(history);
    build_indexed(kind, &raw_rows, &details, &indexed, &countries, now)
}

fn build_indexed(
    kind: Kind,
    raw_rows: &[Value],
    details: &[Value],
    history: &HistoryIndex,
    countries: &[Value],
    now: DateTime<Utc>,
) -> Vec<Listing> {
    let details: HashMap<String, &Value> = details.iter().map(|d| (string(d, "id"), d)).collect();
    let countries: HashMap<i64, String> = countries
        .iter()
        .filter_map(|c| Some((c.get("cid")?.as_i64()?, string(c, "country"))))
        .collect();
    let mut brands = HashMap::new();
    let rows: Vec<Row<'_>> = raw_rows
        .iter()
        .filter(|r| string(r, "kind") == kind.as_str())
        .filter_map(|raw| {
            if number(raw, "price").is_none_or(|price| price <= 0.) {
                return None;
            }
            let spec = raw
                .get("spec")
                .and_then(Value::as_str)
                .and_then(|s| serde_json::from_str::<Value>(s).ok())
                .unwrap_or(Value::Null);
            let s = spec.get("spec").unwrap_or(&Value::Null);
            if kind == Kind::Wheels
                && s.get("wheel-type")
                    .and_then(Value::as_str)
                    .is_some_and(|v| v != "1372")
            {
                return None;
            }
            let brand = string(raw, "brand");
            let patterns = brands
                .entry(brand.to_lowercase())
                .or_insert_with(|| brand_patterns(&brand));
            let model = normalized_model(&kind, &string(raw, "name"), patterns);
            let brake = if kind == Kind::Wheels {
                match s.get("complete-wheels-brakes-type").and_then(Value::as_str) {
                    Some("1430") => "disc",
                    Some("1431") => "rim",
                    _ => "",
                }
            } else {
                ""
            }
            .to_owned();
            let material = if kind == Kind::Wheels {
                match s.get("rim-material").and_then(Value::as_str) {
                    Some("1433") => "carbon",
                    Some("1432") => "aluminium",
                    Some("1434") => "steel",
                    _ => "",
                }
            } else {
                ""
            }
            .to_owned();
            let detail = details
                .get(&string(raw, "id"))
                .copied()
                .unwrap_or(&Value::Null);
            let days = days_listed(raw, now);
            Some(Row {
                raw,
                detail,
                id: raw.get("id").and_then(Value::as_str).unwrap_or(""),
                year: number(raw, "year"),
                group: format!(
                    "{}\0{}\0{}\0{}",
                    brand.to_lowercase(),
                    model,
                    brake,
                    material
                ),
                model,
                brake,
                material,
                days,
            })
        })
        .collect();
    let mut groups: BTreeMap<String, Vec<&Row<'_>>> = BTreeMap::new();
    for row in &rows {
        if !row.model.is_empty() {
            groups.entry(row.group.clone()).or_default().push(row)
        }
    }
    let today = now.with_timezone(&Luxembourg).date_naive();
    let cut = today - Duration::days(30);
    let earliest = rows
        .iter()
        .filter_map(|r| day(&string(r.raw, "first_seen")))
        .min();
    rows.iter()
        .map(|row| {
            let price =
                number(row.raw, "price").expect("priced rows are validated before grouping");
            let id = string(row.raw, "id");
            let cohort: Vec<&Row<'_>> = groups
                .get(&row.group)
                .into_iter()
                .flatten()
                .copied()
                .filter(|other| comparable(row, other, &kind))
                .collect();
            let comps: Vec<&Row<'_>> = cohort
                .iter()
                .copied()
                .filter(|r| optional(r.raw, "gone_at").is_none())
                .collect();
            let prices: Vec<f64> = comps
                .iter()
                .filter_map(|r| number(r.raw, "price"))
                .collect();
            let reference = if prices.len() >= 3 {
                median(&prices)
            } else {
                None
            };
            let average = if prices.is_empty() {
                None
            } else {
                Some(prices.iter().sum::<f64>() / prices.len() as f64)
            };
            let z = if prices.len() >= 2 {
                let mean = average.unwrap();
                let sd = (prices.iter().map(|p| (p - mean).powi(2)).sum::<f64>()
                    / prices.len() as f64)
                    .sqrt();
                (sd > 0.).then(|| round((price - mean) / sd, 2))
            } else {
                None
            };
            let dispersion = if prices.len() >= 4 {
                let mut v = prices.clone();
                v.sort_by(f64::total_cmp);
                let quantile = |q: f64| {
                    let p = (v.len() + 1) as f64 * q;
                    let i = (p.floor() as usize).clamp(1, v.len() - 1);
                    v[i - 1] + (v[i] - v[i - 1]) * (p - i as f64)
                };
                reference
                    .filter(|v| *v > 0.)
                    .map(|r| round((quantile(0.75) - quantile(0.25)) / r * 100., 0))
            } else {
                None
            };
            let confidence = if reference.is_none() {
                "none"
            } else if prices.len() >= 10 && dispersion.unwrap_or(0.) <= 40. {
                "high"
            } else if prices.len() >= 5 {
                "medium"
            } else {
                "low"
            };
            let discount = reference
                .filter(|r| *r > 0.)
                .map(|r| round((r - price) / r * 100., 1));
            let h = history.0.get(&id).map(Vec::as_slice).unwrap_or_default();
            let original = number(row.raw, "original_price")
                .filter(|p| *p != 0.)
                .unwrap_or(price);
            let cut_per_day = if h.is_empty() {
                None
            } else {
                let highest = h.iter().map(|h| h.price).fold(original, f64::max);
                let delta = highest - price;
                if delta <= 0. {
                    Some(0.)
                } else if round(row.days, 1) <= 0. {
                    None
                } else {
                    Some(round(delta / round(row.days, 1), 2))
                }
            };
            let mature: Vec<&Row<'_>> = cohort
                .iter()
                .copied()
                .filter(|r| day(&string(r.raw, "first_seen")).is_some_and(|d| d <= cut))
                .collect();
            let (sold, sold_n) = if mature.len() < 5 {
                (None, None)
            } else {
                let fast = mature
                    .iter()
                    .filter(|r| {
                        day(&string(r.raw, "gone_at"))
                            .zip(day(&string(r.raw, "first_seen")))
                            .is_some_and(|(g, f)| (0..=30).contains(&(g - f).num_days()))
                    })
                    .count();
                (
                    Some(round(fast as f64 / mature.len() as f64 * 100., 1)),
                    Some(mature.len()),
                )
            };
            let disappeared: Vec<f64> = cohort
                .iter()
                .filter(|r| {
                    optional(r.raw, "gone_at").is_some()
                        && day(&string(r.raw, "first_seen")).is_some()
                })
                .map(|r| r.days)
                .collect();
            let versus = if disappeared.len() >= 5 {
                median(&disappeared)
                    .filter(|m| *m > 0.)
                    .map(|m| round(round(row.days, 1) / m, 2))
            } else {
                None
            };
            let mut risk = Vec::new();
            if discount.is_some_and(|d| d >= 55.) {
                risk.push("too-good-to-be-true".into())
            }
            if price < if kind == Kind::Wheels { 60. } else { 250. } {
                risk.push("implausibly low price".into())
            }
            if reference.is_some() && prices.len() < 5 {
                risk.push("few comparables".into())
            }
            if reference.is_none() {
                risk.push("no comparables".into())
            }
            if number(row.detail, "seller_reviews") == Some(0.) {
                risk.push("zero-review seller".into())
            }
            if number(row.raw, "n_media").unwrap_or(0.) < 4. {
                risk.push("few photos".into())
            }
            if number(row.raw, "desc_len").unwrap_or(0.) < 60. {
                risk.push("thin description".into())
            }
            if dispersion.is_some_and(|d| d > 60.) {
                risk.push("wide comp spread".into())
            }
            let next_price = prices
                .iter()
                .copied()
                .filter(|p| *p > price)
                .min_by(f64::total_cmp);
            let next_up = next_price.map(|p| {
                let mut ties: Vec<&Row<'_>> = comps
                    .iter()
                    .copied()
                    .filter(|r| number(r.raw, "price") == Some(p))
                    .collect();
                ties.sort_by_key(|r| {
                    std::cmp::Reverse(
                        day(&string(r.raw, "first_seen"))
                            .map(|d| (today - d).num_days().max(0))
                            .unwrap_or(-1),
                    )
                });
                let pick = ties[0];
                let first = day(&string(pick.raw, "first_seen"));
                NextUp {
                    price: p,
                    url: format!(
                        "https://buycycle.com/en-lu/product/{}",
                        string(pick.raw, "slug")
                    ),
                    days_listed: first.map(|d| (today - d).num_days().max(0)),
                    ties: ties.len() - 1,
                    age_lower_bound: first.is_some() && first == earliest,
                }
            });
            let country = optional(row.detail, "country")
                .or_else(|| {
                    number(row.raw, "country_id").and_then(|n| countries.get(&(n as i64)).cloned())
                })
                .unwrap_or_default();
            let distance_km = country_km(&country);
            Listing {
                id,
                kind: kind.clone(),
                name: string(row.raw, "name"),
                brand: string(row.raw, "brand"),
                model: row.model.clone(),
                price,
                original_price: original,
                reference_price: reference,
                average_ask: average.map(|v| round(v, 2)),
                comparables: comps.len(),
                z_score: z,
                cut_per_day,
                sold_percent: sold,
                sold_sample: sold_n,
                versus_typical: versus,
                confidence: confidence.into(),
                dispersion,
                discount_percent: discount,
                days_listed: round(row.days, 1),
                first_seen: string(row.raw, "first_seen"),
                gone_at: optional(row.raw, "gone_at"),
                url: format!(
                    "https://buycycle.com/en-lu/product/{}",
                    string(row.raw, "slug")
                ),
                year: number(row.raw, "year").map(|n| n as i32),
                size: optional(row.raw, "size"),
                country,
                risk_flags: risk,
                next_up,
                history: h
                    .iter()
                    .rev()
                    .take(30)
                    .cloned()
                    .collect::<Vec<_>>()
                    .into_iter()
                    .rev()
                    .collect(),
                brake: row.brake.clone(),
                rim_material: row.material.clone(),
                wheel_system: {
                    let sp = row
                        .raw
                        .get("spec")
                        .and_then(Value::as_str)
                        .and_then(|s| serde_json::from_str::<Value>(s).ok())
                        .unwrap_or(Value::Null);
                    match sp.pointer("/spec/wheel-system").and_then(Value::as_str) {
                        Some("1435") => "tubeless",
                        Some("1436") => "tubular",
                        Some("1437") => "clincher",
                        _ => "",
                    }
                    .to_owned()
                },
                seller_reviews: number(row.detail, "seller_reviews").map(|n| n as i64),
                photo_count: number(row.detail, "n_images")
                    .filter(|n| *n != 0.)
                    .or_else(|| number(row.raw, "n_media"))
                    .unwrap_or(0.) as i64,
                description_length: number(row.raw, "desc_len").unwrap_or(0.) as i64,
                distance_km,
                price_reduced: number(row.raw, "pr").is_some_and(|n| n != 0.)
                    || row.raw.get("pr").and_then(Value::as_bool) == Some(true),
                price_drop_percent: (original > 0.)
                    .then(|| round((original - price) / original * 100., 1)),
            }
        })
        .collect()
}
pub fn default_costs(kind: &Kind) -> BTreeMap<String, f64> {
    let pairs = if *kind == Kind::Bikes {
        [
            ("bp", 2.5),
            ("bpf", 0.),
            ("pay", 0.),
            ("shipin", 125.),
            ("pack", 0.),
            ("repair", 50.),
            ("buffer", 75.),
            ("haircut", 5.),
            ("sellfee", 6.95),
            ("shipout", 0.),
            ("relist", 0.),
        ]
    } else {
        [
            ("bp", 6.),
            ("bpf", 1.),
            ("pay", 0.),
            ("shipin", 25.),
            ("pack", 10.),
            ("repair", 0.),
            ("buffer", 20.),
            ("haircut", 5.),
            ("sellfee", 0.),
            ("shipout", 0.),
            ("relist", 0.),
        ]
    };
    pairs.into_iter().map(|(k, v)| (k.into(), v)).collect()
}
/// Historical model statistics retain the legacy distinction between withdrawal and a confirmed sale.
pub fn model_market(
    items: &[Listing],
    history: &[Value],
    today: NaiveDate,
) -> Vec<crate::contracts::ModelMarket> {
    model_market_indexed(items, &HistoryIndex::values(history), today)
}
fn model_market_indexed(
    items: &[Listing],
    history: &HistoryIndex,
    today: NaiveDate,
) -> Vec<crate::contracts::ModelMarket> {
    use crate::contracts::{ModelMarket, ModelTrend};
    let cut = today - Duration::days(30);
    let mut groups: BTreeMap<String, Vec<&Listing>> = BTreeMap::new();
    let mut id_model = HashMap::new();
    for item in items {
        let name = format!("{} {}", item.brand, item.model);
        id_model.insert(item.id.clone(), name.clone());
        groups.entry(name).or_default().push(item);
    }
    let mut trends: BTreeMap<String, BTreeMap<String, Vec<f64>>> = BTreeMap::new();
    for (id, points) in &history.0 {
        if let Some(name) = id_model.get(id) {
            for point in points {
                trends
                    .entry(name.clone())
                    .or_default()
                    .entry(point.day.clone())
                    .or_default()
                    .push(point.price);
            }
        }
    }
    groups
        .into_iter()
        .filter_map(|(name, rows)| {
            let active = rows.iter().filter(|x| x.gone_at.is_none()).count();
            let gone: Vec<_> = rows
                .iter()
                .copied()
                .filter(|x| x.gone_at.as_deref().and_then(day).is_some_and(|g| g >= cut))
                .collect();
            let n = active + gone.len();
            if n < 3 {
                return None;
            }
            let days: Vec<f64> = gone.iter().map(|x| x.days_listed).collect();
            let mut disappeared: Vec<_> = gone
                .iter()
                .map(|x| PricePoint {
                    day: x.gone_at.clone().unwrap(),
                    price: x.price,
                })
                .collect();
            disappeared.sort_by(|a, b| a.day.cmp(&b.day));
            if disappeared.len() > 40 {
                disappeared.drain(..disappeared.len() - 40);
            }
            let mut trend: Vec<_> = trends
                .remove(&name)
                .unwrap_or_default()
                .into_iter()
                .filter_map(|(day, prices)| {
                    Some(ModelTrend {
                        day,
                        median_price: round(median(&prices)?, 0),
                        n: prices.len(),
                    })
                })
                .collect();
            if trend.len() > 120 {
                trend.drain(..trend.len() - 120);
            }
            Some(ModelMarket {
                name,
                active,
                gone30: gone.len(),
                sell_through: Some(round(gone.len() as f64 / n as f64 * 100., 1)),
                median_days: median(&days).map(|n| round(n, 1)),
                trend,
                disappeared,
            })
        })
        .collect()
}
pub fn alerts(
    items: &[Listing],
    models: &[crate::contracts::ModelMarket],
    raw: &[Value],
    kind: &Kind,
    today: &str,
    had_prior: bool,
) -> Vec<crate::contracts::Alert> {
    use crate::contracts::Alert;
    let mut result = Vec::new();
    for item in items {
        let Some(reference) = item.reference_price else {
            continue;
        };
        if item.gone_at.is_some() || item.comparables < 5 {
            continue;
        }
        let known = raw
            .iter()
            .find(|r| string(r, "id") == item.id)
            .and_then(|r| number(r, "activated_at"))
            .is_some_and(|n| n != 0.);
        let is_new = (item.first_seen == today && had_prior) || (known && item.days_listed <= 1.5);
        let dropped = item.history.len() > 1
            && item.history.last().is_some_and(|h| {
                h.day == today && h.price < item.history[item.history.len() - 2].price
            });
        if !is_new && !dropped {
            continue;
        }
        let (bp, bpf, ship_in, seller, pack, buffer, minprofit) = if *kind == Kind::Bikes {
            (0.025, 0., 125., 0.0695, 0., 75., 300.)
        } else {
            (0.06, 1., 25., 0., 10., 20., 100.)
        };
        let sale = reference * 0.95;
        let cost = item.price * (1. + bp) + bpf + ship_in + pack + buffer;
        let profit = sale * (1. - seller) - cost;
        let roi = profit / cost * 100.;
        let hard = item.risk_flags.iter().any(|r| {
            matches!(
                r.as_str(),
                "too-good-to-be-true" | "implausibly low price" | "zero-review seller"
            )
        });
        if profit < minprofit || roi < 15. || hard {
            continue;
        }
        let name = format!("{} {}", item.brand, item.model);
        let market = models.iter().find(|m| m.name == name);
        result.push(Alert {
            id: item.id.clone(),
            name: item.name.clone(),
            url: item.url.clone(),
            price: item.price,
            reference_price: reference,
            comparables: item.comparables,
            confidence: item.confidence.clone(),
            estimated_profit: round(profit, 0),
            roi_percent: round(roi, 1),
            reason: if is_new {
                "new listing"
            } else {
                "price dropped today"
            }
            .into(),
            country: item.country.clone(),
            risk_flags: item.risk_flags.clone(),
            model_sell_through: market.and_then(|m| m.sell_through),
            model_median_days: market.and_then(|m| m.median_days),
        });
    }
    result.sort_by(|a, b| b.estimated_profit.total_cmp(&a.estimated_profit));
    result.truncate(50);
    result
}
#[derive(Clone, serde::Serialize, serde::Deserialize)]
pub struct CalculationInput<H = Value> {
    pub kind: Kind,
    pub calculated_at: DateTime<Utc>,
    pub rows: Vec<Value>,
    pub details: Vec<Value>,
    pub history: Vec<H>,
    pub countries: Vec<Value>,
    pub runs: Vec<Value>,
}
/// The same pure computation serves HTTP, the collector's retained output, and offline replay.
pub fn report(input: CalculationInput) -> crate::contracts::ListingsResponse {
    let indexed = HistoryIndex::values(&input.history);
    drop(input.history);
    report_indexed(
        input.kind,
        input.calculated_at,
        input.rows,
        input.details,
        indexed,
        input.countries,
        input.runs,
    )
}

pub fn report_raw(
    input: CalculationInput<Box<serde_json::value::RawValue>>,
) -> crate::contracts::ListingsResponse {
    report_indexed(
        input.kind,
        input.calculated_at,
        input.rows,
        input.details,
        HistoryIndex::raw(input.history),
        input.countries,
        input.runs,
    )
}

fn report_indexed(
    kind: Kind,
    now: DateTime<Utc>,
    rows: Vec<Value>,
    details: Vec<Value>,
    history: HistoryIndex,
    countries: Vec<Value>,
    runs: Vec<Value>,
) -> crate::contracts::ListingsResponse {
    let quarantined = rows
        .iter()
        .filter(|r| {
            string(r, "kind") == kind.as_str() && number(r, "price").is_none_or(|price| price <= 0.)
        })
        .map(|r| crate::contracts::QuarantinedListing {
            id: string(r, "id"),
            reason: "missing_or_invalid_price".into(),
        })
        .collect();
    let today = now.with_timezone(&Luxembourg).date_naive().to_string();
    let items = build_indexed(kind.clone(), &rows, &details, &history, &countries, now);
    let models = model_market_indexed(
        &items,
        &history,
        now.with_timezone(&Luxembourg).date_naive(),
    );
    let had_prior = runs.iter().any(|r| {
        r.get("kind").and_then(Value::as_str) == Some(kind.as_str())
            && r.get("day")
                .and_then(Value::as_str)
                .is_some_and(|d| d < today.as_str())
            && r.get("complete").and_then(Value::as_i64) == Some(1)
    });
    let alerts = alerts(&items, &models, &rows, &kind, &today, had_prior);
    let active = items.iter().filter(|x| x.gone_at.is_none()).count();
    let gone = items.len() - active;
    crate::contracts::ListingsResponse {
        quarantined,
        kind,
        generated: now.to_rfc3339(),
        today,
        items,
        models,
        alerts,
        active,
        gone,
    }
}
