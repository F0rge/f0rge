use std::collections::BTreeMap;

use buycycle_backend::{
    import::{
        LegacyBundle, canonical_rows, canonical_sha256, import_bundle, reconcile, validate_bundle,
    },
    persistence::{DataError, Db, LEGACY_TABLES},
};
use diesel::{sql_query, sql_types::BigInt};
use diesel_async::{AsyncConnection, AsyncPgConnection, RunQueryDsl, SimpleAsyncConnection};
use serde_json::{Value, json};

fn bundle() -> LegacyBundle {
    let tables:BTreeMap<String,Vec<Value>>=[
        ("listing",vec![json!({"id":"bike-1","kind":"bikes","name":"Synthetic café bicycle","price":1234,"first_seen":"2026-01-01","gone_at":null,"unknown_future_column":null}),json!({"id":"wheel-1","kind":"wheels","price":450,"gone_at":"2026-01-02"})]),
        ("price_history",vec![json!({"id":"bike-1","day":"2026-01-01","price":1500}),json!({"id":"bike-1","day":"2026-01-02","price":1234})]),
        ("detail",vec![json!({"id":"bike-1","seller_rating":"4.9","shipping":null,"bp":"12.00"})]),
        ("runs",vec![json!({"day":"2026-01-01","kind":"bikes","complete":0,"n":1,"note":"interrupted"})]),
        ("country_map",vec![json!({"cid":150,"country":"Germany"})]),
    ].into_iter().map(|(name,rows)|(name.to_owned(),rows)).collect();
    let table_sha256 = tables
        .iter()
        .map(|(table, rows)| {
            (
                table.clone(),
                canonical_sha256(&canonical_rows(table, rows).unwrap()).unwrap(),
            )
        })
        .collect();
    LegacyBundle {
        version: 1,
        exported_at: "2026-01-02T00:00:00Z".into(),
        processing_version: "synthetic-source-revision".into(),
        tables,
        table_sha256,
        source_schema: LEGACY_TABLES
            .into_iter()
            .map(|name| (name.to_owned(), json!([])))
            .collect(),
        safety_ledger: None,
    }
}

#[test]
fn validation_rejects_duplicates_unknown_tables_hash_changes_and_bad_ledger() {
    let original = bundle();
    assert!(validate_bundle(&original).is_ok());
    let mut bad = original.clone();
    let duplicate = bad.tables["listing"][0].clone();
    bad.tables.get_mut("listing").unwrap().push(duplicate);
    assert_eq!(validate_bundle(&bad).unwrap_err(), DataError::InvalidInput);
    let mut bad = original.clone();
    bad.tables.insert("not_in_source_schema".into(), vec![]);
    assert_eq!(validate_bundle(&bad).unwrap_err(), DataError::InvalidInput);
    let mut bad = original.clone();
    bad.tables.get_mut("listing").unwrap()[0]["price"] = json!(1235);
    assert_eq!(
        validate_bundle(&bad).unwrap_err(),
        DataError::Reconciliation
    );
    let mut bad = original.clone();
    bad.safety_ledger = Some(
        json!({"version":1,"day":"2026-01-01","detail_attempts":151,"blocked":false,"pending":false,"feeds":[]}),
    );
    assert_eq!(validate_bundle(&bad).unwrap_err(), DataError::InvalidInput);
    let mut bad = original;
    bad.tables.get_mut("listing").unwrap()[0]["price"] = json!(12.5);
    assert_eq!(validate_bundle(&bad).unwrap_err(), DataError::InvalidInput);
}

#[derive(diesel::QueryableByName)]
struct Count {
    #[diesel(sql_type=BigInt)]
    n: i64,
}

#[tokio::test]
async fn actual_postgres_import_reconciles_repeats_rolls_back_and_preserves_edits() {
    let base = std::env::var("BUYCYCLE_TEST_DATABASE_URL")
        .expect("Set BUYCYCLE_TEST_DATABASE_URL to a disposable PostgreSQL rehearsal database");
    let mut url = reqwest::Url::parse(&base).expect("Valid rehearsal URL");
    assert!(
        url.path().contains("test") || url.path().contains("rehearsal"),
        "Refuse a non-rehearsal database"
    );
    assert!(
        [
            "127.0.0.1",
            "localhost",
            "postgres",
            "db",
            "buycycle-postgres"
        ]
        .contains(&url.host_str().unwrap_or("")),
        "Only disposable local/Compose PostgreSQL is allowed"
    );
    let database = format!("buycycle_test_{}", uuid::Uuid::new_v4().simple());
    let mut admin = AsyncPgConnection::establish(&base)
        .await
        .expect("Disposable PostgreSQL is required");
    sql_query(format!("CREATE DATABASE {database}"))
        .execute(&mut admin)
        .await
        .unwrap();
    url.set_path(&database);
    let db = Db::connect(url.as_str()).await.unwrap();
    assert!(db.health().await.is_err());
    db.migrate().await.unwrap();
    db.migrate().await.unwrap();
    db.health().await.unwrap();
    let original = bundle();
    let report = import_bundle(&db, &original).await.unwrap();
    assert!(!report.already_imported);
    assert_eq!(report.table_counts["listing"], 2);
    assert_eq!(
        reconcile(&db, &original).await.unwrap().table_sha256,
        report.table_sha256
    );
    assert!(
        import_bundle(&db, &original)
            .await
            .unwrap()
            .already_imported
    );
    assert_eq!(db.listings("wheels").await.unwrap().len(), 1);
    let mut conflict = original.clone();
    conflict.tables.get_mut("listing").unwrap()[0]["price"] = json!(999);
    conflict.table_sha256.insert(
        "listing".into(),
        canonical_sha256(&canonical_rows("listing", &conflict.tables["listing"]).unwrap()).unwrap(),
    );
    assert_eq!(
        import_bundle(&db, &conflict).await.unwrap_err(),
        DataError::Conflict
    );
    assert_eq!(
        reconcile(&db, &original).await.unwrap().table_sha256,
        report.table_sha256
    );

    let start = db.user_state("person-a").await.unwrap();
    assert_eq!(start.revision, 0);
    let state = json!({"version":1,"bikes":{"watch":{"bike-1":{"n":"Retained","p":1234}},"log":[{"name":"Trade","buy":1000,"sell":0,"bd":"2026-01-01","sd":""}],"costs":{"buffer":40}},"wheels":{"watch":{},"log":[],"costs":{"shipin":12}}});
    let imported = db
        .import_browser_state(
            "person-a",
            0,
            &state,
            &json!({"origin":"synthetic-browser","state":state}),
        )
        .await
        .unwrap();
    assert_eq!(imported.state, state);
    assert_eq!(
        db.import_browser_state(
            "person-a",
            0,
            &state,
            &json!({"origin":"synthetic-browser","state":state})
        )
        .await
        .unwrap()
        .revision,
        1
    );
    let mut changed = state.clone();
    changed["bikes"]["costs"]["buffer"] = json!(50);
    let saved = db
        .compare_and_swap_state("person-a", 1, changed.clone())
        .await
        .unwrap();
    assert_eq!(saved.revision, 2);
    assert_eq!(
        db.compare_and_swap_state("person-a", 1, state.clone())
            .await
            .unwrap_err(),
        DataError::Conflict
    );
    assert_eq!(
        db.import_browser_state(
            "person-a",
            0,
            &state,
            &json!({"origin":"synthetic-browser","state":state})
        )
        .await
        .unwrap_err(),
        DataError::Conflict
    );
    assert_eq!(db.user_state("person-a").await.unwrap().state, changed);
    assert_eq!(db.user_state("person-b").await.unwrap().revision, 0);
    let mut connection = db.connection().await.unwrap();
    assert_eq!(
        sql_query("SELECT count(*) AS n FROM user_state_history")
            .get_result::<Count>(&mut connection)
            .await
            .unwrap()
            .n,
        2
    );
    assert_eq!(
        sql_query(
            "SELECT count(*) AS n FROM collection_day WHERE blocked=true AND detail_attempts=150"
        )
        .get_result::<Count>(&mut connection)
        .await
        .unwrap()
        .n,
        1
    );
    assert_eq!(
        sql_query("SELECT count(*) AS n FROM browser_import")
            .get_result::<Count>(&mut connection)
            .await
            .unwrap()
            .n,
        1
    );
    let runtime_role = format!("buycycle_runtime_{}", uuid::Uuid::new_v4().simple());
    sql_query(format!("CREATE ROLE {runtime_role} LOGIN PASSWORD 'synthetic-isolation-only' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT"))
        .execute(&mut admin).await.unwrap();
    sql_query(format!("GRANT USAGE ON SCHEMA public TO {runtime_role}"))
        .execute(&mut connection)
        .await
        .unwrap();
    connection
        .batch_execute(
            &include_str!("../../ops/grant-runtime.sql").replace("buycycle_runtime", &runtime_role),
        )
        .await
        .unwrap();
    sql_query(format!("SET ROLE {runtime_role}"))
        .execute(&mut connection)
        .await
        .unwrap();
    assert_eq!(
        sql_query("SELECT count(*) AS n FROM legacy_record")
            .get_result::<Count>(&mut connection)
            .await
            .unwrap()
            .n,
        7
    );
    assert!(
        sql_query("CREATE TABLE should_not_exist(id int)")
            .execute(&mut connection)
            .await
            .is_err()
    );
    assert!(
        sql_query("TRUNCATE legacy_record")
            .execute(&mut connection)
            .await
            .is_err()
    );
    assert!(
        sql_query("UPDATE user_state_history SET state='{}'::jsonb")
            .execute(&mut connection)
            .await
            .is_err()
    );
    assert!(
        sql_query("DELETE FROM browser_import")
            .execute(&mut connection)
            .await
            .is_err()
    );
    assert!(
        sql_query("UPDATE import_manifest SET manifest='{}'::jsonb")
            .execute(&mut connection)
            .await
            .is_err()
    );
    sql_query("RESET ROLE")
        .execute(&mut connection)
        .await
        .unwrap();
    let unrelated = format!("other_app_test_{}", uuid::Uuid::new_v4().simple());
    sql_query(format!("CREATE DATABASE {unrelated}"))
        .execute(&mut admin)
        .await
        .unwrap();
    sql_query(format!("REVOKE ALL ON DATABASE {unrelated} FROM PUBLIC"))
        .execute(&mut admin)
        .await
        .unwrap();
    let mut denied_url = url.clone();
    denied_url.set_path(&unrelated);
    denied_url.set_username(&runtime_role).unwrap();
    denied_url
        .set_password(Some("synthetic-isolation-only"))
        .unwrap();
    assert!(
        AsyncPgConnection::establish(denied_url.as_str())
            .await
            .is_err()
    );
    sql_query(format!("DROP DATABASE {unrelated} WITH (FORCE)"))
        .execute(&mut admin)
        .await
        .unwrap();
    drop(connection);
    drop(db);
    sql_query(format!("DROP DATABASE {database} WITH (FORCE)"))
        .execute(&mut admin)
        .await
        .unwrap();
    sql_query(format!("DROP ROLE {runtime_role}"))
        .execute(&mut admin)
        .await
        .unwrap();
}
