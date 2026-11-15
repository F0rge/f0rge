use buycycle_backend::{
    import::{LegacyBundle, import_bundle, reconcile, validate_bundle},
    persistence::Db,
};

#[tokio::main]
async fn main() -> std::process::ExitCode {
    let args: Vec<_> = std::env::args().skip(1).collect();
    let result = async {
        if args.len() != 2 || !["--preview", "--import", "--reconcile"].contains(&args[0].as_str())
        {
            return Err(());
        }
        let metadata = std::fs::symlink_metadata(&args[1]).map_err(|_| ())?;
        if !metadata.is_file() || metadata.len() > 512 * 1024 * 1024 {
            return Err(());
        }
        let bytes = std::fs::read(&args[1]).map_err(|_| ())?;
        let bundle: LegacyBundle = serde_json::from_slice(&bytes).map_err(|_| ())?;
        let report = if args[0] == "--preview" {
            validate_bundle(&bundle).map_err(|_| ())?
        } else {
            let url = std::env::var("MIGRATION_DATABASE_URL").map_err(|_| ())?;
            let db = Db::connect(&url).await.map_err(|_| ())?;
            if args[0] == "--import" {
                import_bundle(&db, &bundle).await.map_err(|_| ())?
            } else {
                reconcile(&db, &bundle).await.map_err(|_| ())?
            }
        };
        println!("{}", serde_json::to_string(&report).map_err(|_| ())?);
        Ok::<_, ()>(())
    }
    .await;
    if result.is_ok() {
        std::process::ExitCode::SUCCESS
    } else {
        eprintln!(
            "Import/reconciliation refused. Usage: import-legacy --preview|--import|--reconcile <private-bundle.json>. No source data or connection details are logged."
        );
        std::process::ExitCode::FAILURE
    }
}
