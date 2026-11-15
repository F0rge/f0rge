pub mod support;
use buycycle_backend::{
    collector::{BLOCK_PAUSE, CollectionError, FEED_PAUSE, Gate, Source, SourceResponse, collect},
    contracts::Kind,
};
use chrono::{DateTime, Duration as Days, Utc};
use serde_json::json;
use std::{collections::VecDeque, sync::Mutex, time::Duration};
struct FakeSource {
    responses: Mutex<VecDeque<SourceResponse>>,
    pauses: Mutex<Vec<Duration>>,
    attempts: Mutex<usize>,
    now: DateTime<Utc>,
}
impl FakeSource {
    fn new(responses: Vec<SourceResponse>) -> Self {
        Self {
            responses: Mutex::new(responses.into()),
            pauses: Mutex::new(vec![]),
            attempts: Mutex::new(0),
            now: Utc::now(),
        }
    }
}
impl Source for FakeSource {
    async fn get(&self, _: &str) -> Result<SourceResponse, CollectionError> {
        *self.attempts.lock().unwrap() += 1;
        self.responses
            .lock()
            .unwrap()
            .pop_front()
            .ok_or(CollectionError::Incomplete)
    }
    async fn pause(&self, d: Duration) {
        self.pauses.lock().unwrap().push(d)
    }
    fn now(&self) -> DateTime<Utc> {
        self.now
    }
}
#[tokio::test]
async fn postgres_budget_is_global_persistent_crash_conservative_and_does_not_cross_midnight() {
    let (db, base, name) = support::database().await;
    let now = Utc::now();
    let mut first = Gate::acquire(&db, now).await.unwrap();
    assert!(matches!(
        Gate::acquire(&db, now).await,
        Err(CollectionError::Held)
    ));
    assert!(first.claim_feed(&Kind::Bikes, now).await.unwrap());
    assert!(!first.claim_feed(&Kind::Bikes, now).await.unwrap());
    assert!(first.claim_feed(&Kind::Wheels, now).await.unwrap());
    for _ in 0..149 {
        first.before_request(true, now).await.unwrap();
        first.finish().await.unwrap();
    }
    drop(first);
    tokio::task::yield_now().await;
    let mut second = Gate::acquire(&db, now).await.unwrap();
    second.before_request(true, now).await.unwrap();
    second.finish().await.unwrap();
    assert!(matches!(
        second.before_request(true, now).await,
        Err(CollectionError::Budget)
    ));
    assert!(matches!(
        second.before_request(false, now + Days::days(1)).await,
        Err(CollectionError::Held)
    ));
    drop(second);
    drop(db);
    support::drop_database(&base, &name).await;
}
#[tokio::test]
async fn pending_request_survives_crash_and_unknown_legacy_consumption_holds_activation_day() {
    let (db, base, name) = support::database().await;
    let now = Utc::now();
    let mut gate = Gate::acquire(&db, now).await.unwrap();
    gate.before_request(false, now).await.unwrap();
    drop(gate);
    tokio::task::yield_now().await;
    let mut again = Gate::acquire(&db, now).await.unwrap();
    assert!(matches!(
        again.before_request(false, now).await,
        Err(CollectionError::Held)
    ));
    drop(again);
    drop(db);
    support::drop_database(&base, &name).await;
    let (db, base, name) = support::database().await;
    db.upsert_rows(
        "listing",
        &[json!({"id":"legacy","kind":"bikes","price":1000})],
    )
    .await
    .unwrap();
    let mut held = Gate::acquire(&db, now).await.unwrap();
    assert!(matches!(
        held.before_request(false, now).await,
        Err(CollectionError::Held)
    ));
    drop(held);
    drop(db);
    support::drop_database(&base, &name).await;
}
#[tokio::test]
async fn upstream_block_is_persisted_before_single_backoff_and_never_retried() {
    for code in [403, 429] {
        let (db, base, name) = support::database().await;
        let source = FakeSource::new(vec![SourceResponse {
            status: code,
            body: String::new(),
        }]);
        assert_eq!(
            collect(
                &db,
                &source,
                "synthetic-key",
                vec![Kind::Bikes, Kind::Wheels]
            )
            .await,
            Err(CollectionError::Blocked)
        );
        assert_eq!(*source.attempts.lock().unwrap(), 1);
        assert_eq!(*source.pauses.lock().unwrap(), vec![BLOCK_PAUSE]);
        assert_eq!(
            collect(&db, &source, "synthetic-key", vec![Kind::Wheels]).await,
            Err(CollectionError::Held)
        );
        assert_eq!(*source.attempts.lock().unwrap(), 1);
        drop(db);
        support::drop_database(&base, &name).await;
    }
}
#[tokio::test]
async fn malformed_and_truncated_feeds_cannot_mark_old_listings_disappeared() {
    let (db, base, name) = support::database().await;
    // Establish a known ledger before adding observations; migration's unknown-usage hold is tested separately.
    drop(Gate::acquire(&db, Utc::now()).await.unwrap());
    tokio::task::yield_now().await;
    db.upsert_rows("listing",&[json!({"id":"retained","kind":"wheels","slug":"synthetic","name":"Synthetic Wheel","brand":"Synthetic","price":1000,"first_seen":"2026-01-01","last_seen":"2026-01-01","gone_at":null})]).await.unwrap();
    let body=json!({"response":{"results":[{"data":{"id":"new","slug":"new","brand_name":"Synthetic","price":500},"value":"Synthetic Wheel"}],"total_num_results":200}}).to_string();
    let source = FakeSource::new(vec![SourceResponse { status: 200, body }]);
    assert_eq!(
        collect(&db, &source, "synthetic-key", vec![Kind::Wheels]).await,
        Err(CollectionError::Incomplete)
    );
    assert_eq!(*source.pauses.lock().unwrap(), vec![FEED_PAUSE]);
    let rows = db.listings("wheels").await.unwrap();
    assert!(rows.iter().find(|r| r["id"] == "retained").unwrap()["gone_at"].is_null());
    assert_eq!(db.rows("runs").await.unwrap()[0]["complete"], 0);
    drop(db);
    support::drop_database(&base, &name).await;
}
#[test]
fn unrecognized_detail_does_not_claim_a_successful_fetch() {
    assert!(
        buycycle_backend::collector::parse_detail(
            "<html>unrecognized</html>",
            "id",
            "slug",
            "2026-11-15"
        )
        .is_err()
    );
}
#[tokio::test]
async fn retained_original_replay_is_read_only_reproducible_and_rejects_tampering() {
    use diesel::{
        sql_query,
        sql_types::{Jsonb, Text},
    };
    use diesel_async::RunQueryDsl;
    let (db, base, name) = support::database().await;
    let source = FakeSource::new(vec![SourceResponse {
        status: 200,
        body: json!({"response":{"results":[],"total_num_results":0}}).to_string(),
    }]);
    collect(&db, &source, "synthetic-key", vec![Kind::Wheels])
        .await
        .unwrap();
    #[derive(diesel::QueryableByName)]
    struct Run {
        #[diesel(sql_type=diesel::sql_types::Uuid)]
        id: uuid::Uuid,
    }
    let mut connection = db.connection().await.unwrap();
    let run = sql_query("SELECT id FROM collector_runs LIMIT 1")
        .get_result::<Run>(&mut connection)
        .await
        .unwrap()
        .id;
    let before = *source.attempts.lock().unwrap();
    let result = buycycle_backend::collector::replay(&db, run, false)
        .await
        .unwrap();
    assert_eq!(result["mode"], "original_replay");
    assert_eq!(result["result"]["kind"], "wheels");
    assert_eq!(*source.attempts.lock().unwrap(), before);
    sql_query("UPDATE source_snapshots SET payload=jsonb_set(payload,'{processing_digest}',$1) WHERE source_kind=$2").bind::<Jsonb,_>(json!("changed-processing-version")).bind::<Text,_>("replay").execute(&mut connection).await.unwrap();
    assert!(
        buycycle_backend::collector::replay(&db, run, false)
            .await
            .is_err()
    );
    drop(connection);
    drop(db);
    support::drop_database(&base, &name).await;
}
#[tokio::test]
async fn related_observation_publication_rolls_back_all_tables_on_a_real_database_failure() {
    use diesel::sql_query;
    use diesel_async::{RunQueryDsl, SimpleAsyncConnection};
    let (db, base, name) = support::database().await;
    let mut connection = db.connection().await.unwrap();
    connection.batch_execute("CREATE FUNCTION reject_synthetic_detail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.table_name='detail' AND NEW.payload->>'id'='synthetic-fault' THEN RAISE EXCEPTION 'synthetic storage failure'; END IF; RETURN NEW; END $$; CREATE TRIGGER reject_synthetic_detail BEFORE INSERT ON legacy_record FOR EACH ROW EXECUTE FUNCTION reject_synthetic_detail()").await.unwrap();
    let result = db
        .upsert_tables(&[
            (
                "listing",
                vec![json!({"id":"new","kind":"wheels","price":1000})],
            ),
            ("detail", vec![json!({"id":"synthetic-fault"})]),
        ])
        .await;
    assert!(result.is_err());
    assert!(db.rows("listing").await.unwrap().is_empty());
    assert!(db.rows("detail").await.unwrap().is_empty());
    sql_query("DROP TRIGGER reject_synthetic_detail ON legacy_record")
        .execute(&mut connection)
        .await
        .unwrap();
    db.upsert_tables(&[
        (
            "listing",
            vec![json!({"id":"new","kind":"wheels","price":1000})],
        ),
        ("detail", vec![json!({"id":"new"})]),
    ])
    .await
    .unwrap();
    assert_eq!(db.rows("listing").await.unwrap().len(), 1);
    assert_eq!(db.rows("detail").await.unwrap().len(), 1);
    drop(connection);
    drop(db);
    support::drop_database(&base, &name).await;
}
fn candidate_feed() -> String {
    let results:Vec<_>=[("cheap",1000),("a",3000),("b",3000),("c",3000)].into_iter().map(|(id,price)|json!({"data":{"id":id,"slug":id,"brand_name":"Synthetic","price":price,"country_id":150},"value":"Synthetic Carbon 50 Wheelset"})).collect();
    json!({"response":{"results":results,"total_num_results":4}}).to_string()
}
#[tokio::test]
async fn detail_http_or_parse_failure_preserves_feed_completion_but_reports_overall_partial() {
    for (status, body) in [(500, "failed"), (200, "unrecognized detail")] {
        let (db, base, name) = support::database().await;
        let source = FakeSource::new(vec![
            SourceResponse {
                status: 200,
                body: candidate_feed(),
            },
            SourceResponse {
                status,
                body: body.into(),
            },
        ]);
        assert_eq!(
            collect(&db, &source, "synthetic-key", vec![Kind::Wheels]).await,
            Err(CollectionError::Incomplete)
        );
        let run = db.rows("runs").await.unwrap().remove(0);
        assert_eq!(run["complete"], 1);
        assert_eq!(run["collection_complete"], 0);
        assert_eq!(run["fetched"], 0);
        let state = buycycle_backend::services::status(&db, "synthetic-user".into())
            .await
            .unwrap();
        assert_eq!(state.status, "partial");
        assert!(state.last_success.is_none());
        drop(db);
        support::drop_database(&base, &name).await;
    }
}
#[tokio::test]
async fn parsed_country_id_or_feed_fallback_updates_country_mapping_atomically() {
    for country_field in [",\"country_id\":150", ""] {
        let (db, base, name) = support::database().await;
        let full = format!(
            "{{\"id\":\"cheap\",\"slug\":\"cheap\",\"price\":1000,\"country\":\"Germany\"{country_field},\"seller\":{{}},\"images\":[]}}"
        );
        let html = format!(
            "self.__next_f.push([1,{}])</script>",
            serde_json::to_string(&full).unwrap()
        );
        let detail =
            buycycle_backend::collector::parse_detail(&html, "cheap", "cheap", "2026-11-15")
                .unwrap();
        if !country_field.is_empty() {
            assert_eq!(detail["country_id"], 150);
        }
        let source = FakeSource::new(vec![
            SourceResponse {
                status: 200,
                body: candidate_feed(),
            },
            SourceResponse {
                status: 200,
                body: html,
            },
        ]);
        collect(&db, &source, "synthetic-key", vec![Kind::Wheels])
            .await
            .unwrap();
        assert_eq!(
            db.rows("country_map").await.unwrap(),
            vec![json!({"cid":150,"country":"Germany"})]
        );
        let run = db.rows("runs").await.unwrap().remove(0);
        assert_eq!(run["collection_complete"], 1);
        assert_eq!(run["fetched"], 1);
        drop(db);
        support::drop_database(&base, &name).await;
    }
}
#[tokio::test]
async fn calculation_reads_one_repeatable_snapshot_during_concurrent_atomic_publication() {
    use buycycle_backend::persistence::Db;
    use tokio::sync::Barrier;

    async fn publish(db: &Db, version: i64) {
        db.upsert_tables(&[
            (
                "listing",
                vec![json!({"id":"same","kind":"bikes","version":version})],
            ),
            ("detail", vec![json!({"id":"same","version":version})]),
        ])
        .await
        .unwrap();
    }

    async fn snapshot_version(db: &Db) -> i64 {
        let snapshot = db
            .read_tables_snapshot(&["listing", "detail"])
            .await
            .unwrap();
        let listing = snapshot["listing"][0]["version"].as_i64().unwrap();
        let detail = snapshot["detail"][0]["version"].as_i64().unwrap();
        assert_eq!(
            listing, detail,
            "Reader straddled two atomically published versions"
        );
        let bounded = db.calculation_snapshot("bikes").await.unwrap();
        let listing = bounded.rows[0]["version"].as_i64().unwrap();
        assert_eq!(
            listing,
            bounded.details[0]["version"].as_i64().unwrap(),
            "Bounded calculation reader straddled two published versions"
        );
        listing
    }

    let (db, base, name) = support::database().await;
    publish(&db, 0).await;
    assert_eq!(snapshot_version(&db).await, 0);
    for round in 0..20 {
        let first = round * 8 + 1;
        let last = first + 7;
        let phase = Barrier::new(2);
        let writer = async {
            publish(&db, first).await;
            phase.wait().await; // Announce a committed epoch.
            phase.wait().await; // Keep it stable until the reader has observed it.
            for version in first + 1..=last {
                publish(&db, version).await;
            }
        };
        let reader = async {
            phase.wait().await;
            assert_eq!(snapshot_version(&db).await, first);
            phase.wait().await;
            let mut previous = first;
            for _ in 0..5 {
                let observed = snapshot_version(&db).await;
                assert!(
                    (previous..=last).contains(&observed),
                    "Sequential snapshots must stay monotonic within this publication round"
                );
                previous = observed;
            }
        };
        // Reads still race the remaining atomic publications. Progress is checked at
        // explicit synchronization points, independent of the executor's scheduling.
        tokio::join!(writer, reader);
        assert_eq!(snapshot_version(&db).await, last);
    }
    drop(db);
    support::drop_database(&base, &name).await;
}
#[tokio::test]
async fn echoed_feed_credentials_are_redacted_before_every_retained_and_derived_payload() {
    use diesel::{
        sql_query,
        sql_types::{Jsonb, Text, Uuid as SqlUuid},
    };
    use diesel_async::RunQueryDsl;
    const SECRET: &str = "synthetic-active-feed-credential-never-retain";
    const SECONDARY: &str = "synthetic-secondary-authorization-never-retain";
    #[derive(diesel::QueryableByName)]
    struct Snapshot {
        #[diesel(sql_type=Jsonb)]
        payload: serde_json::Value,
        #[diesel(sql_type=Text)]
        source_kind: String,
        #[diesel(sql_type=SqlUuid)]
        run_id: uuid::Uuid,
    }
    #[derive(diesel::QueryableByName)]
    struct Metadata {
        #[diesel(sql_type=Jsonb)]
        metadata: serde_json::Value,
    }
    for split in [false, true] {
        let (db, base, name) = support::database().await;
        let mut feed: serde_json::Value = serde_json::from_str(&candidate_feed()).unwrap();
        feed["request_metadata"] = json!({"key":SECRET,"url":format!("https://example.test/?key={SECRET}"),"headers":{"authorization":format!("Bearer {SECONDARY}")},"echo":[[format!("before-{SECRET}-after")]]});
        feed["response"]["business_key_holder"] = json!({"key":"keep-this-business-model-key"});
        for item in feed["response"]["results"].as_array_mut().unwrap() {
            item["value"] = json!(format!("Synthetic Carbon 50 Wheelset {SECRET}"));
            item["data"]["description"] = json!(format!("Unrelated descriptive text {SECRET}"));
            item["data"]["specifications"] = json!({"key":"keep-this-specification-key","business_note":format!("A business value echoing {SECRET}"),"nested":[{"echo":SECRET}]});
        }
        let product = json!({"id":"cheap","slug":"cheap","price":1000,"country":"Germany","country_id":150,"seller":{"member_since":format!("2020 {SECRET}")},"request":{"authorization":SECONDARY},"key":"keep-this-product-model-key","images":[]});
        let full = serde_json::to_string(&product).unwrap();
        let mut html = format!("<!-- outer echo {SECRET} -->");
        if split {
            let boundary = full.find(SECRET).unwrap() + SECRET.len() / 2;
            for chunk in [&full[..boundary], &full[boundary..]] {
                html.push_str(&format!(
                    "self.__next_f.push([1,{}])</script>",
                    serde_json::to_string(chunk).unwrap()
                ));
            }
        } else {
            html.push_str(&format!(
                "self.__next_f.push([1,{}])</script>",
                serde_json::to_string(&full).unwrap()
            ));
        }
        let source = FakeSource::new(vec![
            SourceResponse {
                status: 200,
                body: feed.to_string(),
            },
            SourceResponse {
                status: 200,
                body: html,
            },
        ]);
        collect(&db, &source, SECRET, vec![Kind::Wheels])
            .await
            .unwrap();
        let mut connection = db.connection().await.unwrap();
        let snapshots = sql_query(
            "SELECT payload,source_kind,run_id FROM source_snapshots ORDER BY recorded_at",
        )
        .load::<Snapshot>(&mut connection)
        .await
        .unwrap();
        let metadata = sql_query("SELECT metadata FROM collector_runs")
            .load::<Metadata>(&mut connection)
            .await
            .unwrap();
        for snapshot in &snapshots {
            let text = snapshot.payload.to_string();
            assert!(!text.contains(SECRET));
            assert!(!text.contains(SECONDARY));
        }
        for row in metadata {
            let text = row.metadata.to_string();
            assert!(!text.contains(SECRET));
            assert!(!text.contains(SECONDARY));
            assert_eq!(row.metadata["source_redaction_version"], 1);
        }
        let retained_feed = &snapshots
            .iter()
            .find(|r| r.source_kind == "feed")
            .unwrap()
            .payload;
        assert_eq!(
            retained_feed["response"]["business_key_holder"]["key"],
            "keep-this-business-model-key"
        );
        assert_eq!(
            retained_feed["response"]["results"][0]["data"]["specifications"]["key"],
            "keep-this-specification-key"
        );
        assert!(
            retained_feed["request_metadata"]["key"]
                .as_str()
                .unwrap()
                .contains("REDACTED")
        );
        assert!(
            retained_feed["request_metadata"]["headers"]["authorization"]
                .as_str()
                .unwrap()
                .contains("REDACTED")
        );
        for table in ["listing", "price_history", "detail", "runs", "country_map"] {
            for row in db.rows(table).await.unwrap() {
                let text = row.to_string();
                assert!(!text.contains(SECRET));
                assert!(!text.contains(SECONDARY));
            }
        }
        let listings = db.listings("wheels").await.unwrap();
        assert_eq!(listings.len(), 4);
        assert_eq!(db.rows("price_history").await.unwrap().len(), 4);
        assert!(listings.iter().any(|r| r["price"] == 1000));
        let detail = db.rows("detail").await.unwrap().remove(0);
        assert!(
            detail["member_since"]
                .as_str()
                .unwrap()
                .contains("REDACTED")
        );
        let replay = buycycle_backend::collector::replay(&db, snapshots[0].run_id, false)
            .await
            .unwrap();
        let text = replay.to_string();
        assert!(!text.contains(SECRET));
        assert!(!text.contains(SECONDARY));
        assert_eq!(replay["mode"], "original_replay");
        drop(connection);
        drop(db);
        support::drop_database(&base, &name).await;
    }
}
