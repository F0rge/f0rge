use crate::{
    contracts::*,
    metrics,
    persistence::{DataError, Db, StoredState},
};
use chrono::{NaiveDate, Utc};
use f0rge_api_errors::{ApiError, FieldError, FieldErrorCode};
use serde_json::Value;

pub fn data_error(error: DataError) -> ApiError {
    match error {
        DataError::Conflict => ApiError::conflict(),
        DataError::InvalidInput | DataError::Reconciliation => invalid("state"),
        DataError::Database => ApiError::internal(),
    }
}
pub fn invalid(field: &'static str) -> ApiError {
    ApiError::validation(vec![
        FieldError::new(field, FieldErrorCode::Invalid).expect("fixed schema field"),
    ])
}
fn valid_date(s: &str) -> bool {
    NaiveDate::parse_from_str(s, "%Y-%m-%d").is_ok_and(|d| d.to_string() == s)
}
fn valid_url(s: &str) -> bool {
    s.is_empty()
        || reqwest::Url::parse(s).is_ok_and(|u| {
            u.scheme() == "https" && u.username().is_empty() && u.password().is_none()
        })
}
pub fn validate_state(state: &BrowserState) -> Result<(), ApiError> {
    if state.version != 1 {
        return Err(invalid("version"));
    }
    for category in [&state.bikes, &state.wheels] {
        if category.watch.len() > 50000 || category.log.len() > 50000 {
            return Err(invalid("state"));
        }
        for (id, w) in &category.watch {
            if id.is_empty()
                || id.len() > 256
                || w.n.trim().is_empty()
                || w.n.len() > 4000
                || !w.p.is_finite()
                || w.p < 0.
                || !valid_date(&w.t)
                || !valid_url(&w.u)
            {
                return Err(invalid("watch"));
            }
        }
        for t in &category.log {
            if t.name.trim().is_empty()
                || t.name.len() > 4000
                || !valid_url(&t.url)
                || !t.buy.is_finite()
                || t.buy < 0.
                || !valid_date(&t.bd)
                || t.sell.is_some_and(|v| !v.is_finite() || v < 0.)
                || t.sd
                    .as_ref()
                    .is_some_and(|d| !d.is_empty() && !valid_date(d))
            {
                return Err(invalid("log"));
            }
            if let Some(sold) = t.sd.as_deref().filter(|s| !s.is_empty())
                && sold < t.bd.as_str()
            {
                return Err(invalid("log"));
            }
        }
        for (key, value) in &category.costs {
            if key.is_empty()
                || key.len() > 128
                || !value.is_finite()
                || *value < 0.
                || matches!(key.as_str(), "bp" | "pay" | "haircut" | "sellfee") && *value > 100.
            {
                return Err(invalid("costs"));
            }
        }
    }
    Ok(())
}
fn state_response(record: StoredState) -> Result<StateResponse, ApiError> {
    let mut state: BrowserState =
        serde_json::from_value(record.state).map_err(ApiError::internal_from)?;
    for (category, kind) in [
        (&mut state.bikes, Kind::Bikes),
        (&mut state.wheels, Kind::Wheels),
    ] {
        for (k, v) in metrics::default_costs(&kind) {
            category.costs.entry(k).or_insert(v);
        }
    }
    Ok(StateResponse {
        revision: record.revision,
        state,
    })
}
pub async fn calculation_input(
    db: &Db,
    kind: Kind,
    now: chrono::DateTime<Utc>,
) -> Result<metrics::CalculationInput<Box<serde_json::value::RawValue>>, ApiError> {
    let snapshot = db
        .calculation_snapshot(kind.as_str())
        .await
        .map_err(data_error)?;
    Ok(metrics::CalculationInput {
        rows: snapshot.rows,
        details: snapshot.details,
        history: snapshot.history,
        countries: snapshot.countries,
        runs: snapshot.runs,
        kind,
        calculated_at: now,
    })
}
pub async fn listings(db: &Db, kind: Kind) -> Result<ListingsResponse, ApiError> {
    // Acquire before loading a snapshot. Keep the permit in the blocking task:
    // cancelling a caller must not allow a second heavy calculation beside it.
    static REPORT: tokio::sync::Semaphore = tokio::sync::Semaphore::const_new(1);
    let permit = REPORT.acquire().await.map_err(ApiError::internal_from)?;
    let input = calculation_input(db, kind, Utc::now()).await?;
    actix_web::rt::task::spawn_blocking(move || {
        let _permit = permit;
        metrics::report_raw(input)
    })
    .await
    .map_err(ApiError::internal_from)
}
pub async fn read_state(db: &Db, subject: &str) -> Result<StateResponse, ApiError> {
    state_response(db.user_state(subject).await.map_err(data_error)?)
}
pub async fn write_state(
    db: &Db,
    subject: &str,
    write: StateWrite,
) -> Result<StateResponse, ApiError> {
    if write.expected_revision < 0 {
        return Err(invalid("expected_revision"));
    }
    validate_state(&write.state)?;
    let state = serde_json::to_value(write.state).map_err(ApiError::internal_from)?;
    state_response(
        db.compare_and_swap_state(subject, write.expected_revision, state)
            .await
            .map_err(data_error)?,
    )
}
pub async fn preview_import(
    db: &Db,
    subject: &str,
    write: &ImportWrite,
) -> Result<ImportPreview, ApiError> {
    validate_state(&write.state)?;
    if !write.source.is_object() || write.expected_revision < 0 {
        return Err(invalid("source"));
    }
    let current = db.user_state(subject).await.map_err(data_error)?;
    if current.revision != write.expected_revision {
        return Err(ApiError::conflict());
    }
    Ok(ImportPreview{expected_revision:current.revision,counts:ImportCounts{watches:write.state.bikes.watch.len()+write.state.wheels.watch.len(),trades:write.state.bikes.log.len()+write.state.wheels.log.len(),costs:write.state.bikes.costs.len()+write.state.wheels.costs.len()},warnings:vec!["The original import document is retained; existing server state changes only when you explicitly commit this preview.".into()]})
}
pub async fn import_state(
    db: &Db,
    subject: &str,
    write: ImportWrite,
) -> Result<StateResponse, ApiError> {
    validate_state(&write.state)?;
    if !write.source.is_object() || write.expected_revision < 0 {
        return Err(invalid("source"));
    }
    let state = serde_json::to_value(write.state).map_err(ApiError::internal_from)?;
    state_response(
        db.import_browser_state(subject, write.expected_revision, &state, &write.source)
            .await
            .map_err(data_error)?,
    )
}
pub async fn status(db: &Db, subject: String) -> Result<StatusResponse, ApiError> {
    let runs = db.rows("runs").await.map_err(data_error)?;
    let last_success = runs
        .iter()
        .filter(|r| {
            r.get("collection_complete")
                .or_else(|| r.get("complete"))
                .and_then(Value::as_i64)
                == Some(1)
        })
        .filter_map(|r| r.get("day").and_then(Value::as_str))
        .max()
        .map(str::to_owned);
    let today = Utc::now()
        .with_timezone(&chrono_tz::Europe::Luxembourg)
        .date_naive()
        .to_string();
    let ledger = crate::collector::ledger_status(db)
        .await
        .map_err(data_error)?;
    let stale = last_success.as_deref() != Some(&today);
    let partial = crate::collector::has_incomplete_run_today(db)
        .await
        .map_err(data_error)?
        || runs.iter().any(|r| {
            r.get("day").and_then(Value::as_str) == Some(today.as_str())
                && r.get("collection_complete")
                    .or_else(|| r.get("complete"))
                    .and_then(Value::as_i64)
                    != Some(1)
        });
    Ok(StatusResponse {
        status: if ledger.1 {
            "blocked"
        } else if partial {
            "partial"
        } else if stale {
            "stale"
        } else {
            "ready"
        }
        .into(),
        last_success,
        stale,
        blocked: ledger.1,
        detail_attempts: ledger.0,
        detail_limit: 150,
        version: env!("CARGO_PKG_VERSION").into(),
        identity: Identity { subject },
    })
}
