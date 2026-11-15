//! Single-writer, crash-conservative collection. Reservations commit before outbound requests.
use crate::{
    contracts::Kind,
    metrics,
    persistence::{DataError, Db},
};
use chrono::{DateTime, NaiveDate, Utc};
use chrono_tz::Europe::Luxembourg;
use diesel::{
    sql_query,
    sql_types::{Bool, Date, Integer, Jsonb, Text, Uuid as SqlUuid},
};
use diesel_async::{AsyncPgConnection, RunQueryDsl};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    collections::{HashMap, HashSet},
    future::Future,
    time::Duration,
};
use uuid::Uuid;

pub const FEED_PAUSE: Duration = Duration::from_millis(1600);
pub const DETAIL_PAUSE: Duration = Duration::from_millis(2200);
pub const BLOCK_PAUSE: Duration = Duration::from_secs(120);
pub const DAILY_CAP: i32 = 150;
const LOCK_ID: i64 = 731957311;
const COLLECTOR_VERSION: &str = "buycycle-rust-v1";
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CollectionError {
    Held,
    Blocked,
    Budget,
    Incomplete,
    Storage,
}
impl std::fmt::Display for CollectionError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            Self::Held => "Collection held for safety",
            Self::Blocked => "Collection blocked by upstream",
            Self::Budget => "Daily detail budget exhausted",
            Self::Incomplete => "Collection incomplete; last observations retained",
            Self::Storage => "Collection storage unavailable",
        })
    }
}
impl std::error::Error for CollectionError {}
impl From<DataError> for CollectionError {
    fn from(_: DataError) -> Self {
        Self::Storage
    }
}
impl From<diesel::result::Error> for CollectionError {
    fn from(_: diesel::result::Error) -> Self {
        Self::Storage
    }
}
#[derive(diesel::QueryableByName)]
struct BoolResult {
    #[diesel(sql_type=Bool)]
    value: bool,
}
#[derive(diesel::QueryableByName)]
struct Ledger {
    #[diesel(sql_type=Integer)]
    detail_attempts: i32,
    #[diesel(sql_type=Bool)]
    blocked: bool,
    #[diesel(sql_type=Bool)]
    pending: bool,
}
pub struct Gate {
    connection: AsyncPgConnection,
    day: NaiveDate,
}
impl Gate {
    pub async fn acquire(db: &Db, now: DateTime<Utc>) -> Result<Self, CollectionError> {
        let mut connection = db.connection().await?;
        let locked = sql_query("SELECT pg_try_advisory_lock($1) AS value")
            .bind::<diesel::sql_types::BigInt, _>(LOCK_ID)
            .get_result::<BoolResult>(&mut connection)
            .await?
            .value;
        if !locked {
            return Err(CollectionError::Held);
        }
        let day = now.with_timezone(&Luxembourg).date_naive();
        let future = sql_query("SELECT EXISTS(SELECT 1 FROM collection_day WHERE day>$1) AS value")
            .bind::<Date, _>(day)
            .get_result::<BoolResult>(&mut connection)
            .await?
            .value;
        if future {
            return Err(CollectionError::Held);
        }
        // Existing observations without a ledger cannot establish the activation day's consumption.
        sql_query("INSERT INTO collection_day(day,detail_attempts,blocked,pending,feeds) SELECT $1,CASE WHEN EXISTS(SELECT 1 FROM legacy_record WHERE table_name IN ('listing','price_history','detail','runs')) AND NOT EXISTS(SELECT 1 FROM collection_day) THEN 150 ELSE 0 END,EXISTS(SELECT 1 FROM legacy_record WHERE table_name IN ('listing','price_history','detail','runs')) AND NOT EXISTS(SELECT 1 FROM collection_day),false,'[]'::jsonb ON CONFLICT DO NOTHING").bind::<Date,_>(day).execute(&mut connection).await?;
        Ok(Self { connection, day })
    }
    async fn allowed(&mut self, now: DateTime<Utc>) -> Result<(), CollectionError> {
        if now.with_timezone(&Luxembourg).date_naive() != self.day {
            return Err(CollectionError::Held);
        }
        let state =
            sql_query("SELECT detail_attempts,blocked,pending FROM collection_day WHERE day=$1")
                .bind::<Date, _>(self.day)
                .get_result::<Ledger>(&mut self.connection)
                .await?;
        if state.blocked || state.pending {
            return Err(CollectionError::Held);
        }
        Ok(())
    }
    pub async fn claim_feed(
        &mut self,
        kind: &Kind,
        now: DateTime<Utc>,
    ) -> Result<bool, CollectionError> {
        self.allowed(now).await?;
        let n=sql_query("UPDATE collection_day SET feeds=feeds || to_jsonb($2::text),updated_at=clock_timestamp() WHERE day=$1 AND NOT feeds ? $2").bind::<Date,_>(self.day).bind::<Text,_>(kind.as_str()).execute(&mut self.connection).await?;
        Ok(n == 1)
    }
    pub async fn before_request(
        &mut self,
        detail: bool,
        now: DateTime<Utc>,
    ) -> Result<(), CollectionError> {
        self.allowed(now).await?;
        let n=sql_query("UPDATE collection_day SET pending=true,detail_attempts=detail_attempts+CASE WHEN $2 THEN 1 ELSE 0 END,updated_at=clock_timestamp() WHERE day=$1 AND NOT blocked AND NOT pending AND (NOT $2 OR detail_attempts<150)").bind::<Date,_>(self.day).bind::<Bool,_>(detail).execute(&mut self.connection).await?;
        if n != 1 {
            return Err(CollectionError::Budget);
        }
        Ok(())
    }
    pub async fn finish(&mut self) -> Result<(), CollectionError> {
        sql_query("UPDATE collection_day SET pending=false,next_allowed_at=NULL,updated_at=clock_timestamp() WHERE day=$1 AND NOT blocked").bind::<Date,_>(self.day).execute(&mut self.connection).await?;
        Ok(())
    }
    pub async fn block(&mut self) -> Result<(), CollectionError> {
        sql_query(
            "UPDATE collection_day SET blocked=true,updated_at=clock_timestamp() WHERE day=$1",
        )
        .bind::<Date, _>(self.day)
        .execute(&mut self.connection)
        .await?;
        Ok(())
    }
}
pub struct SourceResponse {
    pub status: u16,
    pub body: String,
}
pub trait Source {
    fn get(&self, url: &str) -> impl Future<Output = Result<SourceResponse, CollectionError>>;
    fn pause(&self, duration: Duration) -> impl Future<Output = ()>;
    fn now(&self) -> DateTime<Utc> {
        Utc::now()
    }
}
pub struct HttpSource {
    client: reqwest::Client,
}
impl HttpSource {
    pub fn new() -> Result<Self, CollectionError> {
        Ok(Self {
            client: reqwest::Client::builder()
                .redirect(reqwest::redirect::Policy::none())
                .http1_only()
                .timeout(Duration::from_secs(60))
                .user_agent("personal-price-tracker (1 pass/day)")
                .build()
                .map_err(|_| CollectionError::Incomplete)?,
        })
    }
}
impl Source for HttpSource {
    async fn get(&self, url: &str) -> Result<SourceResponse, CollectionError> {
        let response = self
            .client
            .get(url)
            .header("Accept-Language", "en")
            .send()
            .await
            .map_err(|_| CollectionError::Incomplete)?;
        let status = response.status().as_u16();
        if matches!(status, 403 | 429) {
            return Ok(SourceResponse {
                status,
                body: String::new(),
            });
        }
        let mut response = response;
        let mut bytes = Vec::new();
        while let Some(chunk) = response
            .chunk()
            .await
            .map_err(|_| CollectionError::Incomplete)?
        {
            if bytes.len() + chunk.len() > 32 * 1024 * 1024 {
                return Err(CollectionError::Incomplete);
            }
            bytes.extend_from_slice(&chunk);
        }
        let body = String::from_utf8_lossy(&bytes).into_owned();
        Ok(SourceResponse { status, body })
    }
    async fn pause(&self, duration: Duration) {
        tokio::time::sleep(duration).await
    }
}
async fn request<S: Source>(
    gate: &mut Gate,
    source: &S,
    url: &str,
    detail: bool,
) -> Result<String, CollectionError> {
    gate.before_request(detail, source.now()).await?;
    let result = source.get(url).await;
    if result.as_ref().is_ok_and(|r| matches!(r.status, 403 | 429)) {
        gate.block().await?;
        source.pause(BLOCK_PAUSE).await;
        return Err(CollectionError::Blocked);
    }
    source
        .pause(if detail { DETAIL_PAUSE } else { FEED_PAUSE })
        .await;
    gate.finish().await?;
    let response = result?;
    if !(200..300).contains(&response.status) {
        return Err(CollectionError::Incomplete);
    }
    Ok(response.body)
}
fn feed_paths(kind: &Kind) -> Vec<&'static str> {
    if *kind == Kind::Wheels {
        vec!["category_slug/complete-wheels?"]
    } else {
        vec![
            "group_id/road-gravel-category-gravel?filters%5BeBike%5D=0&filters%5Bis_frameset%5D=0&",
            "group_id/road-gravel-category-road?filters%5BeBike%5D=0&filters%5Bis_frameset%5D=0&",
        ]
    }
}
fn identifier(value: &Value) -> Option<String> {
    value
        .as_str()
        .filter(|v| !v.is_empty())
        .map(str::to_owned)
        .or_else(|| value.as_i64().map(|n| n.to_string()))
}
fn row_from_feed(
    item: &Value,
    kind: &Kind,
    today: &str,
    existing: Option<&Value>,
) -> Result<Value, CollectionError> {
    let data = item
        .get("data")
        .and_then(Value::as_object)
        .ok_or(CollectionError::Incomplete)?;
    let id = data
        .get("id")
        .and_then(identifier)
        .ok_or(CollectionError::Incomplete)?;
    let price = data
        .get("price")
        .and_then(Value::as_f64)
        .filter(|p| p.is_finite() && *p > 0.)
        .ok_or(CollectionError::Incomplete)?;
    let value = item
        .get("value")
        .and_then(Value::as_str)
        .ok_or(CollectionError::Incomplete)?;
    let mut row = existing.cloned().unwrap_or_else(|| json!({}));
    let o = row.as_object_mut().ok_or(CollectionError::Incomplete)?;
    for (field, upstream) in [
        ("slug", "slug"),
        ("size", "product_size"),
        ("cond", "condition_code"),
        ("msrp", "msrp"),
        ("original_price", "original_price"),
        ("activated_at", "activated_at"),
        ("updated_at", "updated_at_timestamp"),
        ("country_id", "country_id"),
        ("seller_id", "seller_id"),
        ("favs", "favorite_count"),
        ("offers", "unique_buyer_offers"),
        ("high_demand", "is_high_demand"),
        ("pr", "is_price_reduced"),
    ] {
        o.insert(
            field.into(),
            data.get(upstream).cloned().unwrap_or(Value::Null),
        );
    }
    let brand = data
        .get("brand_name")
        .and_then(Value::as_str)
        .unwrap_or("unknown")
        .trim();
    let name = if *kind == Kind::Wheels {
        format!(
            "{} {}",
            data.get("brand_name").and_then(Value::as_str).unwrap_or(""),
            value
        )
        .trim()
        .to_owned()
    } else {
        value.to_owned()
    };
    o.insert("id".into(), json!(id));
    o.insert("kind".into(), json!(kind.as_str()));
    o.insert("name".into(), json!(name));
    o.insert("brand".into(), json!(brand));
    o.insert("price".into(), json!(price.trunc() as i64));
    o.insert(
        "year".into(),
        data.get("year")
            .and_then(|y| y.as_i64().or_else(|| y.as_str()?.parse().ok()))
            .map_or(Value::Null, Value::from),
    );
    if o["size"].is_null() {
        o.insert(
            "size".into(),
            data.get("frame_size_in_string")
                .cloned()
                .unwrap_or(Value::Null),
        );
    }
    o.insert(
        "n_media".into(),
        json!(
            data.get("media")
                .and_then(Value::as_array)
                .map_or(0, Vec::len)
        ),
    );
    o.insert(
        "desc_len".into(),
        json!(
            data.get("description")
                .and_then(Value::as_str)
                .map_or(0, str::len)
        ),
    );
    o.insert("spec".into(),json!(json!({"spec":data.get("specifications"),"cat":data.get("category_name"),"comp":data.get("component_name")}).to_string()));
    o.entry("first_seen".to_owned()).or_insert(json!(today));
    o.insert("last_seen".into(), json!(today));
    o.insert("gone_at".into(), Value::Null);
    Ok(row)
}
async fn snapshot(
    connection: &mut AsyncPgConnection,
    run: Uuid,
    kind: &Kind,
    source_kind: &str,
    payload: Value,
) -> Result<(), CollectionError> {
    let bytes = serde_json::to_vec(&payload).map_err(|_| CollectionError::Incomplete)?;
    let hash = format!("{:x}", Sha256::digest(bytes));
    sql_query("INSERT INTO source_snapshots(id,run_id,kind,source_kind,sha256,payload) VALUES($1,$2,$3,$4,$5,$6)").bind::<SqlUuid,_>(Uuid::new_v4()).bind::<SqlUuid,_>(run).bind::<Text,_>(kind.as_str()).bind::<Text,_>(source_kind).bind::<Text,_>(hash).bind::<Jsonb,_>(payload).execute(connection).await?;
    Ok(())
}
/// Network collection must be explicitly enabled at release; replay and imports never invoke it.
pub async fn collect<S: Source>(
    db: &Db,
    source: &S,
    api_key: &str,
    kinds: Vec<Kind>,
) -> Result<(), CollectionError> {
    if api_key.is_empty() {
        return Err(CollectionError::Held);
    }
    let mut gate = Gate::acquire(db, source.now()).await?;
    let today = gate.day.to_string();
    let mut incomplete = false;
    for kind in kinds {
        if !gate.claim_feed(&kind, source.now()).await? {
            incomplete = true;
            continue;
        }
        let run = Uuid::new_v4();
        sql_query("INSERT INTO collector_runs(id,day,kind,complete,metadata) VALUES($1,$2,$3,false,$4)").bind::<SqlUuid,_>(run).bind::<Date,_>(gate.day).bind::<Text,_>(kind.as_str()).bind::<Jsonb,_>(json!({"processing_version":COLLECTOR_VERSION,"source_redaction_version":crate::redaction::VERSION,"build_sha":option_env!("BUYCYCLE_SOURCE_COMMIT").unwrap_or("unreleased"),"mode":"collection"})).execute(&mut gate.connection).await?;
        let existing = db.listings(kind.as_str()).await?;
        let old: HashMap<String, Value> = existing
            .into_iter()
            .map(|r| (metrics::string(&r, "id"), r))
            .collect();
        let mut seen: HashMap<String, Value> = HashMap::new();
        let mut complete = true;
        'feeds: for path in feed_paths(&kind) {
            let mut ids = HashSet::new();
            let mut reported = None;
            let mut terminal = false;
            for page in 1..120 {
                let url = format!(
                    "https://ac.cnstrc.com/browse/{path}key={api_key}&num_results_per_page=200&page={page}&c=ciojs-client-2"
                );
                let body = match request(&mut gate, source, &url, false).await {
                    Ok(body) => body,
                    Err(CollectionError::Blocked | CollectionError::Held) => {
                        return Err(CollectionError::Blocked);
                    }
                    Err(_) => {
                        complete = false;
                        break 'feeds;
                    }
                };
                let payload: Value = match serde_json::from_str(&body) {
                    Ok(v) => v,
                    Err(_) => {
                        complete = false;
                        break 'feeds;
                    }
                };
                let payload = crate::redaction::source(payload, api_key)?;
                snapshot(&mut gate.connection, run, &kind, "feed", payload.clone()).await?;
                let Some(response) = payload.get("response") else {
                    complete = false;
                    break 'feeds;
                };
                let Some(results) = response
                    .get("results")
                    .and_then(Value::as_array)
                    .filter(|r| r.len() <= 200)
                else {
                    complete = false;
                    break 'feeds;
                };
                if let Some(total) = response.get("total_num_results") {
                    let Some(total) = total.as_u64() else {
                        complete = false;
                        break 'feeds;
                    };
                    if reported.is_some_and(|old| old != total) {
                        complete = false;
                        break 'feeds;
                    }
                    reported = Some(total);
                }
                let mut page_ids = HashSet::new();
                for item in results {
                    let id = item
                        .get("data")
                        .and_then(|d| d.get("id"))
                        .and_then(identifier);
                    let Some(id) = id else {
                        complete = false;
                        break 'feeds;
                    };
                    if !page_ids.insert(id.clone()) {
                        complete = false;
                        break 'feeds;
                    }
                    let row = match row_from_feed(item, &kind, &today, old.get(&id)) {
                        Ok(r) => r,
                        Err(_) => {
                            complete = false;
                            break 'feeds;
                        }
                    };
                    seen.insert(id, row);
                }
                if !results.is_empty() && page_ids.iter().all(|id| ids.contains(id)) {
                    complete = false;
                    break 'feeds;
                }
                ids.extend(page_ids);
                if results.len() < 200 {
                    if reported.is_some_and(|n| n != ids.len() as u64) {
                        complete = false;
                        break 'feeds;
                    }
                    terminal = true;
                    break;
                }
            }
            if !terminal {
                complete = false;
                break;
            }
        }
        let mut all: Vec<Value> = seen.values().cloned().collect();
        let mut gone = 0;
        let new = seen.keys().filter(|id| !old.contains_key(*id)).count();
        if complete && seen.len() > 500 {
            for (id, mut row) in old {
                if !seen.contains_key(&id)
                    && row.get("gone_at").is_none_or(Value::is_null)
                    && row
                        .get("last_seen")
                        .and_then(Value::as_str)
                        .is_some_and(|last| last < today.as_str())
                {
                    row["gone_at"] = json!(today);
                    all.push(row);
                    gone += 1;
                }
            }
        }
        let history: Vec<Value> = seen
            .values()
            .map(|r| json!({"id":r["id"],"day":today,"price":r["price"]}))
            .collect();
        let initial_run = json!({"day":today,"kind":kind.as_str(),"complete":i32::from(complete),"collection_complete":0,"n":seen.len(),"new":new,"gone":gone,"fetched":0,"note":""});
        db.upsert_tables(&[
            ("listing", all),
            ("price_history", history),
            ("runs", vec![initial_run]),
        ])
        .await?;
        let mut fetched = 0;
        let mut detail_complete = true;
        let mut kind_blocked = false;
        if complete {
            let input = crate::services::calculation_input(db, kind.clone(), source.now())
                .await
                .map_err(|_| CollectionError::Storage)?;
            let rows = input.rows.clone();
            let derived = metrics::build(
                kind.clone(),
                input.rows,
                input.details,
                input.history,
                input.countries,
                source.now(),
            );
            let mut candidates: Vec<_> = derived
                .into_iter()
                .filter(|r| {
                    r.gone_at.is_none()
                        && r.discount_percent.is_some_and(|d| d >= 15.)
                        && r.comparables >= 3
                })
                .collect();
            candidates.sort_by(|a, b| {
                b.discount_percent
                    .partial_cmp(&a.discount_percent)
                    .unwrap_or(std::cmp::Ordering::Equal)
            });
            for candidate in candidates {
                let Some(mut row) = rows
                    .iter()
                    .find(|r| metrics::string(r, "id") == candidate.id)
                    .cloned()
                else {
                    continue;
                };
                if row.get("fetch_price") == row.get("price") {
                    continue;
                }
                let slug = metrics::string(&row, "slug");
                if slug.is_empty() || slug.contains(['/', '?', '#']) {
                    detail_complete = false;
                    incomplete = true;
                    continue;
                }
                let body = match request(
                    &mut gate,
                    source,
                    &format!("https://buycycle.com/en-lu/product/{slug}"),
                    true,
                )
                .await
                {
                    Ok(b) => b,
                    Err(CollectionError::Budget) => {
                        detail_complete = false;
                        break;
                    }
                    Err(CollectionError::Blocked | CollectionError::Held) => {
                        detail_complete = false;
                        kind_blocked = true;
                        break;
                    }
                    Err(_) => {
                        detail_complete = false;
                        incomplete = true;
                        continue;
                    }
                };
                let body = crate::redaction::detail_html(&body, api_key)?;
                snapshot(&mut gate.connection, run, &kind, "detail", json!(body)).await?;
                let mut detail = match parse_detail(&body, &candidate.id, &slug, &today) {
                    Ok(d) => d,
                    Err(_) => {
                        detail_complete = false;
                        incomplete = true;
                        continue;
                    }
                };
                if detail.get("country_id").is_none_or(Value::is_null) {
                    detail["country_id"] = row.get("country_id").cloned().unwrap_or(Value::Null);
                }
                row["fetch_price"] = row["price"].clone();
                row["last_fetch"] = json!(today);
                fetched += 1;
                let detail_run = json!({"day":today,"kind":kind.as_str(),"complete":i32::from(complete),"collection_complete":0,"n":seen.len(),"new":new,"gone":gone,"fetched":fetched,"note":""});
                let mut tables = vec![
                    ("detail", vec![detail.clone()]),
                    ("listing", vec![row]),
                    ("runs", vec![detail_run]),
                ];
                if let (Some(cid), Some(country)) = (
                    detail.get("country_id").and_then(Value::as_i64),
                    detail
                        .get("country")
                        .and_then(Value::as_str)
                        .filter(|s| !s.is_empty()),
                ) {
                    tables.push(("country_map", vec![json!({"cid":cid,"country":country})]));
                }
                db.upsert_tables(&tables).await?;
            }
        }
        let overall_complete = complete && detail_complete && !kind_blocked;
        db.upsert_rows("runs",&[json!({"day":today,"kind":kind.as_str(),"complete":i32::from(complete),"collection_complete":i32::from(overall_complete),"n":seen.len(),"new":new,"gone":gone,"fetched":fetched,"note":if !complete{"feed incomplete"}else if !detail_complete{"detail collection incomplete"}else{""}})]).await?;
        sql_query("UPDATE collector_runs SET complete=$2 WHERE id=$1")
            .bind::<SqlUuid, _>(run)
            .bind::<Bool, _>(overall_complete)
            .execute(&mut gate.connection)
            .await?;
        let input = crate::services::calculation_input(db, kind.clone(), source.now())
            .await
            .map_err(|_| CollectionError::Storage)?;
        let expected = metrics::report(input.clone());
        snapshot(
            &mut gate.connection,
            run,
            &kind,
            "replay",
            json!({"processing_digest":processing_digest(),"input":input,"expected":expected}),
        )
        .await?;
        if kind_blocked {
            return Err(CollectionError::Blocked);
        }
        if !overall_complete {
            incomplete = true;
        }
    }
    if incomplete {
        Err(CollectionError::Incomplete)
    } else {
        Ok(())
    }
}
pub fn parse_detail(
    html: &str,
    id: &str,
    slug: &str,
    today: &str,
) -> Result<Value, CollectionError> {
    let re = regex::Regex::new(r#"self\.__next_f\.push\(\[1,\"(.*?)\"\]\)</script>"#)
        .expect("constant regex");
    let mut full = String::new();
    for c in re.captures_iter(html) {
        let decoded: String = serde_json::from_str(&format!("\"{}\"", &c[1]))
            .map_err(|_| CollectionError::Incomplete)?;
        full.push_str(&decoded)
    }
    fn product(value: &Value, id: &str, slug: &str) -> Option<Value> {
        if value.get("id").and_then(identifier).as_deref() == Some(id)
            && value.get("slug").and_then(Value::as_str) == Some(slug)
            && value
                .get("price")
                .and_then(Value::as_f64)
                .is_some_and(|p| p.is_finite() && p >= 0.)
        {
            return Some(value.clone());
        }
        match value {
            Value::Array(values) => values.iter().find_map(|v| product(v, id, slug)),
            Value::Object(values) => values.values().find_map(|v| product(v, id, slug)),
            _ => None,
        }
    }
    let object = crate::redaction::fragments(&full)?
        .iter()
        .find_map(|value| product(value, id, slug))
        .ok_or(CollectionError::Incomplete)?;
    let seller = object.get("seller").unwrap_or(&Value::Null);
    Ok(
        json!({"id":id,"fetched":today,"status":object.get("status"),"can_buy":i32::from(object.get("can_buy_product").and_then(Value::as_bool).unwrap_or(false)),"country":object.get("country"),"country_id":object.get("country_id"),"city":object.get("city"),"seller_reviews":seller.get("user_reviews_count"),"seller_rating":seller.get("avg_rating"),"member_since":seller.get("member_since"),"listings":null,"n_images":object.get("images").and_then(Value::as_array).map(Vec::len),"shipping":null,"bp":null,"total":object.get("total_with_fee_short").and_then(|t|t.get("total_price")),"badge":object.get("price_badge").and_then(|b|b.get("text_value"))}),
    )
}
pub async fn ledger_status(db: &Db) -> Result<(i32, bool), DataError> {
    let mut c = db.connection().await?;
    let day = Utc::now().with_timezone(&Luxembourg).date_naive();
    let state =
        sql_query("SELECT detail_attempts,blocked,pending FROM collection_day WHERE day=$1")
            .bind::<Date, _>(day)
            .load::<Ledger>(&mut c)
            .await?;
    Ok(state
        .first()
        .map_or((0, false), |s| (s.detail_attempts, s.blocked || s.pending)))
}
pub fn processing_digest() -> String {
    let mut hash = Sha256::new();
    for source in [
        include_str!("metrics.rs"),
        include_str!("contracts.rs"),
        include_str!("services.rs"),
        include_str!("collector.rs"),
        include_str!("redaction.rs"),
        include_str!("../Cargo.lock"),
    ] {
        hash.update(source.as_bytes());
    }
    format!("{:x}", hash.finalize())
}
#[derive(diesel::QueryableByName)]
struct SnapshotRow {
    #[diesel(sql_type=Jsonb)]
    payload: Value,
    #[diesel(sql_type=Text)]
    sha256: String,
}
/// Read-only replay cannot construct an HTTP transport or reset collection accounting.
pub async fn replay(db: &Db, run: Uuid, recalculate: bool) -> Result<Value, CollectionError> {
    let mut connection = db.connection().await?;
    let records=sql_query("SELECT payload,sha256 FROM source_snapshots WHERE run_id=$1 AND source_kind='replay' ORDER BY recorded_at DESC LIMIT 1").bind::<SqlUuid,_>(run).load::<SnapshotRow>(&mut connection).await?;
    let saved = records
        .into_iter()
        .next()
        .ok_or(CollectionError::Incomplete)?;
    let hash = format!(
        "{:x}",
        Sha256::digest(
            serde_json::to_vec(&saved.payload).map_err(|_| CollectionError::Incomplete)?
        )
    );
    if hash != saved.sha256 {
        return Err(CollectionError::Incomplete);
    }
    if !recalculate
        && saved
            .payload
            .get("processing_digest")
            .and_then(Value::as_str)
            != Some(processing_digest().as_str())
    {
        return Err(CollectionError::Incomplete);
    }
    let input: metrics::CalculationInput = serde_json::from_value(
        saved
            .payload
            .get("input")
            .cloned()
            .ok_or(CollectionError::Incomplete)?,
    )
    .map_err(|_| CollectionError::Incomplete)?;
    let result =
        serde_json::to_value(metrics::report(input)).map_err(|_| CollectionError::Incomplete)?;
    if !recalculate && saved.payload.get("expected") != Some(&result) {
        return Err(CollectionError::Incomplete);
    }
    Ok(
        json!({"mode":if recalculate{"new_recalculation"}else{"original_replay"},"source_run_id":run,"processing_digest":processing_digest(),"result":result}),
    )
}

pub async fn has_incomplete_run_today(db: &Db) -> Result<bool, DataError> {
    let mut connection = db.connection().await?;
    let today = Utc::now().with_timezone(&Luxembourg).date_naive();
    Ok(sql_query(
        "SELECT EXISTS(SELECT 1 FROM collector_runs WHERE day=$1 AND NOT complete) AS value",
    )
    .bind::<Date, _>(today)
    .get_result::<BoolResult>(&mut connection)
    .await?
    .value)
}
