from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dietary_ingredient import DietaryIngredient
from app.services.dietary_ingredient_catalog import DietaryIngredientCatalogService

CATALOG_CONTEXT_MAX_ENTRIES = 500

_TRUNCATION_NOTE = "list truncated — pick closest catalog match or free-form"


def _format_catalog_line(item: DietaryIngredient) -> str:
    aliases = sorted(alias.alias for alias in item.aliases if alias.alias != item.canonical_name)
    if aliases:
        return f"{item.canonical_name} [aliases: {', '.join(aliases)}]"
    return item.canonical_name


def format_catalog_context(items: list[DietaryIngredient]) -> str:
    """Format dietary ingredients as compact one-line-per-canonical catalog text.

    Lines are sorted alphabetically by canonical_name. When more than
    CATALOG_CONTEXT_MAX_ENTRIES items are supplied, the list is truncated and
    a note is prepended on the first line.
    """
    if not items:
        return ""

    sorted_items = sorted(items, key=lambda item: item.canonical_name)
    truncated = len(sorted_items) > CATALOG_CONTEXT_MAX_ENTRIES
    if truncated:
        sorted_items = sorted_items[:CATALOG_CONTEXT_MAX_ENTRIES]

    lines = [_format_catalog_line(item) for item in sorted_items]
    if truncated:
        return _TRUNCATION_NOTE + "\n" + "\n".join(lines)
    return "\n".join(lines)


async def build_catalog_context(db: AsyncSession) -> str:
    """Load the current user's dietary catalog and format it for vision prompts."""
    service = DietaryIngredientCatalogService(db)
    items = await service.list_items()
    return format_catalog_context(items)
