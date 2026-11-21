"""The one layout every customer document prints with: tax invoice, quote, credit note, receipt."""

from __future__ import annotations

import uuid
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

DocumentKind = Literal["invoice", "quote", "credit_note", "receipt"]
SectionKey = Literal["parties", "lines", "totals", "notes", "payments", "bank", "terms"]
SECTION_KEYS: tuple[SectionKey, ...] = (
    "parties",
    "lines",
    "totals",
    "notes",
    "payments",
    "bank",
    "terms",
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentSection(_Strict):
    key: SectionKey
    visible: bool = True


class DocumentColumns(_Strict):
    sku_ref: bool = True
    discount: bool = True
    line_vat: bool = True


class DocumentWording(_Strict):
    title: str = Field(min_length=1, max_length=60)
    number_label: str = Field(min_length=1, max_length=40)
    terms: str = Field(default="", max_length=2000)

    @field_validator("title", "number_label")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class DocumentWordingSet(_Strict):
    invoice: DocumentWording = DocumentWording(
        title="Tax invoice",
        number_label="Invoice no.",
        terms="Payment is due by the due date shown.",
    )
    quote: DocumentWording = DocumentWording(
        title="Quote",
        number_label="Quote no.",
        terms="Prices are valid until the date shown and subject to stock availability.",
    )
    credit_note: DocumentWording = DocumentWording(
        title="Credit note",
        number_label="Credit note no.",
        terms="This credit note reduces the amount owing on the original tax invoice.",
    )
    receipt: DocumentWording = DocumentWording(title="Payment receipt", number_label="Receipt no.")


class DocumentTemplate(_Strict):
    logo_position: Literal["left", "centre", "right"] = "right"
    logo_height: int = Field(default=72, ge=40, le=120)
    accent_colour: str = Field(default="#161616", pattern=r"^#[0-9a-fA-F]{6}$")
    font: Literal["sans", "serif", "mono"] = "sans"
    density: Literal["comfortable", "compact"] = "comfortable"
    table_header: Literal["band", "lines", "solid"] = "band"
    sections: list[DocumentSection] = Field(
        default_factory=lambda: [DocumentSection(key=key) for key in SECTION_KEYS]
    )
    columns: DocumentColumns = DocumentColumns()
    wording: DocumentWordingSet = DocumentWordingSet()
    footer: str = Field(default="Thank you for your business.", max_length=500)
    show_trading_name: bool = False
    paid_stamp: bool = True

    @field_validator("accent_colour")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.lower()

    @field_validator("sections")
    @classmethod
    def _each_section_once(cls, value: list[DocumentSection]) -> list[DocumentSection]:
        keys = [section.key for section in value]
        if len(keys) != len(set(keys)):
            raise ValueError("each section may appear only once")
        # A section added in a later release shows, at the end, in templates saved before it.
        return value + [DocumentSection(key=key) for key in SECTION_KEYS if key not in keys]


class DocumentTemplateResponse(BaseModel):
    template: DocumentTemplate
    defaults: DocumentTemplate
    is_default: bool


class DocumentTemplatePreview(_Strict):
    template: DocumentTemplate
    kind: DocumentKind = "invoice"
    sample_id: Optional[uuid.UUID] = None
