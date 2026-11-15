pub mod support;
use actix_web::{App, HttpResponse, test, web};
use buycycle_backend::auth::Principal;
use f0rge_api_errors::ErrorCode;
use jsonwebtoken::{Algorithm, EncodingKey, Header, encode};
use serde_json::json;
use support::{claims, setup, signed};
#[actix_web::test]
async fn valid_assertion_is_verified_and_only_approved_signed_email_is_authoritative() {
    let (auth, handle, issuer) = setup().await;
    let principal = auth.verify(&signed(claims(&issuer))).await.unwrap();
    assert_eq!(principal.email, "Leo@example.test");
    assert_eq!(principal.subject, format!("{issuer}|person-1"));
    let mut other = claims(&issuer);
    other["email"] = json!("unapproved@example.test");
    assert_eq!(
        auth.verify(&signed(other)).await.unwrap_err().code(),
        ErrorCode::Forbidden
    );
    handle.stop(true).await;
}
#[actix_web::test]
async fn invalid_signatures_claims_algorithms_and_expiration_fail_closed() {
    let (auth, handle, issuer) = setup().await;
    for (field, value) in [
        ("iss", json!("https://attacker.invalid")),
        ("aud", json!(["different-app"])),
        ("exp", json!(1)),
        ("nbf", json!(4_000_000_000_u64)),
        ("sub", json!("")),
    ] {
        let mut c = claims(&issuer);
        c[field] = value;
        assert_eq!(
            auth.verify(&signed(c)).await.unwrap_err().code(),
            ErrorCode::Unauthenticated,
            "{field}"
        );
    }
    let mut token = signed(claims(&issuer));
    token.push('x');
    assert_eq!(
        auth.verify(&token).await.unwrap_err().code(),
        ErrorCode::Unauthenticated
    );
    let token = encode(
        &Header::new(Algorithm::HS256),
        &claims(&issuer),
        &EncodingKey::from_secret(b"synthetic-only"),
    )
    .unwrap();
    assert_eq!(
        auth.verify(&token).await.unwrap_err().code(),
        ErrorCode::Unauthenticated
    );
    handle.stop(true).await;
}
async fn restricted(user: Principal) -> HttpResponse {
    HttpResponse::Ok().body(user.email)
}
#[actix_web::test]
async fn forged_identity_headers_cannot_authorize_a_request() {
    let (auth, handle, issuer) = setup().await;
    let app = test::init_service(
        App::new()
            .app_data(web::Data::new(auth))
            .route("/private", web::get().to(restricted)),
    )
    .await;
    let req = test::TestRequest::get()
        .uri("/private")
        .insert_header(("Cf-Access-Authenticated-User-Email", "leo@example.test"))
        .insert_header(("Authorization", "Bearer forged-token"))
        .to_request();
    let res = test::call_service(&app, req).await;
    assert_eq!(res.status(), 401);
    let jwt = signed(claims(&issuer));
    let req = test::TestRequest::get()
        .uri("/private")
        .insert_header(("Cf-Access-Jwt-Assertion", jwt))
        .to_request();
    assert_eq!(test::call_service(&app, req).await.status(), 200);
    handle.stop(true).await;
}
