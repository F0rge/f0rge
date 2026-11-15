use crate::{
    auth::{ExpectedPrincipal, Principal},
    contracts::*,
    persistence::Db,
    services,
};
use actix_web::{HttpResponse, web};
use f0rge_api_errors::ApiError;

#[derive(serde::Deserialize)]
pub struct ListingQuery {
    pub kind: Kind,
}
#[utoipa::path(get,path="/api/v1/listings",params(("kind"=Kind,Query)),responses((status=200,body=ListingsResponse),(status=401,body=f0rge_api_errors::ErrorEnvelope),(status=403,body=f0rge_api_errors::ErrorEnvelope),(status="default",body=f0rge_api_errors::ErrorEnvelope)),security(("cloudflare_access"=[])))]
async fn listings(
    _: Principal,
    db: web::Data<Db>,
    query: web::Query<ListingQuery>,
) -> Result<HttpResponse<services::ListingsBody>, ApiError> {
    let body = services::listings(&db, query.into_inner().kind).await?;
    HttpResponse::Ok()
        .content_type("application/json")
        .message_body(body)
        .map_err(ApiError::internal_from)
}
#[utoipa::path(get,path="/api/v1/status",responses((status=200,body=StatusResponse),(status="default",body=f0rge_api_errors::ErrorEnvelope)),security(("cloudflare_access"=[])))]
async fn status(user: Principal, db: web::Data<Db>) -> Result<web::Json<StatusResponse>, ApiError> {
    services::status(&db, user.subject).await.map(web::Json)
}
#[utoipa::path(get,path="/api/v1/state",responses((status=200,body=StateResponse),(status="default",body=f0rge_api_errors::ErrorEnvelope)),security(("cloudflare_access"=[])))]
async fn state(user: Principal, db: web::Data<Db>) -> Result<web::Json<StateResponse>, ApiError> {
    services::read_state(&db, &user.subject)
        .await
        .map(web::Json)
}
#[utoipa::path(put,path="/api/v1/state",params(("X-Buycycle-Expected-Identity"=String,Header,description="Subject captured with the browser draft; must match verified identity")),request_body=StateWrite,responses((status=200,body=StateResponse),(status=409,body=f0rge_api_errors::ErrorEnvelope),(status=422,body=f0rge_api_errors::ErrorEnvelope),(status="default",body=f0rge_api_errors::ErrorEnvelope)),security(("cloudflare_access"=[])))]
async fn update_state(
    fenced: ExpectedPrincipal,
    db: web::Data<Db>,
    write: web::Json<StateWrite>,
) -> Result<web::Json<StateResponse>, ApiError> {
    services::write_state(&db, &fenced.0.subject, write.into_inner())
        .await
        .map(web::Json)
}
#[utoipa::path(post,path="/api/v1/state/import-preview",params(("X-Buycycle-Expected-Identity"=String,Header,description="Subject captured with the browser draft; must match verified identity")),request_body=ImportWrite,responses((status=200,body=ImportPreview),(status=409,body=f0rge_api_errors::ErrorEnvelope),(status=422,body=f0rge_api_errors::ErrorEnvelope),(status="default",body=f0rge_api_errors::ErrorEnvelope)),security(("cloudflare_access"=[])))]
async fn preview(
    fenced: ExpectedPrincipal,
    db: web::Data<Db>,
    write: web::Json<ImportWrite>,
) -> Result<web::Json<ImportPreview>, ApiError> {
    services::preview_import(&db, &fenced.0.subject, &write)
        .await
        .map(web::Json)
}
#[utoipa::path(post,path="/api/v1/state/import",params(("X-Buycycle-Expected-Identity"=String,Header,description="Subject captured with the browser draft; must match verified identity")),request_body=ImportWrite,responses((status=200,body=StateResponse),(status=409,body=f0rge_api_errors::ErrorEnvelope),(status=422,body=f0rge_api_errors::ErrorEnvelope),(status="default",body=f0rge_api_errors::ErrorEnvelope)),security(("cloudflare_access"=[])))]
async fn import(
    fenced: ExpectedPrincipal,
    db: web::Data<Db>,
    write: web::Json<ImportWrite>,
) -> Result<web::Json<StateResponse>, ApiError> {
    services::import_state(&db, &fenced.0.subject, write.into_inner())
        .await
        .map(web::Json)
}
async fn unsupported_method(_: Principal) -> Result<HttpResponse, ApiError> {
    Err(ApiError::method_not_allowed())
}
async fn public_unsupported_method() -> Result<HttpResponse, ApiError> {
    Err(ApiError::method_not_allowed())
}
async fn missing(_: Principal) -> Result<HttpResponse, ApiError> {
    Err(ApiError::not_found())
}
#[utoipa::path(get,path="/health",responses((status=200,body=Health),(status="default",body=f0rge_api_errors::ErrorEnvelope)),security())]
async fn health() -> web::Json<Health> {
    web::Json(Health {
        status: "ok".into(),
        version: env!("CARGO_PKG_VERSION").into(),
        source_commit: option_env!("BUYCYCLE_SOURCE_COMMIT")
            .unwrap_or("local-unreleased")
            .into(),
    })
}
#[utoipa::path(get,path="/ready",responses((status=200,body=Health),(status=500,body=f0rge_api_errors::ErrorEnvelope)),security())]
async fn ready(db: web::Data<Db>) -> Result<web::Json<Health>, ApiError> {
    db.health().await.map_err(services::data_error)?;
    Ok(web::Json(Health {
        status: "ready".into(),
        version: env!("CARGO_PKG_VERSION").into(),
        source_commit: option_env!("BUYCYCLE_SOURCE_COMMIT")
            .unwrap_or("local-unreleased")
            .into(),
    }))
}
pub fn configure(cfg: &mut web::ServiceConfig) {
    cfg.app_data(
        web::JsonConfig::default()
            .limit(8 * 1024 * 1024)
            .error_handler(|_, _| services::invalid("body").into()),
    )
    .app_data(web::QueryConfig::default().error_handler(|_, _| services::invalid("query").into()))
    .service(
        web::resource("/health")
            .route(web::get().to(health))
            .default_service(web::to(public_unsupported_method)),
    )
    .service(
        web::resource("/ready")
            .route(web::get().to(ready))
            .default_service(web::to(public_unsupported_method)),
    )
    .service(
        web::scope("/api/v1")
            .service(
                web::resource("/listings")
                    .route(web::get().to(listings))
                    .default_service(web::to(unsupported_method)),
            )
            .service(
                web::resource("/status")
                    .route(web::get().to(status))
                    .default_service(web::to(unsupported_method)),
            )
            .service(
                web::resource("/state")
                    .route(web::get().to(state))
                    .route(web::put().to(update_state))
                    .default_service(web::to(unsupported_method)),
            )
            .service(
                web::resource("/state/import-preview")
                    .route(web::post().to(preview))
                    .default_service(web::to(unsupported_method)),
            )
            .service(
                web::resource("/state/import")
                    .route(web::post().to(import))
                    .default_service(web::to(unsupported_method)),
            )
            .default_service(web::to(missing)),
    );
}
#[derive(utoipa::OpenApi)]
#[openapi(paths(health,ready,listings,status,state,update_state,preview,import),components(schemas(Listing,ListingsResponse,Kind,PricePoint,NextUp,Identity,StatusResponse,WatchEntry,Trade,CategoryState,BrowserState,StateResponse,StateWrite,ImportWrite,ImportPreview,ImportCounts,Health,f0rge_api_errors::ErrorEnvelope)),modifiers(&Security))]
pub struct ApiDoc;
struct Security;
impl utoipa::Modify for Security {
    fn modify(&self, doc: &mut utoipa::openapi::OpenApi) {
        use utoipa::openapi::security::{ApiKey, ApiKeyValue, SecurityScheme};
        doc.components
            .as_mut()
            .expect("schemas")
            .add_security_scheme(
                "cloudflare_access",
                SecurityScheme::ApiKey(ApiKey::Header(ApiKeyValue::new("Cf-Access-Jwt-Assertion"))),
            );
    }
}
