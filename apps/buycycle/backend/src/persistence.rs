//! App-owned PostgreSQL storage. Schema changes run only through `migrate`.
use std::{fmt, time::Duration};

use diesel::{
    sql_query,
    sql_types::{BigInt, Jsonb, Text},
};
use diesel_async::{
    AsyncConnection, AsyncPgConnection, RunQueryDsl, SimpleAsyncConnection,
    pooled_connection::{AsyncDieselConnectionManager, bb8::Pool},
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use uuid::Uuid;

pub const LEGACY_TABLES: [&str; 5] = ["listing", "price_history", "detail", "runs", "country_map"];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum DataError {
    Database,
    InvalidInput,
    Conflict,
    Reconciliation,
}
pub type DbError = DataError;
impl fmt::Display for DataError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::Database => "Database operation failed",
            Self::InvalidInput => "Invalid data input",
            Self::Conflict => "Data changed; review the current revision",
            Self::Reconciliation => "Data reconciliation failed",
        })
    }
}
impl std::error::Error for DataError {}
impl From<diesel::result::Error> for DataError {
    fn from(_: diesel::result::Error) -> Self {
        Self::Database
    }
}

#[derive(Clone)]
pub struct Db {
    pool: Pool<AsyncPgConnection>,
    url: String,
}
impl fmt::Debug for Db {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("Db([redacted connection])")
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, diesel::QueryableByName)]
pub struct StoredState {
    #[diesel(sql_type = BigInt)]
    pub revision: i64,
    #[diesel(sql_type = Jsonb)]
    pub state: Value,
}
#[derive(diesel::QueryableByName)]
struct JsonRow {
    #[diesel(sql_type = Jsonb)]
    payload: Value,
}

pub fn empty_state() -> Value {
    json!({"version":1,"bikes":{"watch":{},"log":[],"costs":{}},"wheels":{"watch":{},"log":[],"costs":{}}})
}

/// Keys encode the original primary-key tuple, without delimiter ambiguity.
pub fn row_key(table: &str, row: &Value) -> Result<String, DataError> {
    let object = row.as_object().ok_or(DataError::InvalidInput)?;
    let fields: &[&str] = match table {
        "listing" | "detail" => &["id"],
        "price_history" => &["id", "day"],
        "runs" => &["day", "kind"],
        "country_map" => &["cid"],
        _ => return Err(DataError::InvalidInput),
    };
    let mut key = Vec::new();
    for field in fields {
        let value = object.get(*field).ok_or(DataError::InvalidInput)?;
        if *field == "cid" {
            if value.as_i64().is_none() {
                return Err(DataError::InvalidInput);
            }
        } else if value.as_str().is_none_or(str::is_empty) {
            return Err(DataError::InvalidInput);
        }
        key.push(value.clone());
    }
    serde_json::to_string(&key).map_err(|_| DataError::InvalidInput)
}

impl Db {
    pub async fn connect(url: &str) -> Result<Self, DataError> {
        let manager = AsyncDieselConnectionManager::<AsyncPgConnection>::new(url);
        let pool = Pool::builder()
            .max_size(8)
            .connection_timeout(Duration::from_secs(10))
            .build(manager)
            .await
            .map_err(|_| DataError::Database)?;
        Ok(Self {
            pool,
            url: url.to_owned(),
        })
    }
    /// A fresh owned session: dropping a collector lease closes its advisory lock.
    pub async fn connection(&self) -> Result<AsyncPgConnection, DataError> {
        AsyncPgConnection::establish(&self.url)
            .await
            .map_err(|_| DataError::Database)
    }
    pub async fn health(&self) -> Result<(), DataError> {
        let mut connection = self.pool.get().await.map_err(|_| DataError::Database)?;
        #[derive(diesel::QueryableByName)]
        struct Ready {
            #[diesel(sql_type=Text)]
            version: String,
        }
        let checksum = format!(
            "{:x}",
            Sha256::digest(include_str!("../migrations/0001_initial/up.sql").as_bytes())
        );
        let ready=sql_query("SELECT version FROM buycycle_schema_migrations WHERE version='0001_initial' AND checksum=$1")
            .bind::<Text,_>(checksum).get_result::<Ready>(&mut connection).await?;
        if ready.version != "0001_initial" {
            return Err(DataError::Reconciliation);
        }
        Ok(())
    }
    /// Explicit controlled migration entry point; never called by HTTP startup.
    pub async fn migrate(&self) -> Result<(), DataError> {
        let mut connection = self.connection().await?;
        AsyncPgConnection::transaction::<_, DataError, _>(&mut connection, async move |connection| {
            sql_query("SELECT pg_advisory_xact_lock(731957310)").execute(&mut *connection).await?;
            connection.batch_execute("CREATE TABLE IF NOT EXISTS buycycle_schema_migrations(version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT clock_timestamp())").await?;
            #[derive(diesel::QueryableByName)]
            struct Applied { #[diesel(sql_type=Text)] checksum:String }
            let source=include_str!("../migrations/0001_initial/up.sql");
            let checksum=format!("{:x}",Sha256::digest(source.as_bytes()));
            let applied=sql_query("SELECT checksum FROM buycycle_schema_migrations WHERE version='0001_initial'").load::<Applied>(&mut *connection).await?;
            if let Some(applied)=applied.first() {
                return if applied.checksum==checksum {Ok(())} else {Err(DataError::Reconciliation)};
            }
            connection.batch_execute(source).await?;
            sql_query("INSERT INTO buycycle_schema_migrations(version,checksum) VALUES ('0001_initial',$1)").bind::<Text,_>(checksum).execute(&mut *connection).await?;
            Ok(())
        }).await
    }
    /// Release/operator step only. The runtime login and its schema privileges
    /// must already be provisioned; failure rolls back every table grant.
    pub async fn grant_runtime(&self) -> Result<(), DataError> {
        let mut connection = self.connection().await?;
        AsyncPgConnection::transaction::<_, DataError, _>(
            &mut connection,
            async move |connection| {
                connection
                    .batch_execute(include_str!("../../ops/grant-runtime.sql"))
                    .await?;
                Ok(())
            },
        )
        .await
    }
    pub async fn rows(&self, table: &str) -> Result<Vec<Value>, DataError> {
        if !LEGACY_TABLES.contains(&table) {
            return Err(DataError::InvalidInput);
        }
        let mut connection = self.pool.get().await.map_err(|_| DataError::Database)?;
        let rows =
            sql_query("SELECT payload FROM legacy_record WHERE table_name=$1 ORDER BY row_key")
                .bind::<Text, _>(table)
                .load::<JsonRow>(&mut connection)
                .await?;
        Ok(rows.into_iter().map(|row| row.payload).collect())
    }
    pub async fn listings(&self, kind: &str) -> Result<Vec<Value>, DataError> {
        if !["bikes", "wheels"].contains(&kind) {
            return Err(DataError::InvalidInput);
        }
        let mut connection = self.pool.get().await.map_err(|_| DataError::Database)?;
        let rows = sql_query("SELECT payload FROM legacy_record WHERE table_name='listing' AND payload->>'kind'=$1 ORDER BY row_key")
            .bind::<Text,_>(kind).load::<JsonRow>(&mut connection).await?;
        Ok(rows.into_iter().map(|row| row.payload).collect())
    }
    /// Related reads share one immutable PostgreSQL MVCC snapshot, including during publication.
    pub async fn read_tables_snapshot(
        &self,
        tables: &[&str],
    ) -> Result<std::collections::BTreeMap<String, Vec<Value>>, DataError> {
        if tables.iter().any(|table| !LEGACY_TABLES.contains(table)) {
            return Err(DataError::InvalidInput);
        }
        let tables: Vec<String> = tables.iter().map(|s| (*s).to_owned()).collect();
        let mut connection = self.pool.get().await.map_err(|_| DataError::Database)?;
        AsyncPgConnection::transaction::<_, DataError, _>(
            &mut connection,
            async move |connection| {
                connection
                    .batch_execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                    .await?;
                let mut snapshot = std::collections::BTreeMap::new();
                for table in tables {
                    let rows = sql_query(
                        "SELECT payload FROM legacy_record WHERE table_name=$1 ORDER BY row_key",
                    )
                    .bind::<Text, _>(&table)
                    .load::<JsonRow>(&mut *connection)
                    .await?;
                    snapshot.insert(table, rows.into_iter().map(|r| r.payload).collect());
                }
                Ok(snapshot)
            },
        )
        .await
    }
    pub async fn upsert_rows(&self, table: &str, rows: &[Value]) -> Result<(), DataError> {
        self.upsert_tables(&[(table, rows.to_vec())]).await
    }
    /// Publish related observations as one unit; any PostgreSQL failure rolls all tables back.
    pub async fn upsert_tables(&self, tables: &[(&str, Vec<Value>)]) -> Result<(), DataError> {
        let mut keyed = Vec::new();
        for (table, rows) in tables {
            for row in rows {
                keyed.push(((*table).to_owned(), row_key(table, row)?, row.clone()));
            }
        }
        let mut connection = self.pool.get().await.map_err(|_| DataError::Database)?;
        AsyncPgConnection::transaction::<_,DataError,_>(&mut connection,async move |connection|{
            for(table,key,payload)in keyed{
                sql_query("INSERT INTO legacy_record(table_name,row_key,payload) VALUES($1,$2,$3) ON CONFLICT(table_name,row_key) DO UPDATE SET payload=EXCLUDED.payload")
                    .bind::<Text,_>(table).bind::<Text,_>(key).bind::<Jsonb,_>(payload).execute(&mut *connection).await?;
            }
            Ok(())
        }).await
    }
    pub async fn user_state(&self, subject: &str) -> Result<StoredState, DataError> {
        if subject.is_empty() || subject.len() > 512 {
            return Err(DataError::InvalidInput);
        }
        let mut connection = self.pool.get().await.map_err(|_| DataError::Database)?;
        let rows = sql_query("SELECT revision,state FROM user_state WHERE subject=$1")
            .bind::<Text, _>(subject)
            .load::<StoredState>(&mut connection)
            .await?;
        Ok(rows.into_iter().next().unwrap_or_else(|| StoredState {
            revision: 0,
            state: empty_state(),
        }))
    }
    pub async fn compare_and_swap_state(
        &self,
        subject: &str,
        expected: i64,
        state: Value,
    ) -> Result<StoredState, DataError> {
        if subject.is_empty() || subject.len() > 512 || expected < 0 || !state.is_object() {
            return Err(DataError::InvalidInput);
        }
        let subject = subject.to_owned();
        let mut connection = self.pool.get().await.map_err(|_| DataError::Database)?;
        AsyncPgConnection::transaction::<_, DataError, _>(&mut connection, async move |connection| {
            sql_query("INSERT INTO user_state(subject,revision,state) VALUES($1,0,$2) ON CONFLICT DO NOTHING")
                .bind::<Text,_>(&subject).bind::<Jsonb,_>(empty_state()).execute(&mut *connection).await?;
            let mut rows=sql_query("UPDATE user_state SET revision=revision+1,state=$1,updated_at=clock_timestamp() WHERE subject=$2 AND revision=$3 RETURNING revision,state")
                .bind::<Jsonb,_>(state).bind::<Text,_>(&subject).bind::<BigInt,_>(expected).load::<StoredState>(&mut *connection).await?;
            let next=rows.pop().ok_or(DataError::Conflict)?;
            sql_query("INSERT INTO user_state_history(subject,revision,state) VALUES($1,$2,$3)")
                .bind::<Text,_>(&subject).bind::<BigInt,_>(next.revision).bind::<Jsonb,_>(&next.state).execute(&mut *connection).await?;
            Ok(next)
        }).await
    }
    /// Archive original browser exports and their explicit reviewed result atomically.
    pub async fn import_browser_state(
        &self,
        subject: &str,
        expected: i64,
        state: &Value,
        source: &Value,
    ) -> Result<StoredState, DataError> {
        if subject.is_empty()
            || subject.len() > 512
            || expected < 0
            || !state.is_object()
            || !source.is_object()
        {
            return Err(DataError::InvalidInput);
        }
        let subject = subject.to_owned();
        let state = state.clone();
        let source = source.clone();
        let digest = format!(
            "{:x}",
            Sha256::digest(serde_json::to_vec(&source).map_err(|_| DataError::InvalidInput)?)
        );
        let mut connection = self.pool.get().await.map_err(|_| DataError::Database)?;
        AsyncPgConnection::transaction::<_, DataError, _>(&mut connection, async move |connection| {
            sql_query("INSERT INTO user_state(subject,revision,state) VALUES($1,0,$2) ON CONFLICT DO NOTHING")
                .bind::<Text,_>(&subject).bind::<Jsonb,_>(empty_state()).execute(&mut *connection).await?;
            // Serialize this subject's imports with ordinary state updates.
            let current=sql_query("SELECT revision,state FROM user_state WHERE subject=$1 FOR UPDATE")
                .bind::<Text,_>(&subject).get_result::<StoredState>(&mut *connection).await?;
            #[derive(diesel::QueryableByName)]
            struct Previous { #[diesel(sql_type=BigInt)] state_revision:i64 }
            let previous=sql_query("SELECT state_revision FROM browser_import WHERE subject=$1 AND sha256=$2")
                .bind::<Text,_>(&subject).bind::<Text,_>(&digest).load::<Previous>(&mut *connection).await?;
            if let Some(previous)=previous.first() {
                if previous.state_revision==current.revision && current.state==state { return Ok(current); }
                return Err(DataError::Conflict);
            }
            if current.revision!=expected { return Err(DataError::Conflict); }
            let next=sql_query("UPDATE user_state SET revision=revision+1,state=$1,updated_at=clock_timestamp() WHERE subject=$2 RETURNING revision,state")
                .bind::<Jsonb,_>(state).bind::<Text,_>(&subject).get_result::<StoredState>(&mut *connection).await?;
            sql_query("INSERT INTO user_state_history(subject,revision,state) VALUES($1,$2,$3)")
                .bind::<Text,_>(&subject).bind::<BigInt,_>(next.revision).bind::<Jsonb,_>(&next.state).execute(&mut *connection).await?;
            sql_query("INSERT INTO browser_import(id,subject,sha256,source,state_revision) VALUES($1,$2,$3,$4,$5)")
                .bind::<diesel::sql_types::Uuid,_>(Uuid::new_v4()).bind::<Text,_>(&subject).bind::<Text,_>(digest).bind::<Jsonb,_>(source).bind::<BigInt,_>(next.revision).execute(&mut *connection).await?;
            Ok(next)
        }).await
    }
}
