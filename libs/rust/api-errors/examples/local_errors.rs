//! Synthetic loopback-only probe. No database, credentials or external calls.
use std::io;

use actix_web::{App, HttpResponse, HttpServer, web};
use f0rge_api_errors::{ApiError, FieldError, FieldErrorCode};

async fn healthy() -> HttpResponse {
    HttpResponse::Ok().body("Synthetic API-error probe")
}

async fn error(path: web::Path<String>) -> Result<HttpResponse, ApiError> {
    Err(match path.as_str() {
        "validation" => ApiError::validation(vec![
            FieldError::new("purchase_price", FieldErrorCode::OutOfRange)
                .expect("The probe uses a fixed schema field"),
        ]),
        "unauthenticated" => ApiError::unauthenticated(),
        "forbidden" => ApiError::forbidden(),
        "not-found" => ApiError::not_found(),
        "conflict" => ApiError::conflict(),
        _ => ApiError::internal_from(io::Error::other("synthetic-private-cause-do-not-publish")),
    })
}

#[actix_web::main]
async fn main() -> io::Result<()> {
    eprintln!("Synthetic API-error probe: http://127.0.0.1:8872");
    HttpServer::new(|| {
        App::new()
            .route("/", web::get().to(healthy))
            .route("/errors/{kind}", web::get().to(error))
    })
    .workers(1)
    .bind(("127.0.0.1", 8872))?
    .run()
    .await
}
