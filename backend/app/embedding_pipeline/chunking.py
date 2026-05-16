from __future__ import annotations


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ≈ 4 characters."""
    return len(text) // 4


def _sliding_window(text: str, max_tokens: int, overlap_tokens: int) -> list[str]:
    """Split text into overlapping fixed-size windows when a section is too long."""
    max_chars = max_tokens * 4
    overlap_chars = overlap_tokens * 4
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap_chars
    return chunks


def chunk_text(
    text: str, *, max_tokens: int = 800, overlap_tokens: int = 100
) -> list[str]:
    """Markdown-aware H2 split, with token estimate = len(s) // 4.

    First splits on ``\\n## `` boundaries. If any resulting section exceeds
    max_tokens, falls through to a sliding-window split on that section.
    Overlap applies only within the same H2 section.
    """
    if not text:
        return []

    # Split on H2 headings, keeping the heading attached to each section.
    raw_sections: list[str] = []
    parts = text.split("\n## ")
    for i, part in enumerate(parts):
        if i == 0:
            raw_sections.append(part)
        else:
            raw_sections.append("## " + part)

    chunks: list[str] = []
    for section in raw_sections:
        if not section.strip():
            continue
        if _estimate_tokens(section) <= max_tokens:
            chunks.append(section)
        else:
            chunks.extend(_sliding_window(section, max_tokens, overlap_tokens))

    return [c for c in chunks if c.strip()]
