from __future__ import annotations

from pydantic import BaseModel


class TagConfig(BaseModel):
    portrait_landscape: str
    tag_height: float
    tag_width: float
    font_size: int
    max_characters: int
    auto_max_characters: bool
    left_margin: float = 7.5
    top_margin: float = 10.0
    inner_padding: float = 2.0


class CSVUploadResponse(BaseModel):
    session_id: str
    data: list[dict]
    price_columns: list[str]
    product_codes: list[str]


class PDFGenerateRequest(BaseModel):
    session_id: str | None = None
    csv_data: list[dict] | None = None
    selected_products: list[str]
    price_column: str
    config: TagConfig
