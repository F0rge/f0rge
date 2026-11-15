-- Apply in the controlled migration step, never during API startup.
-- Archive tables are append-only for the runtime login.
GRANT SELECT, INSERT, UPDATE ON legacy_record, user_state, collection_day, collector_runs TO buycycle_runtime;
GRANT SELECT, INSERT ON user_state_history, browser_import, source_snapshots TO buycycle_runtime;
GRANT SELECT ON import_manifest TO buycycle_runtime;
