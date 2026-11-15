use std::{error::Error as _, io};

use actix_web::{
    App, HttpResponse, ResponseError,
    body::to_bytes,
    http::{StatusCode, header},
    test as web_test, web,
};
use f0rge_api_errors::{ApiError, ErrorCode, FieldError, FieldErrorCode};
use serde_json::{Value, json};
use uuid::Uuid;

fn validation() -> ApiError {
    ApiError::validation(vec![
        FieldError::new("costs.purchase_price", FieldErrorCode::Required).unwrap(),
    ])
}

type ErrorCase = (fn() -> ApiError, StatusCode, &'static str, &'static str);

#[actix_web::test]
async fn every_error_has_the_exact_safe_envelope_status_and_headers() {
    let cases: [ErrorCase; 7] = [
        (
            validation,
            StatusCode::UNPROCESSABLE_ENTITY,
            "validation_failed",
            "Some fields are invalid.",
        ),
        (
            ApiError::unauthenticated,
            StatusCode::UNAUTHORIZED,
            "unauthenticated",
            "Authentication is required.",
        ),
        (
            ApiError::forbidden,
            StatusCode::FORBIDDEN,
            "forbidden",
            "You do not have permission to perform this action.",
        ),
        (
            ApiError::not_found,
            StatusCode::NOT_FOUND,
            "not_found",
            "The requested resource was not found.",
        ),
        (
            ApiError::method_not_allowed,
            StatusCode::METHOD_NOT_ALLOWED,
            "method_not_allowed",
            "This request method is not allowed.",
        ),
        (
            ApiError::conflict,
            StatusCode::CONFLICT,
            "conflict",
            "The resource changed. Refresh and try again.",
        ),
        (
            ApiError::internal,
            StatusCode::INTERNAL_SERVER_ERROR,
            "internal_error",
            "An unexpected error occurred.",
        ),
    ];
    for (factory, status, code, message) in cases {
        let error = factory();
        assert_eq!(error.status_code(), status);
        let response = error.error_response();
        assert_eq!(response.status(), status);
        assert_eq!(
            response.headers().get(header::CONTENT_TYPE).unwrap(),
            "application/json"
        );
        assert_eq!(
            response.headers().get(header::CACHE_CONTROL).unwrap(),
            "no-store"
        );
        assert!(!response.headers().contains_key(header::WWW_AUTHENTICATE));
        let body: Value =
            serde_json::from_slice(&to_bytes(response.into_body()).await.unwrap()).unwrap();
        let fields = if code == "validation_failed" {
            json!([{"field": "costs.purchase_price", "code": "required", "message": "This field is required."}])
        } else {
            json!([])
        };
        assert_eq!(
            body,
            json!({"error": {"code": code, "message": message, "error_id": error.error_id(), "field_errors": fields}})
        );
        let identifier = Uuid::parse_str(body["error"]["error_id"].as_str().unwrap()).unwrap();
        assert_eq!(identifier.get_version_num(), 4);
    }
}

#[test]
fn field_codes_have_fixed_messages_without_raw_values() {
    for (code, serialized, message) in [
        (
            FieldErrorCode::Required,
            "required",
            "This field is required.",
        ),
        (FieldErrorCode::Invalid, "invalid", "This field is invalid."),
        (
            FieldErrorCode::OutOfRange,
            "out_of_range",
            "This field is out of range.",
        ),
    ] {
        let field = FieldError::new("items.purchase_price", code).unwrap();
        assert_eq!(
            serde_json::to_value(field).unwrap(),
            json!({"field":"items.purchase_price", "code":serialized, "message":message})
        );
    }
}

#[test]
fn field_paths_accept_bounded_schema_identifiers() {
    for path in [
        "price",
        "_private",
        "items.purchase_price",
        "item2._value_3",
        "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwx",
    ] {
        assert!(
            FieldError::new(path, FieldErrorCode::Invalid).is_ok(),
            "{path}"
        );
    }
}

#[test]
fn field_paths_reject_empty_ambiguous_and_untrusted_metadata() {
    for path in [
        "",
        ".price",
        "price.",
        "price..amount",
        "9price",
        "items.0.price",
        "items[0].price",
        "price-value",
        "price/value",
        "price\nsecret",
        "pricé",
        "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvwxy",
    ] {
        let error = FieldError::new(path, FieldErrorCode::Invalid).unwrap_err();
        assert_eq!(error.to_string(), "Invalid schema field path");
        assert_eq!(format!("{error:?}"), "InvalidFieldPath");
    }
}

#[actix_web::test]
async fn error_identifier_is_generated_once_for_every_response() {
    let error = ApiError::conflict();
    let first = to_bytes(error.error_response().into_body()).await.unwrap();
    let second = to_bytes(error.error_response().into_body()).await.unwrap();
    assert_eq!(first, second);
    assert_ne!(error.error_id(), ApiError::conflict().error_id());
    assert_eq!(error.code(), ErrorCode::Conflict);
    assert!(error.to_string().contains(&error.error_id().to_string()));
}

#[actix_web::test]
async fn internal_cause_is_not_retained_serialized_or_formatted() {
    let error = ApiError::internal_from(io::Error::other(
        "sentinel-secret database/password stack trace",
    ));
    assert!(error.source().is_none());
    assert_eq!(error.code(), ErrorCode::InternalError);
    for text in [
        error.to_string(),
        format!("{error:?}"),
        String::from_utf8(
            to_bytes(error.error_response().into_body())
                .await
                .unwrap()
                .to_vec(),
        )
        .unwrap(),
    ] {
        for forbidden in ["sentinel-secret", "database/password", "stack trace"] {
            assert!(!text.contains(forbidden), "Leaked {forbidden}");
        }
    }
}

async fn result_error(path: web::Path<String>) -> Result<HttpResponse, ApiError> {
    Err(match path.as_str() {
        "validation" => validation(),
        "unauthenticated" => ApiError::unauthenticated(),
        "forbidden" => ApiError::forbidden(),
        "not-found" => ApiError::not_found(),
        "conflict" => ApiError::conflict(),
        _ => ApiError::internal_from(io::Error::other("sentinel-cause-token")),
    })
}

#[actix_web::test]
async fn actix_handler_result_maps_errors_without_reflecting_request_headers_or_values() {
    let app =
        web_test::init_service(App::new().route("/{kind}", web::get().to(result_error))).await;
    for (route, status) in [
        ("validation", 422),
        ("unauthenticated", 401),
        ("forbidden", 403),
        ("not-found", 404),
        ("conflict", 409),
        ("internal", 500),
    ] {
        let request = web_test::TestRequest::get()
            .uri(&format!("/{route}?submitted=sentinel-raw-value"))
            .insert_header(("x-request-id", "sentinel-untrusted-request-id"))
            .insert_header((header::AUTHORIZATION, "Bearer sentinel-header-token"))
            .to_request();
        let response = web_test::call_service(&app, request).await;
        assert_eq!(response.status().as_u16(), status);
        assert_eq!(
            response.headers().get(header::CACHE_CONTROL).unwrap(),
            "no-store"
        );
        let text = String::from_utf8(web_test::read_body(response).await.to_vec()).unwrap();
        assert!(!text.contains("sentinel-"));
        let body: Value = serde_json::from_str(&text).unwrap();
        assert_eq!(
            body["error"]["field_errors"].as_array().unwrap().is_empty(),
            status != 422
        );
        assert_eq!(
            Uuid::parse_str(body["error"]["error_id"].as_str().unwrap())
                .unwrap()
                .get_version_num(),
            4
        );
    }
}
