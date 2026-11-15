//! Complete replay documents use canonical text inside a closed JSONB envelope.
//! JSONB must not reinterpret report numbers (notably -0.0), and neither capture
//! nor replay may materialize the complete history/report as a Value tree.
use std::{
    collections::BTreeMap,
    fmt,
    io::{self, Write},
};

use diesel::{
    sql_query,
    sql_types::{BigInt, Bool, Text, Uuid as SqlUuid},
};
use diesel_async::{AsyncConnection, AsyncPgConnection, RunQueryDsl, SimpleAsyncConnection};
use serde::{
    Deserialize, Serialize,
    de::{MapAccess, SeqAccess, Visitor},
    ser::{Error as _, SerializeMap, SerializeSeq},
};
use serde_json::{Value, value::RawValue};
use sha2::{Digest, Sha256};
use uuid::Uuid;

use crate::{
    collector::CollectionError,
    contracts::*,
    import::{CanonicalRows, stream_ordered_sha256},
    metrics::{self, CalculationInput},
    persistence::{DataError, Db},
};

const ENCODING: &str = "f0rge.buycycle.replay.canonical-json.v1";
// Explicit failure bounds, never retention/deletion rules. The real-data
// rehearsal must establish capacity below these bounds before a release.
const MAX_DOCUMENT_BYTES: usize = 256 * 1024 * 1024;
const MAX_DEPTH: usize = 128;
const MAX_ARRAY_ELEMENTS: usize = 2_000_000;
const MAX_OBJECT_MEMBERS: usize = 16_384;
const MAX_KEY_BYTES: usize = 4096;
type RawInput = CalculationInput<Box<RawValue>>;

// Value equality treats float signed zeros as equal, but keeps integer and
// floating-point numbers distinct. This applies ONLY to expected/result
// comparison, never archive serialization or its authenticated canonical hash.
fn comparison_zeros(value: &mut Value) {
    match value {
        Value::Number(number) if number.is_f64() && number.as_f64() == Some(0.) => {
            *value = serde_json::json!(0.0);
        }
        Value::Array(values) => values.iter_mut().for_each(comparison_zeros),
        Value::Object(values) => values.values_mut().for_each(comparison_zeros),
        _ => {}
    }
}

fn comparison_report(report: &ListingsResponse) -> CanonicalReport<'_> {
    let mut value = CanonicalReport::from(report);
    value.alerts.1 = true;
    value.items.1 = true;
    value.models.1 = true;
    value.quarantined.1 = true;
    value
}

struct CanonicalItems<'a, T>(&'a [T], bool);
impl<T: Serialize> Serialize for CanonicalItems<'_, T> {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        let mut sequence = serializer.serialize_seq(Some(self.0.len()))?;
        for item in self.0 {
            let mut value = serde_json::to_value(item).map_err(S::Error::custom)?;
            if self.1 {
                comparison_zeros(&mut value);
            }
            sequence.serialize_element(&value)?;
        }
        sequence.end()
    }
}

// Declaration order is deliberately alphabetical, matching the old Value
// canonicalization. Individual output items normalize nested objects as before.
#[derive(Serialize)]
struct CanonicalReport<'a> {
    active: usize,
    alerts: CanonicalItems<'a, Alert>,
    generated: &'a str,
    gone: usize,
    items: CanonicalItems<'a, Listing>,
    kind: &'a Kind,
    models: CanonicalItems<'a, ModelMarket>,
    quarantined: CanonicalItems<'a, QuarantinedListing>,
    today: &'a str,
}
impl<'a> From<&'a ListingsResponse> for CanonicalReport<'a> {
    fn from(report: &'a ListingsResponse) -> Self {
        Self {
            active: report.active,
            alerts: CanonicalItems(&report.alerts, false),
            generated: &report.generated,
            gone: report.gone,
            items: CanonicalItems(&report.items, false),
            kind: &report.kind,
            models: CanonicalItems(&report.models, false),
            quarantined: CanonicalItems(&report.quarantined, false),
            today: &report.today,
        }
    }
}
#[derive(Serialize)]
struct CanonicalInput<'a> {
    calculated_at: &'a chrono::DateTime<chrono::Utc>,
    countries: CanonicalRows<'a, Value>,
    details: CanonicalRows<'a, Value>,
    history: CanonicalRows<'a, Box<RawValue>>,
    kind: &'a Kind,
    rows: CanonicalRows<'a, Value>,
    runs: CanonicalRows<'a, Value>,
}
impl<'a> From<&'a RawInput> for CanonicalInput<'a> {
    fn from(input: &'a RawInput) -> Self {
        Self {
            calculated_at: &input.calculated_at,
            countries: CanonicalRows(&input.countries),
            details: CanonicalRows(&input.details),
            history: CanonicalRows(&input.history),
            kind: &input.kind,
            rows: CanonicalRows(&input.rows),
            runs: CanonicalRows(&input.runs),
        }
    }
}
#[derive(Serialize)]
struct CanonicalReplay<'a> {
    expected: CanonicalReport<'a>,
    input: CanonicalInput<'a>,
    processing_digest: &'a str,
}

struct LimitedWriter {
    bytes: Vec<u8>,
    limit: usize,
}
impl Write for LimitedWriter {
    fn write(&mut self, bytes: &[u8]) -> io::Result<usize> {
        if self.bytes.len().saturating_add(bytes.len()) > self.limit {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                "Replay document exceeds the supported byte bound",
            ));
        }
        self.bytes.extend_from_slice(bytes);
        Ok(bytes.len())
    }
    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}
fn document(
    input: &RawInput,
    expected: &ListingsResponse,
    digest: &str,
) -> Result<(String, String), CollectionError> {
    let mut writer = LimitedWriter {
        bytes: Vec::new(),
        limit: MAX_DOCUMENT_BYTES,
    };
    serde_json::to_writer(
        &mut writer,
        &CanonicalReplay {
            expected: expected.into(),
            input: input.into(),
            processing_digest: digest,
        },
    )
    .map_err(|_| CollectionError::Incomplete)?;
    let hash = format!("{:x}", Sha256::digest(&writer.bytes));
    let text = String::from_utf8(writer.bytes).map_err(|_| CollectionError::Incomplete)?;
    Ok((text, hash))
}

pub(crate) async fn capture(
    connection: &mut AsyncPgConnection,
    run: Uuid,
    kind: &Kind,
    input: RawInput,
    expected: ListingsResponse,
    digest: &str,
) -> Result<(), CollectionError> {
    let (text, hash) = document(&input, &expected, digest)?;
    // Release the source and calculated response before the SQL driver encodes
    // its text parameter. PostgreSQL parses only this small envelope and string.
    drop(input);
    drop(expected);
    sql_query("INSERT INTO source_snapshots(id,run_id,kind,source_kind,sha256,payload) VALUES($1,$2,$3,'replay',$4,jsonb_build_object('encoding',$5::text,'document',$6::text))")
        .bind::<SqlUuid,_>(Uuid::new_v4()).bind::<SqlUuid,_>(run).bind::<Text,_>(kind.as_str())
        .bind::<Text,_>(hash).bind::<Text,_>(ENCODING).bind::<Text,_>(text).execute(connection).await?;
    Ok(())
}

enum Members<'a> {
    Object(BTreeMap<String, &'a RawValue>),
    Array(Vec<&'a RawValue>),
}
impl<'de> Deserialize<'de> for Members<'de> {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct BoundedVisitor;
        impl<'de> Visitor<'de> for BoundedVisitor {
            type Value = Members<'de>;
            fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
                formatter.write_str("a bounded JSON object or array")
            }
            fn visit_map<M: MapAccess<'de>>(self, mut map: M) -> Result<Self::Value, M::Error> {
                let mut values = BTreeMap::new();
                while let Some((key, value)) = map.next_entry::<String, &'de RawValue>()? {
                    if key.len() > MAX_KEY_BYTES
                        || (!values.contains_key(&key) && values.len() >= MAX_OBJECT_MEMBERS)
                    {
                        return Err(serde::de::Error::custom(
                            "Replay object exceeds supported bounds",
                        ));
                    }
                    values.insert(key, value);
                }
                Ok(Members::Object(values))
            }
            fn visit_seq<A: SeqAccess<'de>>(self, mut array: A) -> Result<Self::Value, A::Error> {
                let mut values = Vec::new();
                while let Some(value) = array.next_element::<&'de RawValue>()? {
                    if values.len() >= MAX_ARRAY_ELEMENTS {
                        return Err(serde::de::Error::custom(
                            "Replay array exceeds supported bounds",
                        ));
                    }
                    values.push(value);
                }
                Ok(Members::Array(values))
            }
        }
        deserializer.deserialize_any(BoundedVisitor)
    }
}
struct CanonicalRaw<'a> {
    value: &'a RawValue,
    depth: usize,
    comparison: bool,
}
impl Serialize for CanonicalRaw<'_> {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        if self.depth > MAX_DEPTH {
            return Err(S::Error::custom(
                "Replay nesting exceeds the supported bound",
            ));
        }
        let text = self.value.get().trim();
        if matches!(text.as_bytes().first(), Some(b'{' | b'[')) {
            let members: Members<'_> = serde_json::from_str(text).map_err(S::Error::custom)?;
            match members {
                Members::Object(values) => {
                    let mut map = serializer.serialize_map(Some(values.len()))?;
                    for (key, value) in values {
                        map.serialize_entry(
                            &key,
                            &Self {
                                value,
                                depth: self.depth + 1,
                                comparison: self.comparison,
                            },
                        )?;
                    }
                    map.end()
                }
                Members::Array(values) => {
                    let mut array = serializer.serialize_seq(Some(values.len()))?;
                    for value in values {
                        array.serialize_element(&Self {
                            value,
                            depth: self.depth + 1,
                            comparison: self.comparison,
                        })?;
                    }
                    array.end()
                }
            }
        } else {
            let mut value: Value = serde_json::from_str(text).map_err(S::Error::custom)?;
            if self.comparison {
                comparison_zeros(&mut value);
            }
            value.serialize(serializer)
        }
    }
}

#[derive(diesel::QueryableByName)]
struct SavedDocument {
    #[diesel(sql_type=Text)]
    document: String,
    #[diesel(sql_type=Text)]
    sha256: String,
    #[diesel(sql_type=Bool)]
    encoded: bool,
}
#[derive(Deserialize)]
struct ReplaySections<'a> {
    #[serde(borrow)]
    input: &'a RawValue,
    #[serde(borrow)]
    expected: &'a RawValue,
    #[serde(borrow)]
    processing_digest: &'a str,
}
fn serialize_report<S: serde::Serializer>(
    report: &ListingsResponse,
    serializer: S,
) -> Result<S::Ok, S::Error> {
    CanonicalReport::from(report).serialize(serializer)
}
/// Fully verified, owned output. Callers may stream this without a Value tree.
#[derive(Serialize)]
pub struct VerifiedReplay {
    pub mode: &'static str,
    pub processing_digest: String,
    #[serde(serialize_with = "serialize_report")]
    pub result: ListingsResponse,
    pub source_run_id: Uuid,
}

pub(crate) async fn verify(
    db: &Db,
    run: Uuid,
    recalculate: bool,
    digest: String,
) -> Result<VerifiedReplay, CollectionError> {
    let mut connection = db.connection().await?;
    let saved=AsyncPgConnection::transaction::<_,DataError,_>(&mut connection,async move |connection| {
        connection.batch_execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY").await?;
        // Legacy direct objects retain their complete JSONB value, including
        // unknown outer metadata. New envelopes must have exactly two keys.
        // Materialize the extracted document once: inlining repeats the large
        // detoast/decoding expression for both bounds and the returned column.
        let records=sql_query("WITH candidate AS (SELECT payload,sha256 FROM source_snapshots WHERE run_id=$1 AND source_kind='replay' ORDER BY recorded_at DESC LIMIT 1), documents AS MATERIALIZED (SELECT sha256, (payload ? 'input') IS NOT TRUE AS encoded, CASE WHEN jsonb_typeof(payload)='object' THEN CASE WHEN payload ? 'input' THEN payload::text WHEN payload->>'encoding'=$2 AND jsonb_typeof(payload->'document')='string' AND (SELECT count(*) FROM jsonb_object_keys(payload))=2 THEN payload->>'document' ELSE NULL END ELSE NULL END AS document FROM candidate) SELECT document,sha256,encoded FROM documents WHERE octet_length(document) BETWEEN 1 AND $3")
            .bind::<SqlUuid,_>(run).bind::<Text,_>(ENCODING).bind::<BigInt,_>(MAX_DOCUMENT_BYTES as i64).load::<SavedDocument>(connection).await?;
        Ok(records.into_iter().next())
    }).await?.ok_or(CollectionError::Incomplete)?;
    drop(connection);
    let SavedDocument {
        document,
        sha256,
        encoded,
    } = saved;
    let raw: &RawValue =
        serde_json::from_str(&document).map_err(|_| CollectionError::Incomplete)?;
    let canonical = stream_ordered_sha256(&CanonicalRaw {
        value: raw,
        depth: 0,
        comparison: false,
    })
    .map_err(|_| CollectionError::Incomplete)?;
    if canonical != sha256
        || (encoded && format!("{:x}", Sha256::digest(document.as_bytes())) != sha256)
    {
        return Err(CollectionError::Incomplete);
    }
    let sections: ReplaySections<'_> =
        serde_json::from_str(&document).map_err(|_| CollectionError::Incomplete)?;
    if !recalculate && sections.processing_digest != digest {
        return Err(CollectionError::Incomplete);
    }
    let expected_hash = stream_ordered_sha256(&CanonicalRaw {
        value: sections.expected,
        depth: 0,
        comparison: true,
    })
    .map_err(|_| CollectionError::Incomplete)?;
    let input: RawInput =
        serde_json::from_str(sections.input.get()).map_err(|_| CollectionError::Incomplete)?;
    drop(document);
    let result = metrics::report_raw(input);
    if !recalculate
        && stream_ordered_sha256(&comparison_report(&result))
            .map_err(|_| CollectionError::Incomplete)?
            != expected_hash
    {
        return Err(CollectionError::Incomplete);
    }
    Ok(VerifiedReplay {
        mode: if recalculate {
            "new_recalculation"
        } else {
            "original_replay"
        },
        processing_digest: digest,
        result,
        source_run_id: run,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn raw(text: &str) -> &RawValue {
        serde_json::from_str(text).unwrap()
    }
    fn hash(text: &str, comparison: bool) -> Result<String, DataError> {
        stream_ordered_sha256(&CanonicalRaw {
            value: raw(text),
            depth: 0,
            comparison,
        })
    }

    #[test]
    fn streamed_document_matches_original_value_bytes_and_hash() {
        let fixture: Value =
            serde_json::from_str(include_str!("../tests/metrics-golden.json")).unwrap();
        for kind in [Kind::Bikes, Kind::Wheels] {
            let rows = |name: &str| fixture["tables"][name].as_array().unwrap().clone();
            let mut input = RawInput {
                kind,
                calculated_at: "2026-10-17T12:00:00Z".parse().unwrap(),
                rows: rows("listing"),
                details: rows("detail"),
                countries: rows("country_map"),
                runs: rows("runs"),
                history: rows("price_history")
                    .iter()
                    .map(|row| serde_json::value::to_raw_value(row).unwrap())
                    .collect(),
            };
            input.rows[0]["unknown_future_column"] = serde_json::json!("café 🚲");
            input.rows[0]["nullable"] = Value::Null;
            let mut expected = metrics::report_raw_borrowed(&input);
            expected.items[0].z_score = Some(-0.0);
            let digest = "a".repeat(64);
            let old = serde_json::json!({"input":&input,"expected":&expected,"processing_digest":&digest});
            let (text, sha) = document(&input, &expected, &digest).unwrap();
            assert_eq!(text.as_bytes(), serde_json::to_vec(&old).unwrap());
            assert_eq!(sha, crate::import::canonical_sha256(&old).unwrap());
            assert!(text.contains("-0.0"));
            assert_eq!(sha, hash(&text, false).unwrap());
        }
    }

    #[test]
    fn raw_canonical_hash_preserves_original_numbers_unicode_and_unknown_metadata() {
        for text in [
            r#"{"unknown":{"café":"🚲","nullable":null},"values":[-0.0,0.0,1.0,1e6,1e-6,123456.789,9223372036854775807]}"#,
            r#"{"b":[{"z":1,"a":"line\nquote\""}],"a":true,"duplicate":1,"duplicate":2}"#,
        ] {
            let old: Value = serde_json::from_str(text).unwrap();
            assert_eq!(
                hash(text, false).unwrap(),
                crate::import::canonical_sha256(&old).unwrap()
            );
        }
        assert_ne!(hash("-0.0", false).unwrap(), hash("0.0", false).unwrap());
    }

    #[test]
    fn comparison_matches_value_equality_without_changing_archive_integrity() {
        let cases = [
            "-0.0",
            "0.0",
            "0",
            "1.0",
            "1",
            "1e-6",
            r#"{"nested":[-0.0]}"#,
            r#"{"nested":[0.0]}"#,
        ];
        for first in cases {
            for second in cases {
                let a: Value = serde_json::from_str(first).unwrap();
                let b: Value = serde_json::from_str(second).unwrap();
                assert_eq!(
                    hash(first, true).unwrap() == hash(second, true).unwrap(),
                    a == b,
                    "{first} vs {second}"
                );
            }
        }
        assert_ne!(hash("-0.0", false).unwrap(), hash("0.0", false).unwrap());
    }

    #[test]
    fn resource_bounds_refuse_without_publishing_or_truncating() {
        let mut writer = LimitedWriter {
            bytes: Vec::new(),
            limit: 4,
        };
        writer.write_all(b"1234").unwrap();
        assert!(writer.write_all(b"5").is_err());
        assert_eq!(writer.bytes, b"1234");
        let deep = format!(
            "{}0{}",
            "[".repeat(MAX_DEPTH + 2),
            "]".repeat(MAX_DEPTH + 2)
        );
        if let Ok(value) = serde_json::from_str::<&RawValue>(&deep) {
            assert!(
                stream_ordered_sha256(&CanonicalRaw {
                    value,
                    depth: 0,
                    comparison: false
                })
                .is_err()
            );
        }
        let key = "k".repeat(MAX_KEY_BYTES + 1);
        assert!(hash(&serde_json::json!({key:1}).to_string(), false).is_err());
        let object: BTreeMap<_, _> = (0..MAX_OBJECT_MEMBERS + 1)
            .map(|i| (i.to_string(), 0))
            .collect();
        assert!(hash(&serde_json::to_string(&object).unwrap(), false).is_err());
        let array = format!("[{}0]", "0,".repeat(MAX_ARRAY_ELEMENTS));
        assert!(hash(&array, false).is_err());
    }
}
