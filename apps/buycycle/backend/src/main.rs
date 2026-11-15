use actix_files::{Files, NamedFile};
use actix_web::{App, HttpRequest, HttpServer, web};
use buycycle_backend::{auth, http, persistence::Db};
use std::io;
#[actix_web::main]
async fn main() -> io::Result<()> {
    let _ = tracing_subscriber::fmt()
        .json()
        .with_env_filter("info")
        .try_init();
    if std::env::args().nth(1).is_some_and(|a| a != "serve") {
        return Err(io::Error::other(
            "Only serve is supported; migrations and collectors use explicit binaries",
        ));
    }
    let url =
        std::env::var("DATABASE_URL").map_err(|_| io::Error::other("DATABASE_URL is required"))?;
    let db = Db::connect(&url)
        .await
        .map_err(|_| io::Error::other("Database unavailable"))?;
    let auth = auth::configured_from_env()
        .await
        .map_err(|_| io::Error::other("Verified Access identity configuration is required"))?;
    let bind = std::env::var("BUYCYCLE_BIND").unwrap_or_else(|_| "127.0.0.1:8080".into());
    let frontend = std::env::var("BUYCYCLE_FRONTEND_DIR")
        .unwrap_or_else(|_| "apps/buycycle/frontend/dist".into());
    let db = web::Data::new(db);
    let auth = web::Data::new(auth);
    tracing::info!(event = "server_start", version = env!("CARGO_PKG_VERSION"));
    HttpServer::new(move || {
        let index = format!("{frontend}/index.html");
        App::new()
            .app_data(db.clone())
            .app_data(auth.clone())
            .wrap(
                actix_web::middleware::DefaultHeaders::new()
                    .add(("X-Content-Type-Options", "nosniff"))
                    .add(("Referrer-Policy", "same-origin"))
                    .add(("Cache-Control", "no-store")),
            )
            .configure(http::configure)
            .service(
                Files::new("/", &frontend)
                    .index_file("index.html")
                    .default_handler(web::to(move |req: HttpRequest| {
                        let index = index.clone();
                        async move {
                            let file = NamedFile::open_async(index).await?;
                            Ok::<_, actix_web::Error>(file.into_response(&req))
                        }
                    })),
            )
    })
    .workers(2)
    .client_request_timeout(std::time::Duration::from_secs(15))
    .bind(bind)?
    .run()
    .await
}
