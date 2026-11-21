#![forbid(unsafe_code)]
//! Cloudflare Access assertions are verified cryptographically; email headers alone carry no authority.
use actix_web::{FromRequest, HttpRequest, dev::Payload, web};
use f0rge_api_errors::ApiError;
use jsonwebtoken::{Algorithm, DecodingKey, Validation, decode, decode_header, jwk::JwkSet};
use serde::Deserialize;
use std::{
    collections::HashSet,
    future::Future,
    pin::Pin,
    time::{Duration, Instant},
};
use tokio::sync::RwLock;

#[derive(Debug, Deserialize, Clone)]
pub struct Claims {
    pub sub: String,
    pub email: String,
    pub iss: String,
    pub aud: serde_json::Value,
    pub exp: u64,
    #[serde(default)]
    pub nbf: Option<u64>,
}
#[derive(Debug, Clone)]
pub struct Principal {
    pub subject: String,
    pub email: String,
}
struct CachedKeys {
    set: JwkSet,
    fetched: Instant,
}
pub struct Auth {
    issuer: String,
    audience: String,
    jwks_url: String,
    emails: HashSet<String>,
    client: reqwest::Client,
    keys: RwLock<CachedKeys>,
    expected_identity_header: Option<actix_web::http::header::HeaderName>,
}
impl Auth {
    pub async fn from_env() -> Result<Self, ApiError> {
        let issuer = std::env::var("ACCESS_ISSUER")
            .map_err(ApiError::internal_from)?
            .trim_end_matches('/')
            .to_owned();
        let audience = std::env::var("ACCESS_AUDIENCE").map_err(ApiError::internal_from)?;
        let emails: HashSet<String> = std::env::var("ACCESS_ALLOWED_EMAILS")
            .map_err(ApiError::internal_from)?
            .split(',')
            .map(|s| s.trim().to_lowercase())
            .filter(|s| !s.is_empty())
            .collect();
        let jwks_url = std::env::var("ACCESS_JWKS_URL")
            .unwrap_or_else(|_| format!("{issuer}/cdn-cgi/access/certs"));
        // Environment configuration never enables local mode; only `new(.., true)` does.
        Self::new(issuer, audience, jwks_url, emails, false).await
    }
    /// `local` permits loopback HTTP issuer/JWKS fixtures and disables Cloudflare origin/path pinning;
    /// tests only. Production callers pass `false`.
    pub async fn new(
        issuer: String,
        audience: String,
        jwks_url: String,
        emails: HashSet<String>,
        local: bool,
    ) -> Result<Self, ApiError> {
        let iss = reqwest::Url::parse(&issuer).map_err(ApiError::internal_from)?;
        let keys = reqwest::Url::parse(&jwks_url).map_err(ApiError::internal_from)?;
        let loopback = |u: &reqwest::Url| {
            u.scheme() == "http"
                && matches!(
                    u.host_str(),
                    Some("127.0.0.1" | "localhost" | "[::1]" | "::1")
                )
        };
        if audience.is_empty()
            || emails.is_empty()
            || emails.iter().any(|e| !e.contains('@'))
            || !iss.username().is_empty()
            || !keys.username().is_empty()
            || iss.password().is_some()
            || keys.password().is_some()
            || !(iss.scheme() == "https" && keys.scheme() == "https"
                || local && loopback(&iss) && loopback(&keys))
        {
            return Err(ApiError::internal());
        }
        if !local
            && (!iss
                .host_str()
                .is_some_and(|h| h.ends_with(".cloudflareaccess.com"))
                || keys.origin() != iss.origin()
                || keys.path() != "/cdn-cgi/access/certs")
        {
            return Err(ApiError::internal());
        }
        let client = reqwest::Client::builder()
            .redirect(reqwest::redirect::Policy::none())
            .timeout(Duration::from_secs(10))
            .build()
            .map_err(ApiError::internal_from)?;
        let set = fetch_keys(&client, &jwks_url).await?;
        Ok(Self {
            issuer,
            audience,
            jwks_url,
            emails,
            client,
            expected_identity_header: None,
            keys: RwLock::new(CachedKeys {
                set,
                fetched: Instant::now(),
            }),
        })
    }
    /// Configure a consumer-owned draft/read identity precondition; it grants no authority.
    pub fn with_expected_identity_header(
        mut self,
        header: actix_web::http::header::HeaderName,
    ) -> Self {
        self.expected_identity_header = Some(header);
        self
    }
    pub async fn verify(&self, token: &str) -> Result<Principal, ApiError> {
        if token.len() > 16384 {
            return Err(ApiError::unauthenticated());
        }
        let header = decode_header(token).map_err(|_| ApiError::unauthenticated())?;
        if header.alg != Algorithm::RS256 {
            return Err(ApiError::unauthenticated());
        }
        let kid = header
            .kid
            .filter(|s| !s.is_empty() && s.len() <= 128)
            .ok_or_else(ApiError::unauthenticated)?;
        {
            let current = self.keys.read().await;
            if current.fetched.elapsed() > Duration::from_secs(300)
                || (current.set.find(&kid).is_none()
                    && current.fetched.elapsed() > Duration::from_secs(5))
            {
                drop(current);
                let mut current = self.keys.write().await;
                if current.fetched.elapsed() > Duration::from_secs(5) {
                    current.set = fetch_keys(&self.client, &self.jwks_url)
                        .await
                        .map_err(|_| ApiError::unauthenticated())?;
                    current.fetched = Instant::now();
                }
            }
        }
        let current = self.keys.read().await;
        let jwk = current
            .set
            .find(&kid)
            .ok_or_else(ApiError::unauthenticated)?;
        let key = DecodingKey::from_jwk(jwk).map_err(|_| ApiError::unauthenticated())?;
        let mut validation = Validation::new(Algorithm::RS256);
        validation.set_audience(&[&self.audience]);
        validation.set_issuer(&[&self.issuer]);
        validation.set_required_spec_claims(&["exp", "sub", "iss", "aud"]);
        validation.validate_nbf = true;
        validation.leeway = 0;
        let claims = decode::<Claims>(token, &key, &validation)
            .map_err(|_| ApiError::unauthenticated())?
            .claims;
        if claims.sub.is_empty() || claims.email.is_empty() {
            return Err(ApiError::unauthenticated());
        }
        if !self.emails.contains(&claims.email.to_lowercase()) {
            return Err(ApiError::forbidden());
        }
        Ok(Principal {
            subject: format!("{}|{}", claims.iss, claims.sub),
            email: claims.email,
        })
    }
}
async fn fetch_keys(client: &reqwest::Client, url: &str) -> Result<JwkSet, ApiError> {
    let mut response = client
        .get(url)
        .send()
        .await
        .map_err(ApiError::internal_from)?
        .error_for_status()
        .map_err(ApiError::internal_from)?;
    let mut bytes = Vec::new();
    while let Some(chunk) = response.chunk().await.map_err(ApiError::internal_from)? {
        if bytes.len() + chunk.len() > 1024 * 1024 {
            return Err(ApiError::internal());
        }
        bytes.extend_from_slice(&chunk);
    }
    let set: JwkSet = serde_json::from_slice(&bytes).map_err(ApiError::internal_from)?;
    if set.keys.is_empty() {
        return Err(ApiError::internal());
    }
    Ok(set)
}
impl FromRequest for Principal {
    type Error = ApiError;
    type Future = Pin<Box<dyn Future<Output = Result<Self, Self::Error>>>>;
    fn from_request(req: &HttpRequest, _: &mut Payload) -> Self::Future {
        let auth = req.app_data::<web::Data<Auth>>().cloned();
        let values: Vec<_> = req.headers().get_all("cf-access-jwt-assertion").collect();
        let token = if values.len() == 1 {
            values[0].to_str().ok().map(str::to_owned)
        } else {
            None
        };
        let expected_header = auth
            .as_ref()
            .and_then(|a| a.expected_identity_header.as_ref());
        let expected_values: Vec<_> = expected_header
            .map(|h| req.headers().get_all(h).collect())
            .unwrap_or_default();
        let expected_count = expected_values.len();
        let expected = expected_values
            .first()
            .and_then(|v| v.to_str().ok())
            .map(str::to_owned);
        Box::pin(async move {
            let auth = auth.ok_or_else(ApiError::internal)?;
            let token = token.ok_or_else(ApiError::unauthenticated)?;
            let principal = auth.verify(&token).await?;
            if expected_count > 1
                || expected_count == 1 && expected.as_deref() != Some(principal.subject.as_str())
            {
                return Err(ApiError::forbidden());
            }
            Ok(principal)
        })
    }
}
/// An identity fence for drafts captured by a browser session. This header never authenticates a caller.
pub struct ExpectedPrincipal(pub Principal);
impl FromRequest for ExpectedPrincipal {
    type Error = ApiError;
    type Future = Pin<Box<dyn Future<Output = Result<Self, Self::Error>>>>;
    fn from_request(req: &HttpRequest, payload: &mut Payload) -> Self::Future {
        let auth = req.app_data::<web::Data<Auth>>();
        let header = auth.and_then(|a| a.expected_identity_header.as_ref());
        let values: Vec<_> = header
            .map(|h| req.headers().get_all(h).collect())
            .unwrap_or_default();
        let expected = if values.len() == 1 {
            values[0].to_str().ok().map(str::to_owned)
        } else {
            None
        };
        let authenticated = Principal::from_request(req, payload);
        Box::pin(async move {
            let principal = authenticated.await?;
            if expected.as_deref() != Some(principal.subject.as_str()) {
                return Err(ApiError::forbidden());
            }
            Ok(Self(principal))
        })
    }
}
