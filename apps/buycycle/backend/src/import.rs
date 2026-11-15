//! Lossless legacy import: validate before opening a write transaction, reconcile
//! every table before commit, and never overwrite an existing conflicting row.
use std::{
    borrow::Cow,
    collections::{BTreeMap, BTreeSet},
    io::{self, Write},
};

use chrono::{NaiveDate, Utc};
use diesel::{
    sql_query,
    sql_types::{Bool, Date, Integer, Jsonb, Text},
};
use diesel_async::{AsyncConnection, AsyncPgConnection, RunQueryDsl, SimpleAsyncConnection};
use futures_util::TryStreamExt;
use serde::{
    Deserialize, Serialize,
    ser::{Error as _, SerializeMap, SerializeSeq},
};
use serde_json::{Value, json, value::RawValue};
use sha2::{Digest, Sha256};

use crate::persistence::{DataError, Db, LEGACY_TABLES, row_key};

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LegacyBundle<R = Value> {
    pub version: u32,
    pub exported_at: String,
    pub processing_version: String,
    pub tables: BTreeMap<String, Vec<R>>,
    pub table_sha256: BTreeMap<String, String>,
    pub source_schema: BTreeMap<String, Value>,
    pub safety_ledger: Option<Value>,
}

/// The CLI retains compact row JSON and decodes only the row being processed;
/// small seed/test callers can continue to borrow their existing Value rows.
pub trait LegacyRow: Serialize + Send + Sync {
    fn value(&self) -> Result<Cow<'_, Value>, DataError>;
}

impl LegacyRow for Value {
    fn value(&self) -> Result<Cow<'_, Value>, DataError> {
        Ok(Cow::Borrowed(self))
    }
}

impl LegacyRow for Box<RawValue> {
    fn value(&self) -> Result<Cow<'_, Value>, DataError> {
        serde_json::from_str(self.get())
            .map(Cow::Owned)
            .map_err(|_| DataError::InvalidInput)
    }
}

pub(crate) struct CanonicalRows<'a, R>(pub(crate) &'a [R]);
impl<R: LegacyRow> Serialize for CanonicalRows<'_, R> {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        let mut sequence = serializer.serialize_seq(Some(self.0.len()))?;
        for row in self.0 {
            let value = row
                .value()
                .map_err(|_| S::Error::custom("Invalid legacy row"))?;
            sequence.serialize_element(value.as_ref())?;
        }
        sequence.end()
    }
}

struct CanonicalTables<'a, R>(&'a BTreeMap<String, Vec<R>>);
impl<R: LegacyRow> Serialize for CanonicalTables<'_, R> {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        let mut map = serializer.serialize_map(Some(self.0.len()))?;
        for (name, rows) in self.0 {
            map.serialize_entry(name, &CanonicalRows(rows))?;
        }
        map.end()
    }
}

// The exported Python bundle is recursively key-sorted. Spell out its struct
// order while normalizing each raw row through the same Value parser as before.
impl<R: LegacyRow> Serialize for LegacyBundle<R> {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        #[derive(Serialize)]
        struct CanonicalBundle<'a, R: LegacyRow> {
            exported_at: &'a str,
            processing_version: &'a str,
            safety_ledger: &'a Option<Value>,
            source_schema: &'a BTreeMap<String, Value>,
            table_sha256: &'a BTreeMap<String, String>,
            tables: CanonicalTables<'a, R>,
            version: u32,
        }
        CanonicalBundle {
            exported_at: &self.exported_at,
            processing_version: &self.processing_version,
            safety_ledger: &self.safety_ledger,
            source_schema: &self.source_schema,
            table_sha256: &self.table_sha256,
            tables: CanonicalTables(&self.tables),
            version: self.version,
        }
        .serialize(serializer)
    }
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
    #[diesel(sql_type=Text)]
    row_key: String,
    #[diesel(sql_type=Jsonb)]
    payload: Value,
}

#[derive(Default)]
struct HashWriter(Sha256);
impl Write for HashWriter {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        self.0.update(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}
impl HashWriter {
    fn finish(self) -> String {
        format!("{:x}", self.0.finalize())
    }
}

/// General convenience for small fixtures, including arbitrary Serialize structs.
/// Keep its original recursive sorting contract; the production bundle uses the
/// explicitly ordered serializer directly, without this Value conversion.
pub fn canonical_sha256(value: &impl Serialize) -> Result<String, DataError> {
    let canonical = serde_json::to_value(value).map_err(|_| DataError::InvalidInput)?;
    stream_ordered_sha256(&canonical)
}

pub(crate) fn stream_ordered_sha256(value: &impl Serialize) -> Result<String, DataError> {
    let mut hash = HashWriter::default();
    serde_json::to_writer(&mut hash, value).map_err(|_| DataError::InvalidInput)?;
    Ok(hash.finish())
}

fn validate_row(table: &str, row: &Value) -> Result<String, DataError> {
    let key = row_key(table, row)?;
    // Preserve unknown integer/text/null columns; never coerce or drop values.
    if row
        .as_object()
        .ok_or(DataError::InvalidInput)?
        .values()
        .any(|v| !(v.is_null() || v.is_string() || v.as_i64().is_some()))
    {
        return Err(DataError::InvalidInput);
    }
    Ok(key)
}

fn ordered_rows<'a, R: LegacyRow>(
    table: &str,
    rows: &'a [R],
) -> Result<Vec<(String, &'a R)>, DataError> {
    let mut keyed = rows
        .iter()
        .map(|row| Ok((validate_row(table, row.value()?.as_ref())?, row)))
        .collect::<Result<Vec<_>, DataError>>()?;
    keyed.sort_unstable_by(|left, right| left.0.cmp(&right.0));
    if keyed.windows(2).any(|pair| pair[0].0 == pair[1].0) {
        return Err(DataError::InvalidInput);
    }
    Ok(keyed)
}

/// Owned convenience for the small seed/test fixtures. Production borrows rows.
pub fn canonical_rows(table: &str, rows: &[Value]) -> Result<Vec<Value>, DataError> {
    Ok(ordered_rows(table, rows)?
        .into_iter()
        .map(|(_, row)| row.clone())
        .collect())
}

pub fn validate_bundle<R: LegacyRow>(bundle: &LegacyBundle<R>) -> Result<ImportReport, DataError> {
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
        let rows = ordered_rows(table, &bundle.tables[table])?;
        let digest = hash_rows(rows.iter().map(|(_, row)| *row))?;
        if bundle.table_sha256[table] != digest || !bundle.source_schema[table].is_array() {
            return Err(DataError::Reconciliation);
        }
        table_counts.insert(table.to_owned(), rows.len());
        table_sha256.insert(table.to_owned(), digest);
    }
    Ok(ImportReport {
        bundle_sha256: stream_ordered_sha256(bundle)?,
        table_counts,
        table_sha256,
        already_imported: false,
    })
}

fn hash_rows<'a, R: LegacyRow + 'a>(
    rows: impl Iterator<Item = &'a R>,
) -> Result<String, DataError> {
    let mut hash = HashWriter::default();
    hash.0.update(b"[");
    for (index, row) in rows.enumerate() {
        if index != 0 {
            hash.0.update(b",");
        }
        serde_json::to_writer(&mut hash, row.value()?.as_ref())
            .map_err(|_| DataError::InvalidInput)?;
    }
    hash.0.update(b"]");
    Ok(hash.finish())
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

pub async fn reconcile<R: LegacyRow>(
    db: &Db,
    bundle: &LegacyBundle<R>,
) -> Result<ImportReport, DataError> {
    let report = validate_bundle(bundle)?;
    let mut connection = db.connection().await?;
    AsyncPgConnection::transaction::<_, DataError, _>(&mut connection, async move |connection| {
        connection
            .batch_execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            .await?;
        for table in LEGACY_TABLES {
            reconcile_table(connection, table, &report).await?;
        }
        Ok(report)
    })
    .await
}

async fn reconcile_table(
    connection: &mut AsyncPgConnection,
    table: &str,
    report: &ImportReport,
) -> Result<(), DataError> {
    let mut rows = sql_query("SELECT row_key,payload FROM legacy_record WHERE table_name=$1 ORDER BY row_key COLLATE \"C\"")
        .bind::<Text, _>(table)
        .load_stream::<JsonRow>(connection)
        .await?;
    let mut hash = HashWriter::default();
    hash.0.update(b"[");
    let mut count = 0;
    let mut previous: Option<String> = None;
    while let Some(row) = rows.try_next().await? {
        if validate_row(table, &row.payload)? != row.row_key
            || previous.as_ref().is_some_and(|key| key >= &row.row_key)
        {
            return Err(DataError::Reconciliation);
        }
        if count != 0 {
            hash.0.update(b",");
        }
        serde_json::to_writer(&mut hash, &row.payload).map_err(|_| DataError::InvalidInput)?;
        previous = Some(row.row_key);
        count += 1;
    }
    hash.0.update(b"]");
    if count != report.table_counts[table] || hash.finish() != report.table_sha256[table] {
        return Err(DataError::Reconciliation);
    }
    Ok(())
}

pub async fn import_bundle<R: LegacyRow>(
    db: &Db,
    bundle: &LegacyBundle<R>,
) -> Result<ImportReport, DataError> {
    let report = validate_bundle(bundle)?;
    let mut connection = db.connection().await?;
    AsyncPgConnection::transaction::<_, DataError, _>(&mut connection, async move |connection| {
        sql_query("SELECT pg_advisory_xact_lock(731957311)")
            .execute(&mut *connection)
            .await?;
        #[derive(diesel::QueryableByName)]
        struct Present {
            #[diesel(sql_type=Bool)]
            present: bool,
        }
        let present = sql_query(
            "SELECT EXISTS(SELECT 1 FROM import_manifest WHERE bundle_sha256=$1) AS present",
        )
        .bind::<Text, _>(&report.bundle_sha256)
        .get_result::<Present>(&mut *connection)
        .await?;
        if present.present {
            return Ok(ImportReport {
                already_imported: true,
                ..report
            });
        }
        for table in LEGACY_TABLES {
            for (key, row) in ordered_rows(table, &bundle.tables[table])? {
                let row = row.value()?;
                let existing = sql_query(
                    "SELECT row_key,payload FROM legacy_record WHERE table_name=$1 AND row_key=$2",
                )
                .bind::<Text, _>(table)
                .bind::<Text, _>(&key)
                .load::<JsonRow>(&mut *connection)
                .await?;
                if let Some(existing) = existing.first() {
                    if &existing.payload != row.as_ref() {
                        return Err(DataError::Conflict);
                    }
                } else {
                    sql_query(
                        "INSERT INTO legacy_record(table_name,row_key,payload) VALUES($1,$2,$3)",
                    )
                    .bind::<Text, _>(table)
                    .bind::<Text, _>(key)
                    .bind::<Jsonb, _>(row.as_ref())
                    .execute(&mut *connection)
                    .await?;
                }
            }
            reconcile_table(connection, table, &report).await?;
        }
        import_safety(connection, bundle.safety_ledger.as_ref()).await?;
        #[derive(Serialize)]
        struct Manifest<'a, R: LegacyRow> {
            bundle: &'a LegacyBundle<R>,
            report: &'a ImportReport,
        }
        let provenance = serde_json::to_string(&Manifest {
            bundle,
            report: &report,
        })
        .map_err(|_| DataError::InvalidInput)?;
        sql_query("INSERT INTO import_manifest(bundle_sha256,manifest) VALUES($1,$2::jsonb)")
            .bind::<Text, _>(&report.bundle_sha256)
            .bind::<Text, _>(&provenance)
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
