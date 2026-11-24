from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from pathlib import PurePosixPath
from typing import BinaryIO

from PIL import Image
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.ops_commerce import SHOP_CATEGORIES
from app.exceptions import ForbiddenError
from app.models.product_group import ProductGroup, ProductGroupVariant
from app.models.sku import Sku
from app.models.team import Team
from app.permissions import SLUG_OWNER
from app.schemas.curated_catalogue import (
    CuratedCatalogueManifest,
    CuratedCatalogueResult,
    CuratedCatalogueScope,
    ReviewedGroup,
    ReviewedSku,
)
from app.schemas.sku import SKU_DETAIL_FIELDS
from app.services.curated_catalogue_archive import (
    ReviewedCatalogue,
    read_catalogue_archive,
    validate_jpeg,
)
from app.services.object_storage import read_bytes, save_bytes, tenant_storage_ref
from app.services.permissions import PermissionService
from app.services.sku_archive import SkuArchiveService
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work
from f0rge_db.organisation import tenant_id_ctx


class CuratedCatalogueService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def import_archive(
        self,
        file: BinaryIO,
        *,
        user_id: uuid.UUID,
        dry_run: bool,
        scope: CuratedCatalogueScope = "catalogue",
    ) -> CuratedCatalogueResult:
        team_id = tenant_id_ctx.get()
        if team_id is None:
            raise ForbiddenError("An active organisation is required")
        await self._require_owner(user_id)
        reviewed = await asyncio.to_thread(read_catalogue_archive, file)
        manifest = reviewed.manifest
        if scope == "photos":
            return await self._update_supplemental_photos(
                team_id, user_id, reviewed, dry_run=dry_run
            )
        if any(row.supplemental_photos() for row in manifest.skus):
            raise ValidationError("Use the supplemental photos scope to upload these photos")
        if scope == "sku":
            return await self._update_selected_sku(team_id, user_id, reviewed, dry_run=dry_run)
        if any(row.retain_current_photo_as_setting for row in manifest.skus):
            raise ValidationError("Use the single SKU scope to retain the current setting photo")
        if dry_run:
            skus = await self._catalogue_skus(team_id, manifest)
            return self._receipt(reviewed, skus, applied=False)

        # Reject mismatched identifiers before writing any objects. Immutable, tenant-scoped
        # objects staged during a failed or interrupted apply are safe to reuse on the next try.
        await self._catalogue_skus(team_id, manifest)
        gallery_keys = await self._stage_galleries(reviewed)
        try:
            async with unit_of_work(self.db):
                await SkuArchiveService(self.db).lock_skus([row.sku_id for row in manifest.skus])
                await self._require_owner(user_id)
                skus = await self._catalogue_skus(team_id, manifest)
                receipt = self._receipt(reviewed, skus, applied=True)
                team = await self.db.get(Team, team_id, populate_existing=True)
                if team is None:
                    raise NotFoundError("Organisation not found")
                for sku in skus.values():
                    sku.storefront_catalogue_selected = False
                for row in manifest.skus:
                    sku = skus[row.sku_id]
                    sku.storefront_catalogue_selected = True
                    sku.storefront_hidden = False
                    if row.gallery is not None:
                        self._write_reviewed_details(sku, row, gallery_keys[row.sku_id])
                await self._reconcile_groups(team_id, manifest)
                team.storefront_curated_catalogue = True
        except IntegrityError as exc:
            raise ConflictError(
                "The reviewed catalogue conflicts with existing SKU or variant data"
            ) from exc
        return receipt

    async def _update_supplemental_photos(
        self,
        team_id: uuid.UUID,
        user_id: uuid.UUID,
        reviewed: ReviewedCatalogue,
        *,
        dry_run: bool,
    ) -> CuratedCatalogueResult:
        manifest = reviewed.manifest
        if manifest.groups or any(not row.supplemental_photos() for row in manifest.skus):
            raise ValidationError(
                "Supplemental photos require one or two photos per SKU and no variant groups"
            )
        skus = await self._catalogue_skus(team_id, manifest, scope="photos")
        legacy_primaries = await self._read_legacy_primary_digests(skus)
        self._validate_supplemental_photos(manifest, skus, legacy_primaries)
        if dry_run:
            return self._receipt(reviewed, skus, applied=False)

        # Finish storage I/O before locking SKU records. After taking the locks,
        # revalidate the legacy photo references and current gallery digests.
        keys = await self._stage_supplemental_photos(reviewed)
        async with unit_of_work(self.db):
            await SkuArchiveService(self.db).lock_skus([row.sku_id for row in manifest.skus])
            await self._require_owner(user_id)
            skus = await self._catalogue_skus(team_id, manifest, scope="photos")
            self._validate_supplemental_photos(manifest, skus, legacy_primaries)
            for row in manifest.skus:
                sku = skus[row.sku_id]
                if setting_key := keys[row.sku_id].get("setting"):
                    sku.setting_photo_storage_key = setting_key
                if detail_key := keys[row.sku_id].get("detail"):
                    sku.detail_photo_storage_key = detail_key
            return self._receipt(reviewed, skus, applied=True)

    @staticmethod
    async def _read_legacy_primary_digests(
        skus: dict[uuid.UUID, Sku],
    ) -> dict[uuid.UUID, tuple[str, str]]:
        digests = {}
        for sku in skus.values():
            key = sku.photo_storage_key
            if sku.gallery_photo_keys or not key:
                continue
            try:
                primary = await asyncio.to_thread(read_bytes, key)
            except FileNotFoundError as exc:
                raise ValidationError(f"SKU primary photo is unavailable: {sku.our_ref}") from exc
            digests[sku.id] = key, hashlib.sha256(primary).hexdigest()
        return digests

    @staticmethod
    def _validate_supplemental_photos(
        manifest: CuratedCatalogueManifest,
        skus: dict[uuid.UUID, Sku],
        legacy_primaries: dict[uuid.UUID, tuple[str, str]],
    ) -> None:
        for row in manifest.skus:
            sku = skus[row.sku_id]
            retained = {PurePosixPath(key).stem for key in sku.gallery_photo_keys or ()}
            primary_key = None if sku.gallery_photo_keys else sku.photo_storage_key or None
            captured_key, digest = legacy_primaries.get(row.sku_id, (None, None))
            if primary_key != captured_key:
                raise ConflictError(f"SKU primary photo changed during import: {row.our_ref}")
            if digest is not None:
                retained.add(digest)
            if row.setting_photo is None and sku.setting_photo_storage_key:
                retained.add(PurePosixPath(sku.setting_photo_storage_key).stem)
            if row.detail_photo is None and sku.detail_photo_storage_key:
                retained.add(PurePosixPath(sku.detail_photo_storage_key).stem)
            incoming = [photo.sha256 for photo in row.supplemental_photos().values()]
            if len(incoming) != len(set(incoming)) or retained.intersection(incoming):
                raise ValidationError(f"Gallery photos must be distinct: {row.our_ref}")

    async def _update_selected_sku(
        self,
        team_id: uuid.UUID,
        user_id: uuid.UUID,
        reviewed: ReviewedCatalogue,
        *,
        dry_run: bool,
    ) -> CuratedCatalogueResult:
        manifest = reviewed.manifest
        row = manifest.skus[0]
        if len(manifest.skus) != 1 or manifest.groups or row.gallery is None:
            raise ValidationError("A single SKU update needs one three-photo gallery and no groups")

        sku = await self._selected_sku(team_id, manifest)
        setting_key = _setting_source(sku, row)
        if setting_key:
            await asyncio.to_thread(
                _read_setting_photo,
                setting_key,
                row,
                preserved=setting_key == sku.setting_photo_storage_key,
                detail_key=sku.detail_photo_storage_key,
            )
        if dry_run:
            return self._receipt(
                reviewed,
                {sku.id: sku},
                applied=False,
                retained_photos=int(bool(setting_key or sku.setting_photo_storage_key))
                + int(bool(sku.detail_photo_storage_key)),
            )

        # Staged studio photos are immutable. The setting source is resolved again under
        # the SKU lock so a concurrent legacy upload cannot change what is retained.
        gallery_keys = await self._stage_galleries(reviewed)
        async with unit_of_work(self.db):
            await SkuArchiveService(self.db).lock_skus([row.sku_id])
            await self._require_owner(user_id)
            sku = await self._selected_sku(team_id, manifest)
            setting_key = _setting_source(sku, row)
            if setting_key:
                sku.setting_photo_storage_key = await asyncio.to_thread(
                    _preserve_setting_photo,
                    row,
                    setting_key,
                    preserved=setting_key == sku.setting_photo_storage_key,
                    detail_key=sku.detail_photo_storage_key,
                )
            self._write_reviewed_details(sku, row, gallery_keys[row.sku_id])
            return self._receipt(
                reviewed,
                {sku.id: sku},
                applied=True,
                retained_photos=int(bool(sku.setting_photo_storage_key))
                + int(bool(sku.detail_photo_storage_key)),
            )

    async def _selected_sku(self, team_id: uuid.UUID, manifest: CuratedCatalogueManifest) -> Sku:
        skus = await self._catalogue_skus(team_id, manifest, scope="sku")
        sku = skus[manifest.skus[0].sku_id]
        if not sku.storefront_catalogue_selected or sku.storefront_hidden:
            raise ValidationError("A single SKU update requires an existing curated storefront SKU")
        return sku

    async def _require_owner(self, user_id: uuid.UUID) -> None:
        role = await PermissionService(self.db).require_staff_manager_role(user_id)
        if role != SLUG_OWNER:
            raise ForbiddenError("Only an organisation owner can apply a curated catalogue")

    async def _catalogue_skus(
        self,
        team_id: uuid.UUID,
        manifest: CuratedCatalogueManifest,
        *,
        scope: CuratedCatalogueScope = "catalogue",
    ) -> dict[uuid.UUID, Sku]:
        selected_ids = [row.sku_id for row in manifest.skus]
        selection = Sku.id.in_(selected_ids)
        if scope == "catalogue":
            selection = or_(selection, Sku.storefront_catalogue_selected.is_(True))
        skus = {
            sku.id: sku
            for sku in (
                await self.db.scalars(
                    select(Sku)
                    .where(
                        Sku.team_id == team_id,
                        selection,
                    )
                    .execution_options(populate_existing=True)
                )
            ).all()
        }
        for row in manifest.skus:
            sku = skus.get(row.sku_id)
            if sku is None or sku.our_ref != row.our_ref:
                raise ValidationError(f"SKU identifier or code does not match: {row.our_ref}")
            if sku.is_archived or not sku.is_sellable:
                raise ValidationError(f"SKU must be active and sellable: {row.our_ref}")
            if scope != "photos" and _category(sku) not in SHOP_CATEGORIES:
                raise ValidationError(f"SKU has no storefront category: {row.our_ref}")
            if sku.setting_photo_storage_key:
                _validate_setting_distinct(row, PurePosixPath(sku.setting_photo_storage_key).stem)
            if sku.detail_photo_storage_key and any(
                photo.sha256 == PurePosixPath(sku.detail_photo_storage_key).stem
                for photo in row.gallery or ()
            ):
                raise ValidationError("The detail photo must be distinct from the studio photos")
        for group in manifest.groups:
            if len({SHOP_CATEGORIES[_category(skus[row.sku_id])] for row in group.variants}) != 1:
                raise ValidationError(
                    "Variants in a product group must have the same shop category"
                )
        return skus

    @staticmethod
    def _receipt(
        reviewed: ReviewedCatalogue,
        skus: dict[uuid.UUID, Sku],
        *,
        applied: bool,
        retained_photos: int = 0,
    ) -> CuratedCatalogueResult:
        return CuratedCatalogueResult(
            applied=applied,
            selected_skus=len(reviewed.manifest.skus),
            gallery_images=len(reviewed.images) + retained_photos,
            groups=len(reviewed.manifest.groups),
            held_without_price=sorted(
                row.our_ref
                for row in reviewed.manifest.skus
                if not skus[row.sku_id].retail_ex_vat or skus[row.sku_id].retail_ex_vat <= 0
            ),
        )

    @staticmethod
    async def _stage_galleries(reviewed: ReviewedCatalogue) -> dict[uuid.UUID, list[str]]:
        semaphore = asyncio.Semaphore(8)

        async def stage_row(row: ReviewedSku) -> tuple[uuid.UUID, list[str]]:
            async with semaphore:
                keys = []
                for photo in row.gallery or ():
                    relative_path = f"skus/{row.sku_id}/curated/{photo.sha256}.jpg"
                    keys.append(
                        await asyncio.to_thread(
                            _store_reviewed_photo,
                            relative_path,
                            reviewed.images[photo.filename],
                            photo.sha256,
                        )
                    )
                return row.sku_id, keys

        rows = [row for row in reviewed.manifest.skus if row.gallery is not None]
        return dict(await asyncio.gather(*(stage_row(row) for row in rows)))

    @staticmethod
    async def _stage_supplemental_photos(
        reviewed: ReviewedCatalogue,
    ) -> dict[uuid.UUID, dict[str, str]]:
        semaphore = asyncio.Semaphore(8)

        async def stage_row(row: ReviewedSku) -> tuple[uuid.UUID, dict[str, str]]:
            async with semaphore:
                return row.sku_id, {
                    role: await asyncio.to_thread(
                        _store_reviewed_photo,
                        f"skus/{row.sku_id}/{role}/{photo.sha256}.jpg",
                        reviewed.images[photo.filename],
                        photo.sha256,
                    )
                    for role, photo in row.supplemental_photos().items()
                }

        return dict(await asyncio.gather(*(stage_row(row) for row in reviewed.manifest.skus)))

    @staticmethod
    def _write_reviewed_details(sku: Sku, row: ReviewedSku, gallery: list[str]) -> None:
        assert row.name is not None
        sku.name = row.name
        if row.fabric is not None:
            sku.fabric = row.fabric
        for field in row.model_fields_set.intersection(SKU_DETAIL_FIELDS):
            setattr(sku, field, getattr(row, field))
        sku.gallery_photo_keys = gallery

    async def _reconcile_groups(
        self, team_id: uuid.UUID, manifest: CuratedCatalogueManifest
    ) -> None:
        edited_ids = [row.sku_id for row in manifest.skus if row.gallery is not None]
        group_ids = {
            row.title: uuid.uuid5(team_id, "curated-catalogue:" + row.title.casefold())
            for row in manifest.groups
        }
        existing = {
            link.source_sku_id: link
            for link in (
                await self.db.scalars(
                    select(ProductGroupVariant).where(
                        ProductGroupVariant.team_id == team_id,
                        or_(
                            ProductGroupVariant.source_sku_id.in_(edited_ids),
                            ProductGroupVariant.product_group_id.in_(group_ids.values()),
                        ),
                    )
                )
            ).all()
        }
        desired = {}
        for row in manifest.groups:
            group_id = group_ids[row.title]
            group = await self.db.get(ProductGroup, group_id)
            if group is None:
                group = ProductGroup(id=group_id, team_id=team_id, title=row.title, options={})
                self.db.add(group)
            elif group.team_id != team_id:
                raise ConflictError("A product group belongs to another organisation")
            group.title = row.title
            group.options = _group_options(row)
            group.storefront_published = True
            for variant in row.variants:
                signature = json.dumps(
                    variant.options, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                )
                if len(signature) > 2048:
                    raise ValidationError("Product group option values are too long")
                desired[variant.sku_id] = (group.id, variant.options, signature)
        for sku_id, link in existing.items():
            match = desired.get(sku_id)
            if match == (link.product_group_id, link.options, link.option_signature):
                del desired[sku_id]
            else:
                await self.db.delete(link)
        await self.db.flush()
        for sku_id, (group_id, options, signature) in desired.items():
            self.db.add(
                ProductGroupVariant(
                    team_id=team_id,
                    product_group_id=group_id,
                    source_sku_id=sku_id,
                    options=options,
                    option_signature=signature,
                )
            )


def _category(sku: Sku) -> str:
    return (sku.category or "").strip().lower()


def _group_options(group: ReviewedGroup) -> dict[str, list[str]]:
    return {
        axis: list(dict.fromkeys(variant.options[axis] for variant in group.variants))
        for axis in group.variants[0].options
    }


def _store_reviewed_photo(relative_path: str, data: bytes, digest: str) -> str:
    try:
        key = save_bytes(relative_path, data)
    except FileExistsError:
        key = tenant_storage_ref(relative_path)
    if hashlib.sha256(read_bytes(key)).hexdigest() != digest:
        raise ConflictError("Stored gallery image did not match the approved checksum")
    return key


def _setting_source(sku: Sku, row: ReviewedSku) -> str | None:
    if not row.retain_current_photo_as_setting:
        return None
    key = sku.setting_photo_storage_key or sku.photo_storage_key
    if not key:
        raise ValidationError("The SKU has no current photo to retain as a setting")
    return key


def _validate_setting_distinct(row: ReviewedSku, digest: str) -> None:
    if any(photo.sha256 == digest for photo in row.gallery or ()):
        raise ValidationError("The retained setting photo must be distinct from the studio photos")


def _read_setting_photo(
    key: str, row: ReviewedSku, *, preserved: bool, detail_key: str | None
) -> tuple[bytes, str]:
    try:
        data = read_bytes(key)
        if len(data) > 5 * 1024 * 1024:
            raise ValidationError("The current setting photo is larger than 5 MiB")
        validate_jpeg(data)
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("The current photo must be available as a readable JPEG") from exc
    digest = hashlib.sha256(data).hexdigest()
    if preserved and digest != PurePosixPath(key).stem:
        raise ConflictError("The retained setting photo did not match its checksum")
    _validate_setting_distinct(row, digest)
    if detail_key and digest == PurePosixPath(detail_key).stem:
        raise ValidationError("The retained setting photo must be distinct from the detail photo")
    return data, digest


def _preserve_setting_photo(
    row: ReviewedSku, key: str, *, preserved: bool, detail_key: str | None
) -> str:
    data, digest = _read_setting_photo(key, row, preserved=preserved, detail_key=detail_key)
    if preserved:
        return key
    return _store_reviewed_photo(f"skus/{row.sku_id}/setting/{digest}.jpg", data, digest)
