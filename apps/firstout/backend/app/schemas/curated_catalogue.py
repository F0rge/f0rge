from __future__ import annotations

import uuid
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.sku import SkuDetails


MAX_CATALOGUE_SKUS = 100
ApprovedText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
ArchiveFilename = Annotated[
    str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}\.jpg$")
]
CuratedCatalogueScope = Literal["catalogue", "sku", "photos"]
CURATED_CATALOGUE_SCOPES = ("catalogue", "sku", "photos")
SUPPLEMENTAL_PHOTO_FIELDS = frozenset({"setting_photo", "detail_photo", "second_detail_photo"})


class ReviewedPhoto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: ArchiveFilename
    sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class ReviewedSku(SkuDetails):
    model_config = ConfigDict(extra="forbid")

    sku_id: uuid.UUID
    our_ref: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    name: Optional[ApprovedText] = None
    fabric: Optional[ApprovedText] = None
    gallery: Optional[tuple[ReviewedPhoto, ReviewedPhoto, ReviewedPhoto]] = None
    retain_current_photo_as_setting: bool = Field(default=False, strict=True)
    setting_photo: Optional[ReviewedPhoto] = None
    detail_photo: Optional[ReviewedPhoto] = None
    second_detail_photo: Optional[ReviewedPhoto] = None

    def supplemental_photos(self) -> dict[str, ReviewedPhoto]:
        return {
            role: photo
            for role, photo in (
                ("setting", self.setting_photo),
                ("detail", self.detail_photo),
                ("second_detail", self.second_detail_photo),
            )
            if photo is not None
        }

    @model_validator(mode="after")
    def preserve_or_replace_gallery(self) -> ReviewedSku:
        if self.model_fields_set & SUPPLEMENTAL_PHOTO_FIELDS:
            if self.model_fields_set != {
                "sku_id",
                "our_ref",
                *(f"{role}_photo" for role in self.supplemental_photos()),
            }:
                raise ValueError(
                    "Supplemental photo rows allow only SKU identifiers and new photos"
                )
            return self
        # Identity-only selections keep the existing SKU data and gallery.
        if self.gallery is None and self.model_fields_set - {"sku_id", "our_ref"}:
            raise ValueError("SKU edits require a reviewed three-photo gallery")
        if self.gallery is not None:
            if self.name is None:
                raise ValueError("Reviewed gallery rows require a SKU name")
            if len({photo.sha256 for photo in self.gallery}) != 3:
                raise ValueError("Gallery slots must contain three distinct photos")
        return self


class ReviewedVariant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_id: uuid.UUID
    options: dict[ApprovedText, ApprovedText] = Field(min_length=1, max_length=4)


class ReviewedGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: ApprovedText
    variants: list[ReviewedVariant] = Field(min_length=2, max_length=MAX_CATALOGUE_SKUS)

    @model_validator(mode="after")
    def same_axes(self) -> ReviewedGroup:
        axes = set(self.variants[0].options)
        if any(set(variant.options) != axes for variant in self.variants):
            raise ValueError("All variants in a group require the same option axes")
        combinations = {tuple(sorted(variant.options.items())) for variant in self.variants}
        if len(combinations) != len(self.variants):
            raise ValueError("Each variant must have a distinct combination of options")
        return self


class CuratedCatalogueManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    skus: list[ReviewedSku] = Field(min_length=1, max_length=MAX_CATALOGUE_SKUS)
    groups: list[ReviewedGroup] = Field(max_length=MAX_CATALOGUE_SKUS // 2)

    @model_validator(mode="after")
    def distinct_members(self) -> CuratedCatalogueManifest:
        sku_ids = {sku.sku_id for sku in self.skus}
        codes = {sku.our_ref for sku in self.skus}
        if len(sku_ids) != len(self.skus) or len(codes) != len(self.skus):
            raise ValueError("The catalogue contains duplicate SKUs")
        names = {group.title.casefold() for group in self.groups}
        if len(names) != len(self.groups):
            raise ValueError("The catalogue contains duplicate group titles")
        grouped = [variant.sku_id for group in self.groups for variant in group.variants]
        edited = {sku.sku_id for sku in self.skus if sku.gallery is not None}
        if len(set(grouped)) != len(grouped) or not set(grouped) <= edited:
            raise ValueError("Every group member must be one reviewed SKU in exactly one group")
        return self


class CuratedCatalogueResult(BaseModel):
    applied: bool
    selected_skus: int
    gallery_images: int
    groups: int
    held_without_price: list[str]
