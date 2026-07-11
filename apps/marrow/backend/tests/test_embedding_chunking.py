from __future__ import annotations

from app.embedding_pipeline.chunking import chunk_text


def test_empty_string_returns_empty() -> None:
    assert chunk_text("") == []


def test_single_short_chunk_returned_as_is() -> None:
    text = "Hello world, this is a short note."
    result = chunk_text(text)
    assert len(result) == 1
    assert result[0] == text


def test_h2_split_on_heading_boundary() -> None:
    text = "Intro paragraph.\n## Section One\nContent of one.\n## Section Two\nContent of two."
    result = chunk_text(text)
    assert len(result) == 3
    assert result[0] == "Intro paragraph."
    assert result[1].startswith("## Section One")
    assert result[2].startswith("## Section Two")


def test_h2_heading_stays_attached_to_section() -> None:
    text = "Before.\n## Alpha\nAlpha content."
    result = chunk_text(text)
    # The heading must be in the same chunk as its content.
    heading_chunk = next(c for c in result if "## Alpha" in c)
    assert "Alpha content." in heading_chunk


def test_oversized_section_splits_with_sliding_window() -> None:
    # 4 chars per token; max_tokens=10 → max_chars=40
    long_text = "A" * 200
    result = chunk_text(long_text, max_tokens=10, overlap_tokens=2)
    # Must have more than one chunk.
    assert len(result) > 1
    # Reconstruct full coverage (no chars dropped — just overlapping windows).
    for chunk in result:
        assert len(chunk) <= 40 + 1  # max_chars bound, small tolerance for boundary


def test_overlap_carried_into_next_window() -> None:
    # 4 chars/token; max=10 tokens (40 chars), overlap=2 tokens (8 chars).
    long_text = "X" * 100
    result = chunk_text(long_text, max_tokens=10, overlap_tokens=2)
    assert len(result) >= 2
    # Each window except the last starts where the previous ended minus overlap.
    # The second chunk should start at 40 - 8 = 32 and end at 72.
    assert len(result[1]) == 40


def test_blank_only_sections_filtered_out() -> None:
    text = "Content.\n## \n   \n## Real Section\nStuff."
    result = chunk_text(text)
    # The blank section should be filtered out.
    for chunk in result:
        assert chunk.strip() != ""


def test_single_newline_h2_prefix_not_confused_with_h3() -> None:
    text = "Intro.\n### Not an H2\nStill intro.\n## Real H2\nNew section."
    result = chunk_text(text)
    # ### heading should stay with the intro, not cause an extra split.
    assert len(result) == 2


def test_no_h2_single_chunk_under_limit() -> None:
    text = "Just a note with no headings at all."
    result = chunk_text(text)
    assert result == [text]


def test_max_tokens_respected() -> None:
    # 800 tokens * 4 chars = 3200 chars max per chunk.
    big = "W" * 5000
    result = chunk_text(big)  # default max_tokens=800
    for chunk in result:
        assert len(chunk) <= 3200
