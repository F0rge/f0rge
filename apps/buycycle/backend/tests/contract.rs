use utoipa::OpenApi;
#[test]
fn authoritative_rust_openapi_matches_the_committed_client_contract() {
    let actual = serde_json::to_value(buycycle_backend::http::ApiDoc::openapi()).unwrap();
    let expected: serde_json::Value =
        serde_json::from_str(include_str!("../openapi.json")).unwrap();
    assert_eq!(
        actual, expected,
        "Regenerate with the buycycle-backend:openapi target, then regenerate the frontend client"
    );
}
