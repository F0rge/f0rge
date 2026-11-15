use buycycle_backend::{
    collector::{HttpSource, collect},
    contracts::Kind,
    persistence::Db,
};
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    if std::env::var("BUYCYCLE_COLLECTION_ENABLED").as_deref() != Ok("true") {
        return Err("Collection is disabled until an approved release enables it".into());
    }
    let args: Vec<_> = std::env::args().skip(1).collect();
    let kinds=match args.as_slice(){[]=>vec![Kind::Bikes,Kind::Wheels],[flag,kind]if flag=="--kind"=>match kind.as_str(){"bikes"=>vec![Kind::Bikes],"wheels"=>vec![Kind::Wheels],"all"=>vec![Kind::Bikes,Kind::Wheels],_=>return Err("Unknown kind".into())},_=>return Err("Only --kind bikes|wheels|all is supported; force and historical collection are not allowed".into())};
    let db = Db::connect(&std::env::var("DATABASE_URL")?).await?;
    let key = std::env::var("BUYCYCLE_API_KEY").map_err(|_| "Feed credential is required")?;
    let source = HttpSource::new()?;
    collect(&db, &source, &key, kinds).await?;
    Ok(())
}
