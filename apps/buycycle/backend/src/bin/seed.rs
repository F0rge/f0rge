//! Synthetic local fixtures only; never an implicit server-startup action.
use std::collections::BTreeMap;

use buycycle_backend::{
    import::{LegacyBundle, canonical_rows, canonical_sha256, import_bundle},
    persistence::{Db, LEGACY_TABLES},
};
use serde_json::{Value, json};

#[tokio::main]
async fn main() -> std::process::ExitCode {
    let result=async {
        if std::env::var("BUYCYCLE_LOCAL_SEED").as_deref()!=Ok("1") {return Err(());}
        let url=std::env::var("MIGRATION_DATABASE_URL").map_err(|_|())?;
        let parsed=reqwest::Url::parse(&url).map_err(|_|())?;
        if !["127.0.0.1","localhost","postgres","db","buycycle-postgres"].contains(&parsed.host_str().unwrap_or("")) ||
            !["local","test","rehearsal"].iter().any(|kind|parsed.path().contains(kind)) {return Err(());}
        let mut tables:BTreeMap<String,Vec<Value>>=LEGACY_TABLES.into_iter().map(|table|(table.to_owned(),vec![])).collect();
        for (kind,model,brand,base) in [("bikes","Synthetic Road 2024","Fixture Cycles",1000),("wheels","Synthetic Carbon Wheels","Fixture Wheels",450)] {
            for index in 0..8 {
                let id=format!("fixture-{kind}-{index}");
                let price=base+index*100;
                tables.get_mut("listing").ok_or(())?.push(json!({"id":id,"kind":kind,"slug":format!("synthetic-{kind}-{index}"),"name":model,"brand":brand,"year":2024,"size":"M","cond":"good","msrp":null,"price":price,"original_price":price+150,"activated_at":1704067200,"updated_at":1704153600,"country_id":150,"seller_id":index,"favs":1,"offers":0,"high_demand":0,"n_media":3,"desc_len":240,"spec":"{}","first_seen":"2026-01-01","last_seen":"2026-01-15","gone_at":null,"last_fetch":null,"fetch_price":null,"pr":0}));
                tables.get_mut("price_history").ok_or(())?.push(json!({"id":id,"day":"2026-01-01","price":price+150}));
                tables.get_mut("price_history").ok_or(())?.push(json!({"id":id,"day":"2026-01-15","price":price}));
            }
            tables.get_mut("runs").ok_or(())?.push(json!({"day":"2026-01-15","kind":kind,"complete":1,"n":8,"new":8,"gone":0,"fetched":0,"note":"Synthetic local fixture only"}));
        }
        tables.get_mut("country_map").ok_or(())?.push(json!({"cid":150,"country":"Germany"}));
        let hashes=tables.iter().map(|(table,rows)|Ok((table.clone(),canonical_sha256(&canonical_rows(table,rows).map_err(|_|())?).map_err(|_|())?))).collect::<Result<_,()>>()?;
        let bundle=LegacyBundle{version:1,exported_at:"2026-01-15T00:00:00Z".into(),processing_version:"synthetic-local-v1".into(),tables,table_sha256:hashes,source_schema:LEGACY_TABLES.into_iter().map(|table|(table.to_owned(),json!([]))).collect(),safety_ledger:None};
        let db=Db::connect(&url).await.map_err(|_|())?;
        import_bundle(&db,&bundle).await.map_err(|_|())?;
        Ok::<_,()>(())
    }.await;
    if result.is_ok() {
        println!("Synthetic Buycycle fixtures ready.");
        std::process::ExitCode::SUCCESS
    } else {
        eprintln!(
            "Synthetic seeding refused; use an explicitly enabled disposable local database."
        );
        std::process::ExitCode::FAILURE
    }
}
