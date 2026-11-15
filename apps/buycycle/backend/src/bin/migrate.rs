use buycycle_backend::persistence::Db;

#[tokio::main]
async fn main() -> std::process::ExitCode {
    let result = async {
        let url = std::env::var("MIGRATION_DATABASE_URL").map_err(|_| ())?;
        let db = Db::connect(&url).await.map_err(|_| ())?;
        db.migrate().await.map_err(|_| ())?;
        Ok::<_, ()>(())
    }
    .await;
    if result.is_ok() {
        println!("Buycycle migrations applied and checked.");
        std::process::ExitCode::SUCCESS
    } else {
        eprintln!(
            "Migration failed; inspect the controlled release prerequisites. No connection details are logged."
        );
        std::process::ExitCode::FAILURE
    }
}
