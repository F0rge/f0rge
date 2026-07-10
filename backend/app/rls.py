from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncConnection

USER_OWNED_TABLES: tuple[str, ...] = (
    "entries",
    "photos",
    "photo_analyses",
    "photo_ingredients",
    "tracker",
    "tracker_log",
    "treatments",
    "treatment_log",
    "labs",
    "lab_markers",
    "health_metrics",
    "weather_readings",
    "embedding",
    "embedding_queue",
    "user_settings",
    "diet_tag_catalog",
    "supplement_catalog",
    "symptom_catalog",
    "medication_catalog",
    "lab_marker_catalog",
    "lab_marker_aliases",
    "dietary_ingredients",
    "ingredient_aliases",
)


async def enable_row_level_security(conn: AsyncConnection) -> None:
    """Apply tenant RLS policies (mirrors migration 021)."""
    import sqlalchemy as sa

    for table in USER_OWNED_TABLES:
        await conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        await conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
        await conn.execute(
            sa.text(
                f"""
                CREATE POLICY tenant_isolation ON {table}
                    FOR ALL
                    USING (user_id = current_setting('app.user_id', true)::uuid)
                    WITH CHECK (user_id = current_setting('app.user_id', true)::uuid)
                """
            )
        )
    await conn.execute(
        sa.text(
            """
            CREATE POLICY mcp_auth_lookup ON user_settings
                FOR SELECT
                USING (current_setting('app.service_role', true) = 'mcp_auth')
            """
        )
    )
    await conn.execute(
        sa.text(
            """
            CREATE POLICY worker_queue ON embedding_queue
                FOR ALL
                USING (current_setting('app.service_role', true) = 'worker')
                WITH CHECK (current_setting('app.service_role', true) = 'worker')
            """
        )
    )
