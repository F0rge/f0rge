from __future__ import annotations

import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from app.config import settings
from app.mcp.observability import instrument_resource
from app.models.lab_marker_catalog import LabMarkerCatalog
from f0rge_db.tenant import owned_by_user


def register_catalog_resources(server: FastMCP) -> None:
    @server.resource(
        "marrow://catalog/lab-markers",
        name="catalog_lab_markers",
        description=(
            "Global reference lab marker catalog: canonical names, display names, and common units. "
            "Load before calling get_lab_history or interpreting lab_markers.canonical_name."
        ),
        mime_type="application/json",
    )
    @instrument_resource("catalog_lab_markers")
    async def catalog_lab_markers() -> dict[str, Any]:
        ref_user_id = uuid.UUID(settings.default_storage_user_id)
        import app.mcp.tools as mcp_tools

        async with mcp_tools.scoped_ro_session(ref_user_id) as db:
            rows = (
                (
                    await db.execute(
                        select(LabMarkerCatalog)
                        .where(owned_by_user(LabMarkerCatalog.user_id))
                        .order_by(LabMarkerCatalog.canonical_name)
                    )
                )
                .scalars()
                .all()
            )

        markers = [
            {
                "canonical_name": row.canonical_name,
                "display_name": row.display_name,
                "common_units": row.common_units,
            }
            for row in rows
        ]
        return {"markers": markers, "count": len(markers)}
