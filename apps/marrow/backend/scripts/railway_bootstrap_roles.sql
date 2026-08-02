-- Railway Postgres bootstrap for marrow (pgvector + RLS roles).
-- Run as the Postgres owner / superuser after the pgvector service is healthy.
--
-- Required env (psql \set or shell export before substituting):
--   :app_password  — HEALTHTRACKER_APP_PASSWORD
--   :ro_password   — HEALTHTRACKER_RO_PASSWORD
--   :migrate_password — password for htmigrate (migrations)
--
-- Example:
--   psql "$DATABASE_PUBLIC_URL" -v app_password="$HEALTHTRACKER_APP_PASSWORD" \
--     -v ro_password="$HEALTHTRACKER_RO_PASSWORD" \
--     -v migrate_password="$MIGRATE_PASSWORD" \
--     -f apps/marrow/backend/scripts/railway_bootstrap_roles.sql

CREATE EXTENSION IF NOT EXISTS vector;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'healthtracker_app') THEN
    CREATE ROLE healthtracker_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'healthtracker_ro') THEN
    CREATE ROLE healthtracker_ro WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'htmigrate') THEN
    CREATE ROLE htmigrate WITH LOGIN NOSUPERUSER CREATEDB CREATEROLE NOREPLICATION;
  END IF;
END
$$;

ALTER ROLE healthtracker_app PASSWORD :'app_password';
ALTER ROLE healthtracker_ro PASSWORD :'ro_password';
ALTER ROLE htmigrate PASSWORD :'migrate_password';

DO $$
BEGIN
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO healthtracker_app', current_database());
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO healthtracker_ro', current_database());
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO htmigrate', current_database());
  EXECUTE format('GRANT ALL ON DATABASE %I TO htmigrate', current_database());
END
$$;

GRANT USAGE ON SCHEMA public TO healthtracker_app, healthtracker_ro, htmigrate;
GRANT ALL ON SCHEMA public TO htmigrate;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO healthtracker_app;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO healthtracker_ro;
GRANT ALL ON ALL TABLES IN SCHEMA public TO htmigrate;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO healthtracker_app, htmigrate;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO healthtracker_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO healthtracker_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON TABLES TO htmigrate;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO healthtracker_app, htmigrate;

-- pg_restore --no-owner leaves tables owned by the restore user (Railway
-- ``postgres``). htmigrate has GRANT ALL but not ownership — Alembic ALTER
-- on existing tables needs SET LOCAL ROLE <owner>. Grant membership here.
DO $$
DECLARE
  owner_role name := current_user;
BEGIN
  IF owner_role <> 'htmigrate' THEN
    EXECUTE format('GRANT %I TO htmigrate', owner_role);
  END IF;
END
$$;

-- After this script: set FLY_MPG_SKIP_ROLE_DDL=1 on Railway services so
-- migrations 004/019 skip role DDL (roles already exist).
