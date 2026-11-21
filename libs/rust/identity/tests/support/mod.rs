//! Synthetic signing key belongs only to these offline tests, never to a deployment.
use actix_web::{App, HttpServer, web};
use f0rge_identity::Auth;
use jsonwebtoken::{Algorithm, EncodingKey, Header, encode};
use serde_json::{Value, json};
use std::{
    collections::HashSet,
    time::{SystemTime, UNIX_EPOCH},
};
const PRIVATE_KEY: &str = r#"-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQCbBewuTsB/xalx
usY8ItrtJjEqJylJsHEF4UOwXJeRwTphidTbVhQmbSE/tSXSik5+jrda1iGt8P7p
0xRZEuVT640cvtntWGtZNAb749kRWR2LpNXMQV/WTX644CU2KKR1wJy4LiLXFvtW
7hBNvCa6AfZ0meZ8vVpSDFYlgHgcyiDFi+G3p1pmYotryKzJD+UU8b+msLNmXtUI
rx4VV8VmzUfI97tnvqEwseFNX8sdEmlWOaIuINOD3OaqHTh3J7JhRiTRCyntG5ot
6U5V/u3JaaZA9khexFxYTlSJpsirMtdvwUjVWvvldlLNPxwDINz9KTkePBD1gPuv
V44C60GNAgMBAAECggEAOz/QPQKsYClT0bvo+CL6OZlXQR0mkpt1FyI5lLZO185a
Wd0sFYiYuvcKtiauBgIGbihtu7ILvUdWpleed0zZiXGFxW7MLAKXRMi1wqAa3p6I
xE6DyEVUM7v6qv5AOqrd8INlYp9/gWWvOlJSuOMoif8mCvqnNRXJ54H/iuXHAnlG
HZxUn9xkemYJTlstY2MPSGH/BYt8BGWmf6G3PtTU0dmuAiK0PDvV0N7woshPbjQT
0FWNA1PEvoQKJQ/ScgQ6mxWOLA+0yx2fMTF1MVnB3iKOiKkJKlMsMnix+2UcWrpr
CSIfn8qR3XbNwbwYWKeXq4hM/l4dAfMVblXHu7IMoQKBgQDOVqDEo+IyelNDCP3v
8C1K4ox7GcN2urTO+JiweJXqcHtZycUkYa32Y9BGq6nb8U02Bz8ecg2I/Slg4+lP
5caWAG2XCVT4YyVIOsf8K8BMPnthZNd/79xCYaKPnlcNzamRtmG7A9MjtSZf3PMv
L03jZi5NIV70pxVx2DCeqnw5FwKBgQDAVYwAFxyuBpti/unZ40O1olDqNQF/jc25
eop2HC8imZ25thgdiOKdGQkpdD2jZFCBBSHzk9cH8p7Ua0MfFcRn2kMo8yZIKI7I
2GMTLcVs429TN54RvYSxVLrufqhdFbhPFy85a2Le5JfJJvokDPoi2SByF7tjxD1Z
QjqT61f4+wKBgQCNtFCUuzgNEpU75GEA9yEj3JI9uGPUlkS2H2Q9TZMnfjg4YalS
YwLlw4a2Ag6VThKImFFwx0MkYTiZoewJQvQu7/xTTcVdEDn6cOQG+sUFl6OEL40P
/9p0fDj4CPYgNK3PtEFJ/kZyr2W7UDJypToIgZQqxFBCFL1VgfNiBBNr4QKBgQCv
0gQnWPloxLVra+hOvIh7FCSv1UDHX9P+iFzm16DnGlKrICEvbqDqR6audIqcQOmu
6Ag/aJibtVkoid1UH0vqPAZE+vG16Q2N4PHA6Iifn9F221LumLcifHhd6P70CRTx
iBotfVNmusVepvjn180Z6i7U3Yj6DLygSgDOk8dZ3QKBgBWKTqEqzukOmhRhQc1+
Wra9zlywnMm70WItveGRJ1dU3lcR0AL6gkwZsnDPQyJ2Cqk4TuwzyFmH84lozMls
m/DSnTOAFM1hsTNLm2a42YlObzCa1sSl/u3WILbI83Gsp12J6C+cEBmAyVldR2kf
kxXkd1XVfquv286C3VhTQ9xB
-----END PRIVATE KEY-----
"#;
const MODULUS: &str = "mwXsLk7Af8WpcbrGPCLa7SYxKicpSbBxBeFDsFyXkcE6YYnU21YUJm0hP7Ul0opOfo63WtYhrfD-6dMUWRLlU-uNHL7Z7VhrWTQG--PZEVkdi6TVzEFf1k1-uOAlNiikdcCcuC4i1xb7Vu4QTbwmugH2dJnmfL1aUgxWJYB4HMogxYvht6daZmKLa8isyQ_lFPG_prCzZl7VCK8eFVfFZs1HyPe7Z76hMLHhTV_LHRJpVjmiLiDTg9zmqh04dyeyYUYk0Qsp7RuaLelOVf7tyWmmQPZIXsRcWE5UiabIqzLXb8FI1Vr75XZSzT8cAyDc_Sk5HjwQ9YD7r1eOAutBjQ";
pub async fn setup() -> (Auth, actix_web::dev::ServerHandle, String) {
    let listener = std::net::TcpListener::bind(("127.0.0.1", 0)).unwrap();
    let issuer = format!("http://{}", listener.local_addr().unwrap());
    let keys = web::Data::new(
        json!({"keys":[{"kty":"RSA","kid":"synthetic-key","alg":"RS256","use":"sig","n":MODULUS,"e":"AQAB"}]}),
    );
    let server = HttpServer::new(move || {
        App::new().app_data(keys.clone()).route(
            "/cdn-cgi/access/certs",
            web::get()
                .to(|keys: web::Data<Value>| async move { web::Json(keys.get_ref().clone()) }),
        )
    })
    .listen(listener)
    .unwrap()
    .run();
    let handle = server.handle();
    actix_rt::spawn(server);
    let emails = HashSet::from(["leo@example.test".to_owned()]);
    let auth = Auth::new(
        issuer.clone(),
        "identity-test".into(),
        format!("{issuer}/cdn-cgi/access/certs"),
        emails,
        true,
    )
    .await
    .unwrap();
    (auth, handle, issuer)
}
pub fn claims(issuer: &str) -> Value {
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs();
    json!({"iss":issuer,"aud":["identity-test"],"sub":"person-1","email":"Leo@example.test","exp":now+600,"nbf":now-10})
}
pub fn signed(claims: Value) -> String {
    let mut header = Header::new(Algorithm::RS256);
    header.kid = Some("synthetic-key".into());
    encode(
        &header,
        &claims,
        &EncodingKey::from_rsa_pem(PRIVATE_KEY.as_bytes()).unwrap(),
    )
    .unwrap()
}
