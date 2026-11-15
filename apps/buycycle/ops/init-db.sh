#!/bin/bash
set -euo pipefail
# Executed once by the dedicated PostgreSQL cluster; runtime cannot create schema.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 <<'SQL'
-- The PostgreSQL administrator reads the mounted secret files directly. No
-- password is placed in the shell environment, psql argv or generated files.
DO $bootstrap$
DECLARE runtime_secret text; migrator_secret text; backup_secret text;
BEGIN
  runtime_secret := rtrim(pg_read_file('/run/secrets/runtime_password'), E'\n');
  migrator_secret := rtrim(pg_read_file('/run/secrets/migrator_password'), E'\n');
  backup_secret := rtrim(pg_read_file('/run/secrets/backup_password'), E'\n');
  IF length(runtime_secret) < 32 OR length(migrator_secret) < 32 OR length(backup_secret) < 32
    OR runtime_secret = migrator_secret OR runtime_secret = backup_secret OR migrator_secret = backup_secret THEN
    RAISE EXCEPTION 'Managed role passwords must contain at least 32 characters';
  END IF;
  EXECUTE format('CREATE ROLE buycycle_runtime LOGIN PASSWORD %L', runtime_secret);
  EXECUTE format('CREATE ROLE buycycle_migrator LOGIN PASSWORD %L', migrator_secret);
  EXECUTE format('CREATE ROLE buycycle_backup LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L', backup_secret);
EXCEPTION WHEN OTHERS THEN
  -- Replace the original dynamic-SQL error/context, which may contain secrets.
  RAISE EXCEPTION 'Managed database role bootstrap failed; inspect secret custody and role prerequisites';
END
$bootstrap$;
REVOKE ALL ON DATABASE buycycle FROM PUBLIC;
GRANT CONNECT ON DATABASE buycycle TO buycycle_runtime, buycycle_migrator, buycycle_backup;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO buycycle_runtime;
GRANT USAGE ON SCHEMA public TO buycycle_backup;
GRANT USAGE, CREATE ON SCHEMA public TO buycycle_migrator;
ALTER DEFAULT PRIVILEGES FOR ROLE buycycle_migrator IN SCHEMA public GRANT SELECT ON TABLES TO buycycle_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE buycycle_migrator IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO buycycle_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE buycycle_migrator IN SCHEMA public GRANT SELECT ON TABLES TO buycycle_backup;
ALTER DEFAULT PRIVILEGES FOR ROLE buycycle_migrator IN SCHEMA public GRANT SELECT ON SEQUENCES TO buycycle_backup;
SQL
