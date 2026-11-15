pub mod support;
use actix_web::{App, test as web_test, web};
use buycycle_backend::{contracts::BrowserState, http};
use serde_json::{Value, json};
#[actix_web::test]
async fn unread_report_blocks_the_next_report_until_drain_or_disconnect_but_not_health() {
    let (db, base, name) = support::database().await;
    let (auth, handle, issuer) = support::setup().await;
    let jwt = support::signed(support::claims(&issuer));
    let app = web_test::init_service(
        App::new()
            .app_data(web::Data::new(db.clone()))
            .app_data(web::Data::new(auth))
            .configure(http::configure),
    )
    .await;
    let request = || {
        web_test::TestRequest::get()
            .uri("/api/v1/listings?kind=bikes")
            .insert_header(("Cf-Access-Jwt-Assertion", jwt.clone()))
            .to_request()
    };
    for disconnect in [false, true] {
        let first = web_test::call_service(&app, request()).await;
        assert_eq!(first.status(), 200);
        let next = web_test::call_service(&app, request());
        tokio::pin!(next);
        assert!(
            tokio::time::timeout(std::time::Duration::from_millis(50), &mut next)
                .await
                .is_err(),
            "an unread report must retain the capacity permit"
        );
        for path in ["/health", "/ready", "/api/v1/status"] {
            let health = web_test::call_service(
                &app,
                web_test::TestRequest::get()
                    .uri(path)
                    .insert_header(("Cf-Access-Jwt-Assertion", jwt.clone()))
                    .to_request(),
            )
            .await;
            assert_eq!(health.status(), 200);
            let _: Value = web_test::read_body_json(health).await;
        }
        if disconnect {
            drop(first);
        } else {
            let payload: Value = web_test::read_body_json(first).await;
            assert!(payload["items"].as_array().unwrap().is_empty());
        }
        let next = tokio::time::timeout(std::time::Duration::from_secs(5), &mut next)
            .await
            .expect("drain or disconnect must release capacity");
        assert_eq!(next.status(), 200);
        let _: Value = web_test::read_body_json(next).await;
    }
    drop(app);
    drop(db);
    handle.stop(true).await;
    support::drop_database(&base, &name).await;
}
#[actix_web::test]
async fn postgres_api_enforces_access_validation_revision_conflicts_and_import_recovery() {
    let (db, base, name) = support::database().await;
    let (auth, handle, issuer) = support::setup().await;
    let jwt = support::signed(support::claims(&issuer));
    let app = web_test::init_service(
        App::new()
            .app_data(web::Data::new(db.clone()))
            .app_data(web::Data::new(auth))
            .configure(http::configure),
    )
    .await;
    let res = web_test::call_service(
        &app,
        web_test::TestRequest::get().uri("/health").to_request(),
    )
    .await;
    assert_eq!(res.status(), 200);
    let res = web_test::call_service(
        &app,
        web_test::TestRequest::get()
            .uri("/api/v1/state")
            .insert_header(("Cf-Access-Authenticated-User-Email", "leo@example.test"))
            .to_request(),
    )
    .await;
    assert_eq!(res.status(), 401);
    let req = web_test::TestRequest::get()
        .uri("/api/v1/state")
        .insert_header(("Cf-Access-Jwt-Assertion", jwt.clone()))
        .insert_header(("X-Buycycle-Expected-Identity", format!("{issuer}|person-1")))
        .to_request();
    let got: Value = web_test::call_and_read_body_json(&app, req).await;
    assert_eq!(got["revision"], 0);
    assert_eq!(got["state"]["bikes"]["costs"]["sellfee"], 6.95);
    assert_eq!(got["state"]["wheels"]["costs"]["bp"], 6.);
    let state = got["state"].clone();
    let req = web_test::TestRequest::put()
        .uri("/api/v1/state")
        .insert_header(("Cf-Access-Jwt-Assertion", jwt.clone()))
        .insert_header(("X-Buycycle-Expected-Identity", format!("{issuer}|person-1")))
        .set_json(json!({"expected_revision":0,"state":state}))
        .to_request();
    let saved: Value = web_test::call_and_read_body_json(&app, req).await;
    assert_eq!(saved["revision"], 1);
    let req = web_test::TestRequest::put()
        .uri("/api/v1/state")
        .insert_header(("Cf-Access-Jwt-Assertion", jwt.clone()))
        .insert_header(("X-Buycycle-Expected-Identity", format!("{issuer}|person-1")))
        .set_json(json!({"expected_revision":0,"state":state}))
        .to_request();
    let res = web_test::call_service(&app, req).await;
    assert_eq!(res.status(), 409);
    let err: Value = web_test::read_body_json(res).await;
    assert_eq!(err["error"]["code"], "conflict");
    let mut invalid = state.clone();
    invalid["bikes"]["costs"]["bp"] = json!(-1);
    let req = web_test::TestRequest::put()
        .uri("/api/v1/state")
        .insert_header(("Cf-Access-Jwt-Assertion", jwt.clone()))
        .insert_header(("X-Buycycle-Expected-Identity", format!("{issuer}|person-1")))
        .set_json(json!({"expected_revision":1,"state":invalid}))
        .to_request();
    assert_eq!(web_test::call_service(&app, req).await.status(), 422);
    let request = json!({"expected_revision":1,"state":state,"source":{"origin":"synthetic-export","watch":{},"log":[],"costs":{"unknown_future_cost":7}}});
    let req = web_test::TestRequest::post()
        .uri("/api/v1/state/import-preview")
        .insert_header(("Cf-Access-Jwt-Assertion", jwt.clone()))
        .insert_header(("X-Buycycle-Expected-Identity", format!("{issuer}|person-1")))
        .set_json(&request)
        .to_request();
    assert_eq!(web_test::call_service(&app, req).await.status(), 200);
    assert_eq!(
        db.user_state(&format!("{issuer}|person-1"))
            .await
            .unwrap()
            .revision,
        1
    );
    for _ in 0..2 {
        let req = web_test::TestRequest::post()
            .uri("/api/v1/state/import")
            .insert_header(("Cf-Access-Jwt-Assertion", jwt.clone()))
            .insert_header(("X-Buycycle-Expected-Identity", format!("{issuer}|person-1")))
            .set_json(&request)
            .to_request();
        let res = web_test::call_service(&app, req).await;
        assert_eq!(res.status(), 200);
        let imported: Value = web_test::read_body_json(res).await;
        assert_eq!(imported["revision"], 2);
    }
    let req = web_test::TestRequest::get()
        .uri("/api/v1/listings?kind=wheels")
        .insert_header(("Cf-Access-Jwt-Assertion", jwt.clone()))
        .insert_header(("X-Buycycle-Expected-Identity", format!("{issuer}|person-1")))
        .to_request();
    let res = web_test::call_service(&app, req).await;
    assert_eq!(res.status(), 200);
    let listings: Value = web_test::read_body_json(res).await;
    assert!(listings["items"].as_array().unwrap().is_empty());
    let req = web_test::TestRequest::get()
        .uri("/api/v1/listings?kind=malformed")
        .insert_header(("Cf-Access-Jwt-Assertion", jwt))
        .insert_header(("X-Buycycle-Expected-Identity", format!("{issuer}|person-1")))
        .to_request();
    assert_eq!(web_test::call_service(&app, req).await.status(), 422);
    drop(app);
    drop(db);
    handle.stop(true).await;
    support::drop_database(&base, &name).await;
}
#[test]
fn validation_retains_unknown_metadata_but_rejects_bad_money_urls_and_dates() {
    let mut raw = json!({"version":1,"bikes":{"watch":{"id":{"n":"Synthetic","u":"https://buycycle.com/en-lu/product/synthetic","p":100.,"t":"2026-11-15","future":"preserve"}},"log":[],"costs":{"unknown_future_cost":7.}},"wheels":{},"future_top_level":{"preserve":true}});
    let state: BrowserState = serde_json::from_value(raw.clone()).unwrap();
    assert!(buycycle_backend::services::validate_state(&state).is_ok());
    assert_eq!(
        serde_json::to_value(state).unwrap()["future_top_level"]["preserve"],
        true
    );
    for (field, value) in [
        ("u", json!("javascript:alert(1)")),
        ("p", json!(-1)),
        ("t", json!("2026-02-30")),
    ] {
        raw["bikes"]["watch"]["id"][field] = value;
        let state: BrowserState = serde_json::from_value(raw.clone()).unwrap();
        assert!(buycycle_backend::services::validate_state(&state).is_err());
        raw["bikes"]["watch"]["id"] = json!({"n":"Synthetic","u":"https://buycycle.com/en-lu/product/synthetic","p":100.,"t":"2026-11-15"});
    }
}
#[actix_web::test]
async fn unsupported_methods_missing_routes_and_malformed_input_use_shared_safe_errors() {
    let (db, base, name) = support::database().await;
    let (auth, handle, issuer) = support::setup().await;
    let jwt = support::signed(support::claims(&issuer));
    let app = web_test::init_service(
        App::new()
            .app_data(web::Data::new(db.clone()))
            .app_data(web::Data::new(auth))
            .configure(http::configure),
    )
    .await;
    for (method, path, expected, code, body) in [
        (
            actix_web::http::Method::DELETE,
            "/api/v1/state",
            405,
            "method_not_allowed",
            "",
        ),
        (
            actix_web::http::Method::GET,
            "/api/v1/missing",
            404,
            "not_found",
            "",
        ),
        (
            actix_web::http::Method::GET,
            "/api/v1/listings?kind=invalid",
            422,
            "validation_failed",
            "",
        ),
        (
            actix_web::http::Method::PUT,
            "/api/v1/state",
            422,
            "validation_failed",
            "{private-invalid-json",
        ),
    ] {
        let request = web_test::TestRequest::default()
            .method(method)
            .uri(path)
            .insert_header(("Cf-Access-Jwt-Assertion", jwt.clone()))
            .insert_header(("X-Buycycle-Expected-Identity", format!("{issuer}|person-1")))
            .insert_header(("Content-Type", "application/json"))
            .set_payload(body)
            .to_request();
        let response = web_test::call_service(&app, request).await;
        assert_eq!(response.status().as_u16(), expected);
        assert_eq!(
            response.headers().get("Content-Type").unwrap(),
            "application/json"
        );
        assert_eq!(response.headers().get("Cache-Control").unwrap(), "no-store");
        let payload: Value = web_test::read_body_json(response).await;
        assert_eq!(payload["error"]["code"], code);
        assert!(payload["error"]["field_errors"].is_array());
        assert!(!payload.to_string().contains("private-invalid-json"));
    }
    drop(app);
    drop(db);
    handle.stop(true).await;
    support::drop_database(&base, &name).await;
}
#[actix_web::test]
async fn a_valid_new_identity_cannot_apply_another_identitys_captured_draft() {
    let (db, base, name) = support::database().await;
    let (auth, handle, issuer) = support::setup().await;
    let mut claims = support::claims(&issuer);
    claims["sub"] = json!("person-2");
    let jwt = support::signed(claims);
    let app = web_test::init_service(
        App::new()
            .app_data(web::Data::new(db.clone()))
            .app_data(web::Data::new(auth))
            .configure(http::configure),
    )
    .await;
    for expected in [None, Some(format!("{issuer}|person-1"))] {
        let mut request = web_test::TestRequest::put()
            .uri("/api/v1/state")
            .insert_header(("Cf-Access-Jwt-Assertion", jwt.clone()));
        if let Some(expected) = expected {
            request = request.insert_header(("X-Buycycle-Expected-Identity", expected));
        }
        let response = web_test::call_service(
            &app,
            request
                .set_json(json!({"expected_revision":0,"state":BrowserState::default()}))
                .to_request(),
        )
        .await;
        assert_eq!(response.status(), 403);
    }
    assert_eq!(
        db.user_state(&format!("{issuer}|person-2"))
            .await
            .unwrap()
            .revision,
        0
    );
    let request = web_test::TestRequest::put()
        .uri("/api/v1/state")
        .insert_header(("Cf-Access-Jwt-Assertion", jwt))
        .insert_header(("X-Buycycle-Expected-Identity", format!("{issuer}|person-2")))
        .set_json(json!({"expected_revision":0,"state":BrowserState::default()}))
        .to_request();
    assert_eq!(web_test::call_service(&app, request).await.status(), 200);
    drop(app);
    drop(db);
    handle.stop(true).await;
    support::drop_database(&base, &name).await;
}
#[actix_web::test]
async fn optional_read_identity_fence_prevents_a_new_sessions_payload_entering_an_old_session() {
    let (db, base, name) = support::database().await;
    let (auth, handle, issuer) = support::setup().await;
    let jwt = support::signed(support::claims(&issuer));
    let app = web_test::init_service(
        App::new()
            .app_data(web::Data::new(db.clone()))
            .app_data(web::Data::new(auth))
            .configure(http::configure),
    )
    .await;
    for path in ["/api/v1/state", "/api/v1/listings?kind=bikes"] {
        let request = web_test::TestRequest::get()
            .uri(path)
            .insert_header(("Cf-Access-Jwt-Assertion", jwt.clone()))
            .insert_header((
                "X-Buycycle-Expected-Identity",
                format!("{issuer}|another-session"),
            ))
            .to_request();
        assert_eq!(web_test::call_service(&app, request).await.status(), 403);
    }
    let request = web_test::TestRequest::get()
        .uri("/api/v1/status")
        .insert_header(("Cf-Access-Jwt-Assertion", jwt))
        .to_request();
    assert_eq!(web_test::call_service(&app, request).await.status(), 200);
    drop(app);
    drop(db);
    handle.stop(true).await;
    support::drop_database(&base, &name).await;
}
