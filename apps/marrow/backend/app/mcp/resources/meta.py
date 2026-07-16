from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from app.embedding_pipeline.chunking import chunk_text
from app.embedding_pipeline.serialization import SERIALIZERS
from app.mcp.observability import instrument_resource

_EMBEDDING_SOURCES: list[dict[str, Any]] = [
    {
        "source_table": "entries",
        "description": "Daily check-in rows — symptoms, scores, diet flags, notes",
        "serializer": "serialize_entry",
        "text_format": "Plain-text lines: date header, notes, scalar scores, effective diet flags, symptoms_json key:value pairs",
    },
    {
        "source_table": "labs",
        "description": "Lab report documents — uses raw_text when present",
        "serializer": "serialize_lab",
        "text_format": "Header with name/type/date, then raw_text body and optional notes",
    },
    {
        "source_table": "treatments",
        "description": "Supplements, medications, and protocols",
        "serializer": "serialize_treatment",
        "text_format": "Name, type, group, start/end dates, dose, notes",
    },
    {
        "source_table": "photo_analyses",
        "description": "Confirmed meal vision analyses with ingredient names",
        "serializer": "serialize_photo_analysis",
        "text_format": "Dish name, cuisine, raw analysis text, visible ingredient list",
    },
]

_CHUNKING_DOC = {
    "strategy": "markdown_aware_h2_split",
    "max_tokens": 800,
    "overlap_tokens": 100,
    "token_estimate": "len(text) // 4",
    "overflow": "sliding window within the same H2 section when a section exceeds max_tokens",
    "function": "chunk_text",
}


def register_meta_resources(server: FastMCP) -> None:
    @server.resource(
        "marrow://meta/embedding-sources",
        name="meta_embedding_sources",
        description=(
            "Tables embedded for semantic search, serializer dispatch table, and chunk format. "
            "Load before interpreting search_health_data results or embedding_queue rows."
        ),
        mime_type="application/json",
    )
    @instrument_resource("meta_embedding_sources")
    async def meta_embedding_sources() -> dict[str, Any]:
        return {
            "sources": _EMBEDDING_SOURCES,
            "serializer_tables": sorted(SERIALIZERS.keys()),
            "chunking": _CHUNKING_DOC,
            "chunk_text_defaults": {
                "max_tokens": 800,
                "overlap_tokens": 100,
            },
            "chunk_text_callable": f"{chunk_text.__module__}.{chunk_text.__name__}",
        }
