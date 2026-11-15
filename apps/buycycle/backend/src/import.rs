//! Lossless legacy import: validate before opening a write transaction, reconcile
//! every table before commit, and never overwrite an existing conflicting row.
use std::collections::{BTreeMap, BTreeSet};

use chrono::{NaiveDate, Utc};
use diesel::{
    sql_query,
    sql_types::{Bool, Date, Integer, Jsonb, Text},
};
use diesel_async::{AsyncConnection, AsyncPgConnection, RunQueryDsl};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};

use crate::persistence::{DataError, Db, LEGACY_TABLES, row_key};

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LegacyBundle {
    pub version: u32,
    pub exported_at: String,
    pub processing_version: String,
    pub tables: BTreeMap<String, Vec<Value>>,
    pub table_sha256: BTreeMap<String, String>,
    pub source_schema: BTreeMap<String, Value>,
    pub safety_ledger: Option<Value>,
}

#[derive(Clone, Debug, Serialize, Deserialize, Eq, PartialEq)]
pub struct ImportReport {
    pub bundle_sha256: String,
    pub table_counts: BTreeMap<String, usize>,
    pub table_sha256: BTreeMap<String, String>,
    pub already_imported: bool,
}

#[derive(diesel::QueryableByName)]
struct JsonRow {
    #[diesel(sql_type=Jsonb)]
    payload: Value,
}

pub fn canonical_sha256(value: &impl Serialize) -> Result<String, DataError> {
    // serde_json's default Map is ordered; every record is key-sorted recursively.
    let canonical: Value = serde_json::to_value(value).map_err(|_| DataError::InvalidInput)?;
    Ok(format!(
        "{:x}",
        Sha256::digest(serde_json::to_vec(&canonical).map_err(|_| DataError::InvalidInput)?)
    ))
}

pub fn canonical_rows(table: &str, rows: &[Value]) -> Result<Vec<Value>, DataError> {
    let mut keyed = BTreeMap::new();
    for row in rows {
        let key = row_key(table, row)?;
        if keyed.insert(key, row.clone()).is_some() {
            return Err(DataError::InvalidInput);
        }
        // Legacy SQLite/Turso scalar columns are integer/text/null. Retain unknown
        // columns, but reject nested/boolean/non-integral values, never coerce them.
        if row
            .as_object()
            .ok_or(DataError::InvalidInput)?
            .values()
            .any(|v| !(v.is_null() || v.is_string() || v.as_i64().is_some()))
        {
            return Err(DataError::InvalidInput);
        }
    }
    Ok(keyed.into_values().collect())
}

pub fn validate_bundle(bundle: &LegacyBundle) -> Result<ImportReport, DataError> {
    let expected: BTreeSet<_> = LEGACY_TABLES.into_iter().map(str::to_owned).collect();
    if bundle.version != 1
        || bundle.processing_version.is_empty()
        || bundle.tables.keys().cloned().collect::<BTreeSet<_>>() != expected
        || bundle.table_sha256.keys().cloned().collect::<BTreeSet<_>>() != expected
        || bundle
            .source_schema
            .keys()
            .cloned()
            .collect::<BTreeSet<_>>()
            != expected
        || chrono::DateTime::parse_from_rfc3339(&bundle.exported_at).is_err()
    {
        return Err(DataError::InvalidInput);
    }
    if let Some(ledger) = &bundle.safety_ledger {
        validate_ledger(ledger)?;
    }
    let mut table_counts = BTreeMap::new();
    let mut table_sha256 = BTreeMap::new();
    for table in LEGACY_TABLES {
        let rows = canonical_rows(table, &bundle.tables[table])?;
        let digest = canonical_sha256(&rows)?;
        if bundle.table_sha256[table] != digest || !bundle.source_schema[table].is_array() {
            return Err(DataError::Reconciliation);
        }
        table_counts.insert(table.to_owned(), rows.len());
        table_sha256.insert(table.to_owned(), digest);
    }
    Ok(ImportReport {
        bundle_sha256: canonical_sha256(bundle)?,
        table_counts,
        table_sha256,
        already_imported: false,
    })
}

fn validate_ledger(ledger: &Value) -> Result<(), DataError> {
    let object = ledger.as_object().ok_or(DataError::InvalidInput)?;
    let expected: BTreeSet<_> = [
        "version",
        "day",
        "detail_attempts",
        "blocked",
        "pending",
        "feeds",
    ]
    .into_iter()
    .collect();
    if object.keys().map(String::as_str).collect::<BTreeSet<_>>() != expected
        || ledger["version"].as_u64() != Some(1)
    {
        return Err(DataError::InvalidInput);
    }
    let day = ledger["day"].as_str().ok_or(DataError::InvalidInput)?;
    let parsed = NaiveDate::parse_from_str(day, "%Y-%m-%d").map_err(|_| DataError::InvalidInput)?;
    if parsed.to_string() != day
        || !ledger["blocked"].is_boolean()
        || !ledger["pending"].is_boolean()
        || ledger["detail_attempts"].as_u64().is_none_or(|n| n > 150)
    {
        return Err(DataError::InvalidInput);
    }
    let feeds = ledger["feeds"].as_array().ok_or(DataError::InvalidInput)?;
    let mut unique = BTreeSet::new();
    for feed in feeds {
        let kind = feed.as_str().ok_or(DataError::InvalidInput)?;
        if !["bikes", "wheels"].contains(&kind) || !unique.insert(kind) {
            return Err(DataError::InvalidInput);
        }
    }
    Ok(())
}

pub async fn reconcile(db: &Db, bundle: &LegacyBundle) -> Result<ImportReport, DataError> {
    let report = validate_bundle(bundle)?;
    for table in LEGACY_TABLES {
        let actual = canonical_rows(table, &db.rows(table).await?)?;
        if report.table_sha256[table] != canonical_sha256(&actual)?
            || report.table_counts[table] != actual.len()
        {
            return Err(DataError::Reconciliation);
        }
    }
    Ok(report)
}

pub async fn import_bundle(db: &Db, bundle: &LegacyBundle) -> Result<ImportReport, DataError> {
    let report = validate_bundle(bundle)?;
    let bundle = bundle.clone();
    let mut connection = db.connection().await?;
    AsyncPgConnection::transaction::<_, DataError, _>(&mut connection, async move |connection| {
        sql_query("SELECT pg_advisory_xact_lock(731957311)")
            .execute(&mut *connection)
            .await?;
        let present =
            sql_query("SELECT manifest AS payload FROM import_manifest WHERE bundle_sha256=$1")
                .bind::<Text, _>(&report.bundle_sha256)
                .load::<JsonRow>(&mut *connection)
                .await?;
        if !present.is_empty() {
            return Ok(ImportReport {
                already_imported: true,
                ..report
            });
        }
        for table in LEGACY_TABLES {
            for row in canonical_rows(table, &bundle.tables[table])? {
                let key = row_key(table, &row)?;
                let existing = sql_query(
                    "SELECT payload FROM legacy_record WHERE table_name=$1 AND row_key=$2",
                )
                .bind::<Text, _>(table)
                .bind::<Text, _>(&key)
                .load::<JsonRow>(&mut *connection)
                .await?;
                if let Some(existing) = existing.first() {
                    if existing.payload != row {
                        return Err(DataError::Conflict);
                    }
                } else {
                    sql_query(
                        "INSERT INTO legacy_record(table_name,row_key,payload) VALUES($1,$2,$3)",
                    )
                    .bind::<Text, _>(table)
                    .bind::<Text, _>(key)
                    .bind::<Jsonb, _>(row)
                    .execute(&mut *connection)
                    .await?;
                }
            }
            let actual =
                sql_query("SELECT payload FROM legacy_record WHERE table_name=$1 ORDER BY row_key")
                    .bind::<Text, _>(table)
                    .load::<JsonRow>(&mut *connection)
                    .await?;
            let rows: Vec<_> = actual.into_iter().map(|row| row.payload).collect();
            if canonical_sha256(&canonical_rows(table, &rows)?)? != report.table_sha256[table] {
                return Err(DataError::Reconciliation);
            }
        }
        import_safety(connection, bundle.safety_ledger.as_ref()).await?;
        sql_query("INSERT INTO import_manifest(bundle_sha256,manifest) VALUES($1,$2)")
            .bind::<Text, _>(&report.bundle_sha256)
            .bind::<Jsonb, _>(json!({"bundle":bundle,"report":report}))
            .execute(&mut *connection)
            .await?;
        Ok(report)
    })
    .await
}

async fn import_safety(
    connection: &mut AsyncPgConnection,
    ledger: Option<&Value>,
) -> Result<(), DataError> {
    let today = Utc::now()
        .with_timezone(&chrono_tz::Europe::Luxembourg)
        .date_naive();
    let same_day = ledger.is_some_and(|l| l["day"].as_str() == Some(&today.to_string()));
    if let Some(ledger) = ledger {
        let day = NaiveDate::parse_from_str(
            ledger["day"].as_str().ok_or(DataError::InvalidInput)?,
            "%Y-%m-%d",
        )
        .map_err(|_| DataError::InvalidInput)?;
        if day > today {
            return Err(DataError::InvalidInput);
        }
    }
    // Pending means we cannot prove whether an attempt/cooldown completed. Missing
    // or older ledgers also cannot establish activation-day request consumption.
    let trusted = same_day && ledger.is_some_and(|l| l["pending"].as_bool() == Some(false));
    let attempts = if trusted {
        ledger
            .and_then(|l| l["detail_attempts"].as_i64())
            .ok_or(DataError::InvalidInput)? as i32
    } else {
        150
    };
    let blocked = !trusted || ledger.is_some_and(|l| l["blocked"].as_bool() == Some(true));
    let feeds = if trusted {
        ledger
            .map(|l| l["feeds"].clone())
            .unwrap_or_else(|| json!([]))
    } else {
        json!(["bikes", "wheels"])
    };
    sql_query("INSERT INTO collection_day(day,detail_attempts,blocked,pending,feeds) VALUES($1,$2,$3,false,$4) ON CONFLICT(day) DO UPDATE SET detail_attempts=GREATEST(collection_day.detail_attempts,EXCLUDED.detail_attempts),blocked=collection_day.blocked OR EXCLUDED.blocked,pending=collection_day.pending OR EXCLUDED.pending,feeds=CASE WHEN collection_day.feeds=EXCLUDED.feeds THEN collection_day.feeds ELSE '[\"bikes\",\"wheels\"]'::jsonb END,updated_at=clock_timestamp()")
        .bind::<Date,_>(today).bind::<Integer,_>(attempts).bind::<Bool,_>(blocked).bind::<Jsonb,_>(feeds).execute(&mut *connection).await?;
    Ok(())
}
