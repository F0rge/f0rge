use buycycle_backend::persistence::Db;

fn grant_requested(arguments: &[String]) -> Result<bool, ()> {
    match arguments {
        [] => Ok(false),
        [flag] if flag == "--grant-runtime" => Ok(true),
        _ => Err(()),
    }
}

#[tokio::main]
async fn main() -> std::process::ExitCode {
    let result = async {
        let grant = grant_requested(&std::env::args().skip(1).collect::<Vec<_>>())?;
        let url = std::env::var("MIGRATION_DATABASE_URL").map_err(|_| ())?;
        let db = Db::connect(&url).await.map_err(|_| ())?;
        db.migrate().await.map_err(|_| ())?;
        if grant {
            db.grant_runtime().await.map_err(|_| ())?;
        }
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

#[cfg(test)]
mod tests {
    use super::grant_requested;

    #[test]
    fn migrations_are_role_neutral_without_the_exact_explicit_flag() {
        assert_eq!(grant_requested(&[]), Ok(false));
        assert_eq!(grant_requested(&["--grant-runtime".into()]), Ok(true));
        for arguments in [
            vec!["--grant-runtime=true".into()],
            vec!["--unknown".into()],
            vec!["--grant-runtime".into(), "--grant-runtime".into()],
            vec!["--grant-runtime".into(), "unexpected".into()],
        ] {
            assert!(grant_requested(&arguments).is_err());
        }
    }
}
