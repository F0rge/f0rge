//! Authoritative wire types. OpenAPI and the frontend client are generated from these definitions.
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
use utoipa::ToSchema;

#[derive(Clone, Debug, Serialize, Deserialize, ToSchema, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum Kind {
    Bikes,
    Wheels,
}
impl Kind {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Bikes => "bikes",
            Self::Wheels => "wheels",
        }
    }
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct PricePoint {
    pub day: String,
    pub price: f64,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct NextUp {
    pub price: f64,
    pub url: String,
    pub days_listed: Option<i64>,
    pub ties: usize,
    pub age_lower_bound: bool,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct Listing {
    pub id: String,
    pub kind: Kind,
    pub name: String,
    pub brand: String,
    pub model: String,
    pub price: f64,
    pub original_price: f64,
    pub reference_price: Option<f64>,
    pub average_ask: Option<f64>,
    pub comparables: usize,
    pub z_score: Option<f64>,
    pub cut_per_day: Option<f64>,
    pub sold_percent: Option<f64>,
    pub sold_sample: Option<usize>,
    pub versus_typical: Option<f64>,
    pub confidence: String,
    pub dispersion: Option<f64>,
    pub discount_percent: Option<f64>,
    pub days_listed: f64,
    pub first_seen: String,
    pub gone_at: Option<String>,
    pub url: String,
    pub year: Option<i32>,
    pub size: Option<String>,
    pub country: String,
    pub risk_flags: Vec<String>,
    pub next_up: Option<NextUp>,
    pub history: Vec<PricePoint>,
    pub brake: String,
    pub rim_material: String,
    pub wheel_system: String,
    pub seller_reviews: Option<i64>,
    pub photo_count: i64,
    pub description_length: i64,
    pub distance_km: Option<f64>,
    pub price_reduced: bool,
    pub price_drop_percent: Option<f64>,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct ListingsResponse {
    pub quarantined: Vec<QuarantinedListing>,
    pub models: Vec<ModelMarket>,
    pub alerts: Vec<Alert>,
    pub kind: Kind,
    pub generated: String,
    pub today: String,
    pub items: Vec<Listing>,
    pub active: usize,
    pub gone: usize,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct Identity {
    pub subject: String,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct StatusResponse {
    pub status: String,
    pub last_success: Option<String>,
    pub stale: bool,
    pub blocked: bool,
    pub detail_attempts: i32,
    pub detail_limit: i32,
    pub version: String,
    pub identity: Identity,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct WatchEntry {
    pub n: String,
    pub u: String,
    pub p: f64,
    pub t: String,
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct Trade {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub id: Option<String>,
    pub name: String,
    pub url: String,
    pub buy: f64,
    pub bd: String,
    #[serde(default)]
    pub sell: Option<f64>,
    #[serde(default)]
    pub sd: Option<String>,
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}
#[derive(Clone, Debug, Default, Serialize, Deserialize, ToSchema)]
pub struct CategoryState {
    #[serde(default)]
    pub watch: BTreeMap<String, WatchEntry>,
    #[serde(default)]
    pub log: Vec<Trade>,
    #[serde(default)]
    pub costs: BTreeMap<String, f64>,
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}
fn version_one() -> u32 {
    1
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct BrowserState {
    #[serde(default = "version_one")]
    pub version: u32,
    #[serde(default)]
    pub bikes: CategoryState,
    #[serde(default)]
    pub wheels: CategoryState,
    #[serde(flatten)]
    pub extra: BTreeMap<String, Value>,
}
impl Default for BrowserState {
    fn default() -> Self {
        Self {
            version: 1,
            bikes: CategoryState::default(),
            wheels: CategoryState::default(),
            extra: BTreeMap::new(),
        }
    }
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct StateResponse {
    pub revision: i64,
    pub state: BrowserState,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
#[serde(deny_unknown_fields)]
pub struct StateWrite {
    pub expected_revision: i64,
    pub state: BrowserState,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
#[serde(deny_unknown_fields)]
pub struct ImportWrite {
    pub expected_revision: i64,
    pub state: BrowserState,
    pub source: Value,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct ImportCounts {
    pub watches: usize,
    pub trades: usize,
    pub costs: usize,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct ImportPreview {
    pub expected_revision: i64,
    pub counts: ImportCounts,
    pub warnings: Vec<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct Health {
    pub status: String,
    pub version: String,
    pub source_commit: String,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct ModelTrend {
    pub day: String,
    pub median_price: f64,
    pub n: usize,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct ModelMarket {
    pub name: String,
    pub active: usize,
    pub gone30: usize,
    pub sell_through: Option<f64>,
    pub median_days: Option<f64>,
    pub trend: Vec<ModelTrend>,
    pub disappeared: Vec<PricePoint>,
}
#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct Alert {
    pub id: String,
    pub name: String,
    pub url: String,
    pub price: f64,
    pub reference_price: f64,
    pub comparables: usize,
    pub confidence: String,
    pub estimated_profit: f64,
    pub roi_percent: f64,
    pub reason: String,
    pub country: String,
    pub risk_flags: Vec<String>,
    pub model_sell_through: Option<f64>,
    pub model_median_days: Option<f64>,
}

#[derive(Clone, Debug, Serialize, Deserialize, ToSchema)]
pub struct QuarantinedListing {
    pub id: String,
    pub reason: String,
}
