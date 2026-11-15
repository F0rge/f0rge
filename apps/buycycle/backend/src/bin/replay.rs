use buycycle_backend::{collector::replay, persistence::Db};
use std::{io::Write, os::unix::fs::OpenOptionsExt};
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().skip(1).collect();
    let run = args
        .windows(2)
        .find(|w| w[0] == "--run-id")
        .ok_or("--run-id UUID is required")?[1]
        .parse::<uuid::Uuid>()?;
    let output = &args
        .windows(2)
        .find(|w| w[0] == "--output")
        .ok_or("--output private/path.json is required")?[1];
    let recalculate = args.iter().any(|s| s == "--recalculate");
    let db = Db::connect(&std::env::var("DATABASE_URL")?).await?;
    let result=replay(&db,run,recalculate).await.map_err(|_|"Original replay unavailable: missing/tampered input, changed processing version, or mismatched result. --recalculate is explicitly labelled and performs no external action.")?;
    let mut file = std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(output)?;
    file.write_all(&serde_json::to_vec_pretty(&result)?)?;
    file.sync_all()?;
    println!(
        "{} saved to a new private output file",
        if recalculate {
            "New recalculation"
        } else {
            "Verified original replay"
        }
    );
    Ok(())
}
