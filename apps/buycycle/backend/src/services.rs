use crate::{
    contracts::*,
    metrics,
    persistence::{DataError, Db, StoredState},
};
use actix_web::web;
use chrono::{NaiveDate, Utc};
use f0rge_api_errors::{ApiError, FieldError, FieldErrorCode};
use serde_json::Value;
use std::{
    pin::Pin,
    sync::{Arc, LazyLock, Mutex},
    task::{Context, Poll, Waker},
    time::Duration,
};

/// Keep one report's capacity reserved until its body is drained or disconnected.
/// Each transport chunk owns only its bounded copy, never the whole allocation.
pub struct ListingsBody {
    encoded_length: u64,
    state: Arc<Mutex<ReportState>>,
    deadline: tokio::task::JoinHandle<()>,
}
struct ReportState {
    bytes: Option<Vec<u8>>,
    offset: usize,
    permit: Option<tokio::sync::OwnedSemaphorePermit>,
    expired: bool,
    waker: Option<Waker>,
}
impl ListingsBody {
    fn new(bytes: Vec<u8>, permit: tokio::sync::OwnedSemaphorePermit, bound: Duration) -> Self {
        let encoded_length = bytes.len() as u64;
        let state = Arc::new(Mutex::new(ReportState {
            bytes: Some(bytes),
            offset: 0,
            permit: Some(permit),
            expired: false,
            waker: None,
        }));
        let weak = Arc::downgrade(&state);
        let deadline = tokio::spawn(async move {
            tokio::time::sleep(bound).await;
            if let Some(state) = weak.upgrade() {
                let mut state = state.lock().expect("report body state");
                // A stalled transport may never poll the body again. Drop its
                // allocation and capacity independently of transport progress.
                state.expired = state.bytes.take().is_some();
                state.permit.take();
                if let Some(waker) = state.waker.take() {
                    waker.wake();
                }
            }
        });
        Self {
            encoded_length,
            state,
            deadline,
        }
    }
}
impl Drop for ListingsBody {
    fn drop(&mut self) {
        self.deadline.abort();
    }
}
impl actix_web::body::MessageBody for ListingsBody {
    type Error = std::io::Error;

    fn size(&self) -> actix_web::body::BodySize {
        // Expiry before encoding must still poll the timeout error, rather than
        // allowing the transport to claim a successful empty response.
        actix_web::body::BodySize::Sized(self.encoded_length)
    }

    fn poll_next(
        self: Pin<&mut Self>,
        cx: &mut Context<'_>,
    ) -> Poll<Option<Result<web::Bytes, Self::Error>>> {
        let mut state = self.state.lock().expect("report body state");
        if state.expired {
            state.expired = false;
            return Poll::Ready(Some(Err(std::io::Error::new(
                std::io::ErrorKind::TimedOut,
                "Report body delivery timed out",
            ))));
        }
        state.waker = Some(cx.waker().clone());
        let Some(bytes) = state.bytes.as_ref() else {
            state.permit.take();
            return Poll::Ready(None);
        };
        let end = (state.offset + 64 * 1024).min(bytes.len());
        let chunk = web::Bytes::copy_from_slice(&bytes[state.offset..end]);
        if end == bytes.len() {
            // The returned last chunk must not keep this allocation alive after
            // the next poll releases capacity for another calculation.
            state.bytes = None;
        }
        state.offset = end;
        Poll::Ready(Some(Ok(chunk)))
    }
}

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
pub async fn listings(db: &Db, kind: Kind) -> Result<ListingsBody, ApiError> {
    // Acquire before loading a snapshot. Keep the permit in the blocking task:
    // cancelling a caller must not allow a second heavy calculation beside it.
    static REPORT: LazyLock<Arc<tokio::sync::Semaphore>> =
        LazyLock::new(|| Arc::new(tokio::sync::Semaphore::new(1)));
    let permit = REPORT
        .clone()
        .acquire_owned()
        .await
        .map_err(ApiError::internal_from)?;
    let input = calculation_input(db, kind, Utc::now()).await?;
    actix_web::rt::task::spawn_blocking(move || {
        let report = metrics::report_raw(input);
        let bytes = serde_json::to_vec(&report).map_err(ApiError::internal_from)?;
        drop(report);
        // This is a memory-safety failure bound for stalled delivery, not an SLO.
        Ok(ListingsBody::new(bytes, permit, Duration::from_secs(120)))
    })
    .await
    .map_err(ApiError::internal_from)?
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

#[cfg(test)]
mod tests {
    use super::*;
    use actix_web::body::MessageBody;

    #[tokio::test]
    async fn report_body_bounds_transport_allocations_and_releases_capacity_on_eof_or_drop() {
        let gate = Arc::new(tokio::sync::Semaphore::new(1));
        let bytes: Vec<u8> = (0..150_000).map(|i| (i % 251) as u8).collect();
        let mut body = ListingsBody::new(
            bytes.clone(),
            gate.clone().acquire_owned().await.unwrap(),
            Duration::from_secs(120),
        );
        let mut received = Vec::new();
        let mut chunks = Vec::new();
        while let Some(chunk) =
            futures_util::future::poll_fn(|cx| Pin::new(&mut body).poll_next(cx)).await
        {
            let chunk = chunk.unwrap();
            assert!(chunk.len() <= 64 * 1024);
            assert_eq!(gate.available_permits(), 0);
            received.extend_from_slice(&chunk);
            chunks.push(chunk);
        }
        assert_eq!(received, bytes);
        assert!(body.state.lock().unwrap().bytes.is_none());
        // Retaining transport chunks after EOF does not retain the full source
        // allocation or its report permit, including the last partial chunk.
        assert_eq!(chunks.last().unwrap().len(), 18_928);
        assert_eq!(gate.available_permits(), 1);

        let body = ListingsBody::new(
            bytes,
            gate.clone().acquire_owned().await.unwrap(),
            Duration::from_secs(120),
        );
        assert_eq!(gate.available_permits(), 0);
        drop(body);
        assert_eq!(gate.available_permits(), 1);
    }

    #[tokio::test]
    async fn stalled_report_expires_without_polling_and_a_dropped_body_has_no_retained_state() {
        let gate = Arc::new(tokio::sync::Semaphore::new(1));
        let mut body = ListingsBody::new(
            vec![7; 150_000],
            gate.clone().acquire_owned().await.unwrap(),
            Duration::from_millis(10),
        );
        tokio::time::sleep(Duration::from_millis(30)).await;
        assert_eq!(gate.available_permits(), 1);
        assert!(body.state.lock().unwrap().bytes.is_none());
        assert_eq!(body.size(), actix_web::body::BodySize::Sized(150_000));
        let error = futures_util::future::poll_fn(|cx| Pin::new(&mut body).poll_next(cx))
            .await
            .unwrap()
            .unwrap_err();
        assert_eq!(error.kind(), std::io::ErrorKind::TimedOut);

        for bound in [Duration::ZERO, Duration::from_secs(120)] {
            let body = ListingsBody::new(
                vec![7; 150_000],
                gate.clone().acquire_owned().await.unwrap(),
                bound,
            );
            let weak = Arc::downgrade(&body.state);
            drop(body);
            tokio::task::yield_now().await;
            assert!(weak.upgrade().is_none());
            assert_eq!(gate.available_permits(), 1);
        }
    }
}
