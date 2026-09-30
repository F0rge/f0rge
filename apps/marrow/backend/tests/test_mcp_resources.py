from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.lab_marker_catalog import LabMarkerCatalog


def _register_resources(server: FastMCP) -> None:
    from app.mcp import resources as resources_mod

    resources_mod.register_resources(server)


def test_list_resources_returns_public_reference_set() -> None:
    server = FastMCP("test")
    _register_resources(server)

    uris = {str(resource.uri) for resource in server._resource_manager.list_resources()}
    assert uris == {
        "marrow://catalog/dietary-ingredients",
        "marrow://catalog/lab-markers",
        "marrow://reference/check-in-day-map",
        "marrow://reference/meal-logging-guide",
    }


async def test_check_in_day_map_mentions_scores() -> None:
    server = FastMCP("test")
    _register_resources(server)

    contents = await server.read_resource("marrow://reference/check-in-day-map")
    text = contents[0].content
    assert isinstance(text, str)
    assert "symptoms_json" in text
    assert "save_day" in text


async def test_catalog_lab_markers_returns_reference_catalog(async_db: AsyncSession) -> None:
    cat = LabMarkerCatalog(
        canonical_name="ferritin",
        display_name="Ferritin",
        common_units=["ng/mL", "µg/L"],
    )
    async_db.add(cat)
    await async_db.flush()

    server = FastMCP("test")
    _register_resources(server)

    ref_user_id = uuid.UUID(settings.default_storage_user_id)
    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:
        mock_ro.return_value.__aenter__ = AsyncMock(return_value=async_db)
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        resource_fn = next(
            r
            for r in server._resource_manager.list_resources()
            if str(r.uri) == "marrow://catalog/lab-markers"
        ).fn
        result = await resource_fn()

    assert result["count"] >= 1
    names = {m["canonical_name"] for m in result["markers"]}
    assert "ferritin" in names
    assert mock_ro.call_args[0][0] == ref_user_id
