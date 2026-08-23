from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

from mcp.server.auth.provider import AccessToken
from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from f0rge_db.tenant import apply_session_user_id
from app.config import settings
from app.models.dietary_ingredient import DietaryIngredient
from app.models.lab_marker_catalog import LabMarkerCatalog
from app.models.user import LEO_PLACEHOLDER_PASSWORD_HASH, User


def _register_resources(server: FastMCP) -> None:
    from app.mcp import resources as resources_mod

    resources_mod.register_resources(server)


def test_list_resources_returns_at_least_five() -> None:
    server = FastMCP("test")
    _register_resources(server)

    uris = {str(resource.uri) for resource in server._resource_manager.list_resources()}
    assert len(uris) >= 5
    assert "marrow://schema/overview" in uris
    assert "marrow://schema/entries" in uris
    assert "marrow://schema/photos" in uris
    assert "marrow://schema/hypotheses" in uris
    assert "marrow://catalog/lab-markers" in uris
    assert "marrow://catalog/dietary-ingredients" in uris
    assert "marrow://meta/embedding-sources" in uris


async def test_schema_overview_mentions_rls_and_healthtracker_ro() -> None:
    server = FastMCP("test")
    _register_resources(server)

    contents = await server.read_resource("marrow://schema/overview")
    text = contents[0].content
    assert isinstance(text, str)
    assert "RLS" in text
    assert "healthtracker_ro" in text


async def test_schema_entries_is_markdown() -> None:
    server = FastMCP("test")
    _register_resources(server)

    contents = await server.read_resource("marrow://schema/entries")
    text = contents[0].content
    assert isinstance(text, str)
    assert "symptoms_json" in text
    assert "effective_flags" in text


async def test_meta_embedding_sources_lists_tables() -> None:
    server = FastMCP("test")
    _register_resources(server)

    contents = await server.read_resource("marrow://meta/embedding-sources")
    text = contents[0].content
    assert isinstance(text, str)
    assert "entries" in text
    assert "photo_analyses" in text
    assert "chunk_text" in text


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


async def test_dietary_ingredients_tenant_isolation(async_db: AsyncSession) -> None:
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    async_db.add(
        User(id=user_a, email="mcp-res-a@example.com", password_hash=LEO_PLACEHOLDER_PASSWORD_HASH)
    )
    async_db.add(
        User(id=user_b, email="mcp-res-b@example.com", password_hash=LEO_PLACEHOLDER_PASSWORD_HASH)
    )
    await async_db.flush()
    async_db.add(
        DietaryIngredient(
            user_id=user_a,
            canonical_name="user-a-kimchi",
            histamine_score=2,
        )
    )
    async_db.add(
        DietaryIngredient(
            user_id=user_b,
            canonical_name="user-b-tofu",
            histamine_score=0,
        )
    )
    await async_db.flush()

    server = FastMCP("test")
    _register_resources(server)

    resource_fn = next(
        r
        for r in server._resource_manager.list_resources()
        if str(r.uri) == "marrow://catalog/dietary-ingredients"
    ).fn

    token_b = AccessToken(token="tenant-b", client_id=str(user_b), scopes=[])
    with patch("app.mcp.tools.scoped_ro_session") as mock_ro:

        async def _aenter(*_args: object, **_kwargs: object) -> AsyncSession:
            await apply_session_user_id(async_db, user_b)
            return async_db

        mock_ro.return_value.__aenter__ = _aenter
        mock_ro.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.mcp.tools.get_access_token", return_value=token_b):
            result = await resource_fn()

    names = {row["canonical_name"] for row in result["ingredients"]}
    assert "user-b-tofu" in names
    assert "user-a-kimchi" not in names
    assert mock_ro.call_args[0][0] == user_b
