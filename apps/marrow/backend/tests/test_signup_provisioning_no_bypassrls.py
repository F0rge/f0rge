"""Regression test for the signup catalog copy under FORCE RLS without BYPASSRLS.

Prod (f0rge-db) runs the copy as ``schema_admin`` — a NOSUPERUSER, NOBYPASSRLS
role — against catalog tables with FORCE ROW LEVEL SECURITY. Migration 030's
``SET row_security = off`` did NOT bypass RLS there (that only works for a
BYPASSRLS/superuser owner), so the copy raised InsufficientPrivilege and aborted
signup. The fix (migration 032) is a ``provisioner`` service-role policy plus the
removal of ``row_security = off``.

The normal suite can't see this bug: conftest connects as the postgres SUPERUSER,
which bypasses RLS. This test faithfully reproduces the prod condition by creating
a NOSUPERUSER role, reassigning the SECURITY DEFINER copy function to it (so the
function executes with RLS-bound privileges, not superuser ones), and running the
copy under ``SET ROLE``.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import settings


async def test_copy_catalog_under_non_superuser_role(async_engine: AsyncEngine) -> None:
    ref_id = uuid.UUID(settings.default_storage_user_id)
    new_id_provisioner = uuid.uuid4()
    new_id_plain = uuid.uuid4()

    async with async_engine.connect() as conn:
        trans = await conn.begin()
        try:
            # --- superuser setup (RLS bypassed) ---
            # Two reference rows for the copy to pick up.
            await conn.execute(
                sa.text(
                    """
                    INSERT INTO dietary_ingredients
                        (user_id, canonical_name, contains_gluten, contains_dairy,
                         archived, created_at, updated_at)
                    VALUES
                        (:u, 'probe_apple', false, false, false, now(), now()),
                        (:u, 'probe_banana', false, false, false, now(), now())
                    """
                ),
                {"u": ref_id},
            )
            # New users must exist: dietary_ingredients.user_id -> users.id (FK).
            for uid in (new_id_provisioner, new_id_plain):
                await conn.execute(
                    sa.text(
                        """
                        INSERT INTO users
                            (id, email, password_hash, avatar_default_index, created_at)
                        VALUES (:id, :email, 'x', 0, now())
                        """
                    ),
                    {"id": uid, "email": f"probe-{uid}@test.local"},
                )

            # NOSUPERUSER role so RLS is actually enforced, and it must OWN the
            # SECURITY DEFINER function — otherwise the function runs as the
            # (superuser) postgres owner and silently bypasses RLS, defeating the
            # whole point of this test.
            await conn.execute(sa.text("CREATE ROLE rls_probe NOSUPERUSER NOBYPASSRLS"))
            await conn.execute(
                sa.text(
                    "GRANT SELECT, INSERT ON dietary_ingredients, ingredient_aliases, "
                    "lab_marker_catalog, lab_marker_aliases TO rls_probe"
                )
            )
            await conn.execute(
                sa.text("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO rls_probe")
            )
            await conn.execute(
                sa.text(
                    "ALTER FUNCTION copy_user_catalog_from_reference(uuid, uuid) OWNER TO rls_probe"
                )
            )

            # --- guard: WITHOUT provisioner role, copy must NOT raise and copies 0 ---
            # (proves the hard `row_security = off` error is gone; tenant isolation
            # simply hides the reference rows.)
            await conn.execute(sa.text("SET ROLE rls_probe"))
            await conn.execute(
                sa.text("SELECT set_config('app.user_id', :u, true)"),
                {"u": str(new_id_plain)},
            )
            await conn.execute(sa.text("SELECT set_config('app.service_role', '', true)"))
            await conn.execute(
                sa.text("SELECT copy_user_catalog_from_reference(:new, :ref)"),
                {"new": new_id_plain, "ref": ref_id},
            )
            await conn.execute(sa.text("RESET ROLE"))
            plain_count = (
                await conn.execute(
                    sa.text("SELECT count(*) FROM dietary_ingredients WHERE user_id = :u"),
                    {"u": new_id_plain},
                )
            ).scalar_one()
            assert plain_count == 0

            # --- positive: WITH provisioner role, cross-tenant copy succeeds ---
            await conn.execute(sa.text("SET ROLE rls_probe"))
            await conn.execute(
                sa.text("SELECT set_config('app.user_id', :u, true)"),
                {"u": str(new_id_provisioner)},
            )
            await conn.execute(
                sa.text("SELECT set_config('app.service_role', 'provisioner', true)")
            )
            await conn.execute(
                sa.text("SELECT copy_user_catalog_from_reference(:new, :ref)"),
                {"new": new_id_provisioner, "ref": ref_id},
            )
            await conn.execute(sa.text("RESET ROLE"))
            copied_count = (
                await conn.execute(
                    sa.text("SELECT count(*) FROM dietary_ingredients WHERE user_id = :u"),
                    {"u": new_id_provisioner},
                )
            ).scalar_one()
            assert copied_count == 2
        finally:
            await trans.rollback()
