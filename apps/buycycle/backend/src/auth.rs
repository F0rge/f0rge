//! Consumer wiring for the shared verified Cloudflare Access identity adapter.
pub use f0rge_identity::{Auth, Claims, ExpectedPrincipal, Principal};
pub fn configure(auth: Auth) -> Auth {
    auth.with_expected_identity_header(actix_web::http::header::HeaderName::from_static(
        "x-buycycle-expected-identity",
    ))
}
pub async fn configured_from_env() -> Result<Auth, f0rge_api_errors::ApiError> {
    Auth::from_env().await.map(configure)
}
