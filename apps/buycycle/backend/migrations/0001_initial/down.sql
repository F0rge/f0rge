-- Deliberately irreversible: drop/recreate is not a data-preserving rollback.
-- Recover a verified backup into a separate database and reconcile later writes.
DO $$ BEGIN RAISE EXCEPTION 'Buycycle migration requires the documented forward recovery procedure'; END $$;
