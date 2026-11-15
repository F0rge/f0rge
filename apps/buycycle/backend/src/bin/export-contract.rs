use std::{io, path::PathBuf};
use utoipa::OpenApi;
fn main() -> io::Result<()> {
    let json = buycycle_backend::http::ApiDoc::openapi()
        .to_pretty_json()
        .map_err(io::Error::other)?
        + "\n";
    if let Some(path) = std::env::args().nth(1) {
        std::fs::write(PathBuf::from(path), json)
    } else {
        print!("{json}");
        Ok(())
    }
}
