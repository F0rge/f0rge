-- Seed the hypothesis scoreboard for handle `leo` only.
-- Not applied by Alembic. Safe to re-run (upserts on user_id + slug).
--
-- Requires FORCE RLS tenant GUC. Run as a role that can SELECT users and
-- INSERT/UPDATE hypotheses, after `alembic upgrade head`.
--
--   cd apps/marrow/backend
--   set -a && . ./.env && set +a
--   psql "$DATABASE_URL_SYNC" -v ON_ERROR_STOP=1 -f scripts/seed_leo_hypotheses.sql
--
-- Or from a session that already has a sync driver:
--   uv run python -c "
--   from pathlib import Path
--   from sqlalchemy import create_engine, text
--   from app.config import settings
--   sql = Path('scripts/seed_leo_hypotheses.sql').read_text()
--   engine = create_engine(settings.database_url.replace('+asyncpg', ''))
--   with engine.begin() as conn:
--       conn.execute(text(sql))
--   "

DO $$
DECLARE
  uid uuid;
BEGIN
  SELECT id INTO uid FROM users WHERE handle = 'leo';
  IF uid IS NULL THEN
    RAISE EXCEPTION 'No user with handle leo — create that user first, then re-run this file';
  END IF;

  PERFORM set_config('app.user_id', uid::text, true);

  INSERT INTO hypotheses (
    id, user_id, slug, title, status, layer, kill_test, next_move, last_evidence, cite, sort_order,
    created_at, updated_at
  ) VALUES
    (gen_random_uuid(), uid, 'l1-sibo-imo', 'L1 SIBO/IMO', 'live', 1,
      'negative prepped H2/CH4 + no high-folate/low-B12', NULL, NULL, NULL, 10,
      (now() at time zone 'utc'), (now() at time zone 'utc')),
    (gen_random_uuid(), uid, 'l2-gastric-b12', 'L2 gastric B12/low acid', 'live', 2,
      'mapped gastric bx clean + neg PCA/IF', NULL, NULL, NULL, 20,
      (now() at time zone 'utc'), (now() at time zone 'utc')),
    (gen_random_uuid(), uid, 'l3-ileum-celiac', 'L3 ileum/celiac-type', 'live', NULL,
      'normal duodenal bx + clean TI', NULL, 'scopes still only ordered; GFD 8 months', NULL, 30,
      (now() at time zone 'utc'), (now() at time zone 'utc')),
    (gen_random_uuid(), uid, 'l4-flare-ibuprofen', 'L4 flare/ibuprofen inflammatory burst', 'live', NULL,
      'flare week where 200mg ibuprofen does nothing and CRP/calprotectin flat', NULL, NULL, NULL, 40,
      (now() at time zone 'utc'), (now() at time zone 'utc')),
    (gen_random_uuid(), uid, 'l5-hpg-quiet', 'L5 HPG quiet after Jul 2026 T course', 'live', NULL,
      'two in-range morning T, LH/FSH not suppressed', NULL, 'Jul 2026 T course', NULL, 50,
      (now() at time zone 'utc'), (now() at time zone 'utc')),
    (gen_random_uuid(), uid, 'k1-structural-heart', 'K1 structural heart', 'killed', NULL,
      NULL, NULL, 'Mar 2026 CUF CAD-RADS 0', 'CUF Mar 2026', 110,
      (now() at time zone 'utc'), (now() at time zone 'utc')),
    (gen_random_uuid(), uid, 'k2-structural-neuro', 'K2 structural/epilepsy neuro', 'killed', NULL,
      NULL, NULL, 'MRI/CAT/EEG clean', NULL, 120,
      (now() at time zone 'utc'), (now() at time zone 'utc')),
    (gen_random_uuid(), uid, 'p1-tcd-lamotrigine', 'P1 TCD/lamotrigine', 'parked', NULL,
      NULL, NULL, 'no CoS drug start', NULL, 210,
      (now() at time zone 'utc'), (now() at time zone 'utc')),
    (gen_random_uuid(), uid, 'p2-hla-dq', 'P2 optional HLA-DQ2/DQ8', 'parked', NULL,
      NULL, NULL, NULL, NULL, 220,
      (now() at time zone 'utc'), (now() at time zone 'utc'))
  ON CONFLICT (user_id, slug) DO UPDATE SET
    title = EXCLUDED.title,
    status = EXCLUDED.status,
    layer = EXCLUDED.layer,
    kill_test = EXCLUDED.kill_test,
    next_move = EXCLUDED.next_move,
    last_evidence = EXCLUDED.last_evidence,
    cite = EXCLUDED.cite,
    sort_order = EXCLUDED.sort_order,
    updated_at = (now() at time zone 'utc');
END $$;
