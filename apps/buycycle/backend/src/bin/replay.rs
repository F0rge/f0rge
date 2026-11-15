use buycycle_backend::{collector::verified_replay, persistence::Db};
use std::{
    io::{BufWriter, Write},
    os::unix::fs::OpenOptionsExt,
    path::Path,
};

fn write_private_output(output: &Path, result: &impl serde::Serialize) -> std::io::Result<()> {
    let parent = output
        .parent()
        .filter(|path| !path.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let temporary = parent.join(format!(".buycycle-replay-{}.tmp", uuid::Uuid::new_v4()));
    let outcome = (|| {
        let file = std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&temporary)?;
        let mut writer = BufWriter::with_capacity(64 * 1024, file);
        serde_json::to_writer_pretty(&mut writer, result).map_err(std::io::Error::other)?;
        writer.flush()?;
        writer.get_ref().sync_all()?;
        drop(writer);
        // Atomic publication without replacing an existing output or symlink.
        std::fs::hard_link(&temporary, output)?;
        std::fs::File::open(parent)?.sync_all()?;
        Ok(())
    })();
    if temporary.exists() {
        std::fs::remove_file(&temporary)?;
    }
    outcome
}
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
    let result=verified_replay(&db,run,recalculate).await.map_err(|_|"Original replay unavailable: missing/tampered input, changed processing version, or mismatched result. --recalculate is explicitly labelled and performs no external action.")?;
    write_private_output(Path::new(output), &result)?;
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::os::unix::fs::PermissionsExt;

    #[test]
    fn private_output_publishes_atomically_and_never_replaces_existing_data() {
        let directory =
            std::env::temp_dir().join(format!("buycycle-replay-output-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&directory).unwrap();
        std::fs::set_permissions(&directory, std::fs::Permissions::from_mode(0o700)).unwrap();
        let output = directory.join("replay.json");
        let value = serde_json::json!({"synthetic":"café","nullable":null});
        write_private_output(&output, &value).unwrap();
        assert_eq!(
            std::fs::read(&output).unwrap(),
            serde_json::to_vec_pretty(&value).unwrap()
        );
        assert_eq!(
            std::fs::metadata(&output).unwrap().permissions().mode() & 0o777,
            0o600
        );
        assert!(write_private_output(&output, &serde_json::json!({"changed":true})).is_err());
        assert_eq!(
            std::fs::read(&output).unwrap(),
            serde_json::to_vec_pretty(&value).unwrap()
        );
        assert_eq!(std::fs::read_dir(&directory).unwrap().count(), 1);
        std::fs::remove_file(output).unwrap();
        std::fs::remove_dir(directory).unwrap();
    }

    #[test]
    fn failed_serialization_leaves_no_final_or_temporary_output() {
        struct Fails;
        impl serde::Serialize for Fails {
            fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
                use serde::ser::{Error, SerializeSeq};
                let mut sequence = serializer.serialize_seq(Some(2))?;
                sequence.serialize_element("synthetic prefix")?;
                Err(S::Error::custom("synthetic serialization failure"))
            }
        }
        let directory =
            std::env::temp_dir().join(format!("buycycle-replay-output-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&directory).unwrap();
        let output = directory.join("replay.json");
        assert!(write_private_output(&output, &Fails).is_err());
        assert!(!output.exists());
        assert_eq!(std::fs::read_dir(&directory).unwrap().count(), 0);
        std::fs::remove_dir(directory).unwrap();
    }
}
