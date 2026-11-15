CREATE TABLE IF NOT EXISTS legacy_record (
    table_name text NOT NULL CHECK (table_name IN ('listing','price_history','detail','runs','country_map')),
    row_key text NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    PRIMARY KEY (table_name, row_key)
);
CREATE INDEX IF NOT EXISTS legacy_listing_kind ON legacy_record ((payload->>'kind')) WHERE table_name='listing';

CREATE TABLE IF NOT EXISTS user_state (
    subject text PRIMARY KEY,
    revision bigint NOT NULL CHECK (revision >= 0),
    state jsonb NOT NULL CHECK (jsonb_typeof(state) = 'object'),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS user_state_history (
    subject text NOT NULL,
    revision bigint NOT NULL,
    state jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (subject, revision)
);
CREATE TABLE IF NOT EXISTS browser_import (
    id uuid PRIMARY KEY,
    subject text NOT NULL,
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    source jsonb NOT NULL,
    state_revision bigint NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (subject, sha256)
);

CREATE TABLE IF NOT EXISTS collection_day (
    day date PRIMARY KEY,
    detail_attempts integer NOT NULL CHECK (detail_attempts BETWEEN 0 AND 150),
    blocked boolean NOT NULL,
    pending boolean NOT NULL,
    feeds jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(feeds) = 'array'),
    next_allowed_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS collector_runs (
    id uuid PRIMARY KEY,
    day date NOT NULL,
    kind text NOT NULL CHECK (kind IN ('bikes','wheels')),
    complete boolean NOT NULL,
    metadata jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE IF NOT EXISTS source_snapshots (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES collector_runs(id),
    kind text NOT NULL CHECK (kind IN ('bikes','wheels')),
    source_kind text NOT NULL,
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    payload jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS source_snapshots_run ON source_snapshots(run_id);

CREATE TABLE IF NOT EXISTS import_manifest (
    bundle_sha256 text PRIMARY KEY CHECK (bundle_sha256 ~ '^[0-9a-f]{64}$'),
    manifest jsonb NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
