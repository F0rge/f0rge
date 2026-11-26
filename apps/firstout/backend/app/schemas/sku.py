from __future__ import annotations

import datetime
import uuid
from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)


from app.schemas.customer_crm import PriceClassification
from app.schemas.quantity import Quantity


SKU_DIMENSION_FIELDS = ("width_cm", "depth_cm", "height_cm", "diameter_cm")
SKU_DETAIL_FIELDS = (*SKU_DIMENSION_FIELDS, "notes", "piece_count")
SKU_SETTING_PHOTO_SLOT = 4
SKU_DETAIL_PHOTO_SLOT = 5
SKU_SECOND_DETAIL_PHOTO_SLOT = 6
SkuDimension = Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2, allow_inf_nan=False)]


def _swatch_hex_input(value: object) -> object:
    # Blank clears the colour; any case is accepted and stored lowercase (ck_skus_swatch_hex).
    if isinstance(value, str):
        return value.strip().lower() or None
    return value


# Finish colour as #rrggbb, synced to the shop as variant metadata ``swatch_hex``.
SkuSwatchHex = Annotated[
    Optional[Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]],
    BeforeValidator(_swatch_hex_input),
]


def _blank_text_input(value: object) -> object:
    if isinstance(value, str):
        return value.strip() or None
    return value


# What customers read beside the swatch ("Oat"). Blank clears it.
SkuColourName = Annotated[
    Optional[Annotated[str, StringConstraints(max_length=64)]],
    BeforeValidator(_blank_text_input),
]
# A SKU's other materials, in display order. Duplicates are refused by the service.
SkuOtherMaterialIds = Annotated[list[uuid.UUID], Field(max_length=20)]
SellQuantity = Annotated[int, Field(ge=1, le=100_000, strict=True)]


class SkuDetails(BaseModel):
    width_cm: Optional[SkuDimension] = None
    depth_cm: Optional[SkuDimension] = None
    height_cm: Optional[SkuDimension] = None
    diameter_cm: Optional[SkuDimension] = None
    notes: Optional[str] = Field(default=None, max_length=4000)
    piece_count: Optional[int] = Field(default=None, ge=1, le=2_147_483_647, strict=True)


class SkuCreate(SkuDetails):
    is_sellable: bool = True
    till_no_stock_required: bool = False
    exclude_from_commission: bool = False
    our_ref: str = Field(min_length=1, max_length=64)
    # Blank means the service assigns ``csv:<our_ref>``. The column itself stays required.
    our_barcode: Optional[str] = Field(default=None, max_length=64)
    name: str = Field(min_length=1)
    design: str = Field(min_length=1)
    # Deprecated: the label is derived from colour name and main material. Used only
    # while the SKU has neither; a create with none of the three stores "-".
    fabric: Optional[str] = Field(default=None, min_length=1, max_length=255)
    supplier_ref: Optional[str] = Field(default=None, max_length=64)
    # Deprecated: a name resolved to an existing top-level category. Send category_id.
    category: Optional[str] = Field(default=None, max_length=64)
    category_id: Optional[uuid.UUID] = None
    subcategory_id: Optional[uuid.UUID] = None
    colour_name: SkuColourName = None
    main_material_id: Optional[uuid.UUID] = None
    other_material_ids: SkuOtherMaterialIds = Field(default_factory=list)
    sell_multiple: SellQuantity = 1
    # Omitted: the smallest valid minimum, which is the sell multiple.
    min_sell_qty: Optional[SellQuantity] = None
    reorder_min: Optional[int] = Field(default=None, ge=1)
    order_up_to: Optional[int] = Field(default=None, ge=1)
    do_not_reorder: bool = False
    opening_location_id: Optional[uuid.UUID] = None
    opening_qty: Optional[Quantity] = Field(default=None, gt=0)
    opening_unit_cost_zar: Optional[Decimal] = Field(default=None, gt=0)
    opening_date: Optional[datetime.date] = None
    carton_count: int = Field(default=1, ge=1)
    swatch_hex: SkuSwatchHex = None

    @field_validator("our_barcode", mode="before")
    @classmethod
    def blank_barcode_means_generate(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @model_validator(mode="after")
    def opening_fields_together(self) -> SkuCreate:
        any_opening = any(
            [
                self.opening_location_id is not None,
                self.opening_qty is not None,
                self.opening_unit_cost_zar is not None,
                self.opening_date is not None,
            ]
        )
        if not any_opening:
            return self
        if (
            self.opening_location_id is None
            or self.opening_qty is None
            or self.opening_unit_cost_zar is None
        ):
            raise ValueError(
                "opening_location_id, opening_qty, and opening_unit_cost_zar "
                "are required when any opening field is set"
            )
        return self


class SkuUpdate(SkuDetails):
    model_config = ConfigDict(extra="forbid")

    is_sellable: Optional[bool] = None
    till_no_stock_required: Optional[bool] = None
    exclude_from_commission: Optional[bool] = None
    storefront_hidden: Optional[bool] = None
    our_ref: Optional[str] = Field(default=None, min_length=1, max_length=64)
    our_barcode: Optional[str] = Field(default=None, min_length=1, max_length=64)
    name: Optional[str] = Field(default=None, min_length=1)
    design: Optional[str] = Field(default=None, min_length=1)
    # Deprecated, see SkuCreate.fabric.
    fabric: Optional[str] = Field(default=None, min_length=1, max_length=255)
    # Deprecated, see SkuCreate.category. Null clears the category.
    category: Optional[str] = Field(default=None, max_length=64)
    category_id: Optional[uuid.UUID] = None
    subcategory_id: Optional[uuid.UUID] = None
    colour_name: SkuColourName = None
    main_material_id: Optional[uuid.UUID] = None
    other_material_ids: Optional[SkuOtherMaterialIds] = None
    sell_multiple: Optional[SellQuantity] = None
    min_sell_qty: Optional[SellQuantity] = None
    order_up_to: Optional[int] = Field(default=None, ge=1)
    do_not_reorder: Optional[bool] = None
    preferred_supplier_id: Optional[uuid.UUID] = None
    lead_time_days: Optional[int] = Field(default=None, ge=0)
    made_to_order_capacity: Optional[int] = Field(default=None, ge=0)
    made_to_order_lead_time_min_days: Optional[int] = Field(default=None, ge=1)
    made_to_order_lead_time_max_days: Optional[int] = Field(default=None, ge=1)
    made_to_order_expires_at: Optional[datetime.datetime] = None
    reorder_min: Optional[int] = Field(default=None, ge=1)
    supplier_ref: Optional[str] = Field(default=None, max_length=64)
    stockist_ex_vat: Optional[Decimal] = None
    stockist_inc_vat: Optional[Decimal] = None
    wholesale_ex_vat: Optional[Decimal] = None
    wholesale_inc_vat: Optional[Decimal] = None
    decorator_ex_vat: Optional[Decimal] = None
    decorator_inc_vat: Optional[Decimal] = None
    retail_ex_vat: Optional[Decimal] = None
    retail_inc_vat: Optional[Decimal] = None
    carton_count: Optional[int] = Field(default=None, ge=1)
    swatch_hex: SkuSwatchHex = None


SkuTradePriceInput = Annotated[
    Decimal, Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
]
SkuRetailPriceInput = Annotated[
    Decimal, Field(ge=0, max_digits=13, decimal_places=2, allow_inf_nan=False)
]


class SkuPricePreviewChanges(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stockist_ex_vat: Optional[SkuTradePriceInput] = None
    wholesale_ex_vat: Optional[SkuTradePriceInput] = None
    decorator_ex_vat: Optional[SkuTradePriceInput] = None
    retail_inc_vat: Optional[SkuRetailPriceInput] = None


class SkuPricePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: PriceClassification
    quantity: int = Field(ge=1, le=999, strict=True)
    price_changes: SkuPricePreviewChanges = Field(default_factory=SkuPricePreviewChanges)


class SkuPricePreviewResponse(BaseModel):
    vat_rate: Decimal
    unit_ex_vat: Decimal
    subtotal_ex_vat: Decimal
    vat_amount: Decimal
    total_inc_vat: Decimal
    source: Literal["stockist", "wholesale", "decorator", "retail", "retail_fallback"]


class SkuMaterialSummary(BaseModel):
    id: uuid.UUID
    name: str
    family: str
    is_archived: bool = False


class SkuResponse(SkuDetails):
    is_archived: bool = False
    archived_at: Optional[datetime.datetime] = None
    archived_by_id: Optional[uuid.UUID] = None
    is_sellable: bool
    till_no_stock_required: bool = False
    exclude_from_commission: bool = False
    storefront_hidden: bool = False
    id: uuid.UUID
    our_ref: str
    our_barcode: str
    name: str
    design: str
    fabric: str
    supplier_ref: Optional[str]
    preferred_supplier_id: Optional[uuid.UUID] = None
    preferred_supplier_name: Optional[str] = None
    lead_time_days: Optional[int] = None
    made_to_order_capacity: Optional[int] = None
    made_to_order_lead_time_min_days: Optional[int] = None
    made_to_order_lead_time_max_days: Optional[int] = None
    made_to_order_expires_at: Optional[datetime.datetime] = None
    made_to_order_offer_id: Optional[uuid.UUID] = None
    reorder_min: Optional[int] = None
    last_landed_cost_zar: Optional[Decimal] = None
    # The top-level category's name, kept in sync with category_id.
    category: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    subcategory_id: Optional[uuid.UUID] = None
    subcategory: Optional[str] = None
    colour_name: Optional[str] = None
    main_material_id: Optional[uuid.UUID] = None
    main_material: Optional[SkuMaterialSummary] = None
    other_material_ids: list[uuid.UUID] = Field(default_factory=list)
    other_materials: list[SkuMaterialSummary] = Field(default_factory=list)
    sell_multiple: int = 1
    min_sell_qty: int = 1
    order_up_to: Optional[int] = None
    do_not_reorder: bool = False
    swatch_hex: Optional[str] = None
    photo_storage_key: Optional[str]
    gallery_photo_count: int = 0
    stockist_ex_vat: Optional[Decimal] = None
    stockist_inc_vat: Optional[Decimal] = None
    wholesale_ex_vat: Optional[Decimal] = None
    wholesale_inc_vat: Optional[Decimal] = None
    decorator_ex_vat: Optional[Decimal] = None
    decorator_inc_vat: Optional[Decimal] = None
    retail_ex_vat: Optional[Decimal] = None
    retail_inc_vat: Optional[Decimal] = None
    # On-hand weighted average. Null without stock.cost.view, or when nothing is on hand.
    average_unit_cost_zar: Optional[Decimal] = None
    # True when that tier's ex-VAT price is strictly under the average cost.
    # The rand amount stays off the payload for roles that cannot see costs.
    stockist_below_cost: bool = False
    wholesale_below_cost: bool = False
    decorator_below_cost: bool = False
    retail_below_cost: bool = False
    carton_count: int
    is_kit: bool = False
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer(*SKU_DIMENSION_FIELDS, when_used="json")
    def serialize_dimension(self, value: Optional[Decimal]) -> Optional[float]:
        return float(value) if value is not None else None


class SkuUnitCostItem(BaseModel):
    sku_id: uuid.UUID
    unit_cost_zar: Optional[Decimal] = None


class SkuUnitCostPage(BaseModel):
    items: list[SkuUnitCostItem]
    total: int = Field(ge=0)


class SkuListPage(BaseModel):
    items: list[SkuResponse]
    total: int = Field(ge=0)
    categories: list[str]
