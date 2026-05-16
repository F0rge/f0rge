# Embedding pipeline — keep `embedding` in sync automatically

## Why this exists

Issue #48 created the `embedding` table and the `EmbeddingClient` contract but left the table empty by design. Issue #49 fills it: every relevant write to a source table (`entries`, `labs`, `treatments`, `photo_analyses`) is captured by an AFTER trigger, enqueued in `embedding_queue`, picked up by a long-running worker process, chunked, embedded via OpenRouter, and UPSERTed into `embedding`. The point is that downstream features (RAG, search, MCP tools that need semantic similarity) can assume `embedding` is durably in sync with the source data — no manual cron job, no application-level "remember to call the embedder" hooks.

## How writes flow

1. App writes to a watched column on a watched table — any write path: ORM, raw SQL, `COPY`, a backfill script. The schema does not care who issued the statement.
2. The AFTER `INSERT OR UPDATE OF <watched cols> OR DELETE` trigger fires `enqueue_embedding()` (defined in migration `005`).
3. `enqueue_embedding()` inserts a row into `embedding_queue` (durable; survives worker downtime or Postgres restart) AND issues `pg_notify('embedding_queue', 'wake')`.
4. The `embedding-worker` container holds a `LISTEN embedding_queue` connection and also polls every `EMBEDDING_WORKER_POLL_INTERVAL_SECONDS` (default 5s) as a fallback in case a notify is dropped (e.g. listener was reconnecting at the moment of the notify).
5. On wake, the worker claims up to `EMBEDDING_WORKER_BATCH_SIZE` rows (default 10) using `SELECT ... FOR UPDATE SKIP LOCKED` — multiple worker replicas can run safely if needed.
6. For each claimed row:
   - Fetch the source row by `(source_table, source_id)`.
   - Run it through the matching serializer in `app.embedding_pipeline.serialization.SERIALIZERS`, which produces a normalized text document.
   - Chunk per the rules in `ai_seams.md` (markdown-aware H2 split, 800 token max, 100 token overlap within an H2 section).
   - Call `EmbeddingClient.embed_batch(chunks)` (OpenRouter, model = current `user_settings.embedding_model`).
   - `UPSERT INTO embedding (source_table, source_id, chunk_index, chunk_text, embedding, embedding_model)` keyed on the unique index.
   - Delete the queue row.

## DELETE handling

When a source row is deleted, the AFTER DELETE trigger enqueues a row with `action='DELETE'` carrying `OLD.id`. The worker handles those by issuing `DELETE FROM embedding WHERE source_table = $1 AND source_id = $2` — every chunk for that source is removed atomically. There are no hard FK constraints between `embedding` and the source tables (by design — see `ai_seams.md`), so cleanup is purely the worker's responsibility.

## UPDATE coalescing

If a row is updated twice in quick succession, both updates enqueue rows. The worker dedups on `(source_table, source_id, action)` when claiming a batch — only the latest write for a given source/action is processed, then `DELETE FROM embedding_queue WHERE source_id = $1 AND created_at <= $2` removes the obsolete entries. This keeps queue depth bounded under chatty write patterns.

## Adding a new embedable table

1. Identify the table and the columns whose content should be embedded.
2. Add a serializer to `backend/app/embedding_pipeline/serialization.py`. The serializer takes a source row dict and returns a markdown string with H2 section headers wherever you want chunk boundaries to fall.
3. Wire it into the `SERIALIZERS: dict[str, Callable]` registry at the top of that module.
4. Create a new Alembic migration that adds the trigger:
   ```sql
   CREATE TRIGGER trg_enqueue_embedding_<table>
   AFTER INSERT OR DELETE OR UPDATE OF <cols>
   ON <table>
   FOR EACH ROW EXECUTE FUNCTION enqueue_embedding();
   ```
5. Run the backfill so existing rows get embeddings:
   ```bash
   docker exec health-tracker-backend uv run python -m app.embedding_pipeline.backfill --table <table>
   ```

## Backfill procedure

For the initial population (and after adding a new embedable table):

```bash
# Dry run — prints how many source rows would be enqueued.
docker exec health-tracker-backend uv run python -m app.embedding_pipeline.backfill --dry-run

# Real run — inserts INSERT-action rows into embedding_queue for every source row.
docker exec health-tracker-backend uv run python -m app.embedding_pipeline.backfill

# Watch the worker drain the queue.
docker logs -f health-tracker-embedding-worker

# Confirm the queue is empty.
docker exec health-tracker-postgres psql -U health -d health \
  -c 'SELECT count(*) FROM embedding_queue;'
```

Backfill is idempotent — re-running it on already-embedded rows is a no-op at the queue layer (deduped on UPSERT) and at the `embedding` layer (unique on `(source_table, source_id, chunk_index, embedding_model)`).

## Troubleshooting

- **Worker logs "permission denied for table embedding"** — the worker is connecting as the wrong role. It must use the read-write `DATABASE_URL` (role `health`), not the read-only `MCP_READONLY_DATABASE_URL` (role `healthtracker_ro`). Check the `embedding-worker` service env in `docker-compose.prod.yml`.
- **Queue rows stuck with `attempts >= 5`** — check the `last_error` column on the queue row:
  ```sql
  SELECT id, source_table, source_id, attempts, last_error
  FROM embedding_queue
  WHERE attempts >= 5
  ORDER BY created_at DESC LIMIT 10;
  ```
  Common causes: OpenRouter rate limit (429), invalid BYOK key (401), model temporarily unavailable. Fix the underlying issue, then `UPDATE embedding_queue SET attempts = 0, last_error = NULL WHERE id = ANY($1)` to retry.
- **Worker never wakes on notify, only polls** — confirm the listener is healthy:
  ```sql
  -- run inside the worker's own DB connection (psql -h ... is no good — must be the worker)
  SELECT * FROM pg_listening_channels();
  ```
  Expect a row with `embedding_queue`. If empty, the worker reconnected and forgot to re-LISTEN — kill and restart the container.
- **Embeddings written under a stale model name** — when the user switches `user_settings.embedding_model`, new chunks use the new model but old chunks remain. The `embedding_model` column is the discriminator; the retrieval layer must filter on the current model to avoid cross-model distance comparisons. Re-embedding old chunks is a separate one-off script (out of scope here; see `ai_seams.md` "Multimodal upgrade path").

## Tuning

| Env var | Default | What it does |
|---|---|---|
| `EMBEDDING_WORKER_POLL_INTERVAL_SECONDS` | `5` | How often the worker checks the queue even without a notify. Lower = lower latency, higher idle CPU. |
| `EMBEDDING_WORKER_BATCH_SIZE` | `10` | Rows claimed per wakeup. Higher = better OpenRouter batching, more memory pressure during chunking. |
| `EMBEDDING_WORKER_MAX_ATTEMPTS` | `5` | Per-row retry limit before the row is parked with `last_error` set. The worker stops touching parked rows until they are manually retried. |

All three are picked up at worker start; restart the `embedding-worker` container after changing them in Coolify env.
