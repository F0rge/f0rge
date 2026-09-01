from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location import LocationCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku import SkuCRUD
from app.models.sku import Sku
from app.models.unit_cost_audit import UnitCostAuditSource
from app.schemas.catalogue_import import (
    CatalogueImportCommitResponse,
    CatalogueImportFilePreview,
    CatalogueImportPreviewResponse,
    CatalogueImportRowError,
    CatalogueImportSohPreview,
)
from app.services.catalogue_csv import (
    InventoryCsvParse,
    InventoryCsvRow,
    SohCsvParse,
    parse_inventory_csv,
    parse_soh_csv,
)
from app.services.stock_movements import StockMovementService
from app.services.stocktakes import StocktakeService
from app.services.vat import inc_to_ex
from f0rge_core.exceptions import ValidationError
from f0rge_db.crud import unit_of_work


class CatalogueImportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.sku_crud = SkuCRUD(db)
        self.location_crud = LocationCRUD(db)
        self.location_stock_crud = LocationStockCRUD(db)
        self.stock_movements = StockMovementService(db)
        self.stocktakes = StocktakeService(db)

    async def preview(
        self,
        inventory: UploadFile,
        soh: Optional[UploadFile],
        inventory_map: Optional[str],
        soh_map: Optional[str],
        _user_id: uuid.UUID,
    ) -> CatalogueImportPreviewResponse:
        inventory_bytes = await inventory.read()
        soh_bytes = await soh.read() if soh is not None else None
        parsed_inventory, parsed_soh, errors = await self._parse_and_validate(
            inventory_bytes,
            soh_bytes,
            inventory_map,
            soh_map,
        )
        create_count, update_count = await self._create_update_counts(parsed_inventory)
        soh_preview = None
        if parsed_soh is not None:
            soh_preview = CatalogueImportSohPreview(
                headers=parsed_soh.headers,
                suggested_map=parsed_soh.suggested_map,
                applied_map=parsed_soh.applied_map,
                sample_row=parsed_soh.sample_row,
                row_count=parsed_soh.row_count,
            )
        return CatalogueImportPreviewResponse(
            ok=not errors,
            errors=errors,
            inventory=CatalogueImportFilePreview(
                headers=parsed_inventory.headers,
                suggested_map=parsed_inventory.suggested_map,
                applied_map=parsed_inventory.applied_map,
                sample_row=parsed_inventory.sample_row,
                row_count=parsed_inventory.row_count,
                create_count=create_count,
                update_count=update_count,
            ),
            soh=soh_preview,
        )

    async def commit(
        self,
        inventory: UploadFile,
        soh: Optional[UploadFile],
        inventory_map: Optional[str],
        soh_map: Optional[str],
        user_id: uuid.UUID,
    ) -> CatalogueImportCommitResponse:
        inventory_bytes = await inventory.read()
        soh_bytes = await soh.read() if soh is not None else None
        parsed_inventory, parsed_soh, errors = await self._parse_and_validate(
            inventory_bytes,
            soh_bytes,
            inventory_map,
            soh_map,
        )
        if errors:
            raise ValidationError(errors[0].message)

        soh_rows = parsed_soh.row_count if parsed_soh is not None else 0
        async with unit_of_work(self.db):
            sku_ids, inventory_costs, created_skus, updated_skus = await self._apply_inventory(
                parsed_inventory
            )
            if parsed_soh is not None:
                await self._apply_soh(parsed_soh, sku_ids, inventory_costs, user_id)
        return CatalogueImportCommitResponse(
            created_skus=created_skus,
            updated_skus=updated_skus,
            soh_rows=soh_rows,
        )

    async def _parse_and_validate(
        self,
        inventory_bytes: bytes,
        soh_bytes: Optional[bytes],
        inventory_map: Optional[str],
        soh_map: Optional[str],
    ) -> tuple[InventoryCsvParse, Optional[SohCsvParse], list[CatalogueImportRowError]]:
        parsed_inventory = parse_inventory_csv(inventory_bytes, inventory_map)
        parsed_soh = parse_soh_csv(soh_bytes, soh_map) if soh_bytes is not None else None
        errors: list[CatalogueImportRowError] = [
            CatalogueImportRowError(file="inventory", row=item.row, message=item.message)
            for item in parsed_inventory.errors
        ]
        await self._validate_inventory_rows(parsed_inventory, errors)
        if parsed_soh is not None:
            errors.extend(
                CatalogueImportRowError(file="soh", row=item.row, message=item.message)
                for item in parsed_soh.errors
            )
            await self._validate_soh_rows(parsed_inventory, parsed_soh, errors)
        return parsed_inventory, parsed_soh, errors

    async def _validate_inventory_rows(
        self,
        parsed: InventoryCsvParse,
        errors: list[CatalogueImportRowError],
    ) -> None:
        seen_refs: dict[str, int] = {}
        seen_barcodes: dict[str, str] = {}
        for row in parsed.rows:
            if row.our_ref is None:
                continue
            if row.our_ref in seen_refs:
                errors.append(
                    CatalogueImportRowError(
                        file="inventory",
                        row=row.row,
                        message=f"Duplicate our_ref: {row.our_ref}",
                    )
                )
                continue
            seen_refs[row.our_ref] = row.row
            existing = await self.sku_crud.get_by_our_ref(row.our_ref)
            barcode = row.barcode
            if barcode is None and existing is None:
                barcode = f"csv:{row.our_ref}"
            if barcode is None:
                continue
            if barcode in seen_barcodes and seen_barcodes[barcode] != row.our_ref:
                errors.append(
                    CatalogueImportRowError(
                        file="inventory",
                        row=row.row,
                        message=f"Barcode collides with another SKU: {barcode}",
                    )
                )
                continue
            seen_barcodes[barcode] = row.our_ref
            existing_barcode = await self.sku_crud.get_by_our_barcode(barcode)
            if existing_barcode is not None and existing_barcode.our_ref != row.our_ref:
                errors.append(
                    CatalogueImportRowError(
                        file="inventory",
                        row=row.row,
                        message=f"Barcode collides with another SKU: {barcode}",
                    )
                )

    async def _validate_soh_rows(
        self,
        inventory: InventoryCsvParse,
        parsed: SohCsvParse,
        errors: list[CatalogueImportRowError],
    ) -> None:
        known_refs = {
            row.our_ref for row in inventory.rows if row.our_ref is not None and not row.errors
        }
        inventory_costs = self._inventory_costs(inventory)
        seen_pairs: dict[tuple[str, str], int] = {}
        for row in parsed.rows:
            if row.our_ref is None or row.location is None or row.qty is None:
                continue
            pair = (row.our_ref, row.location.lower())
            if pair in seen_pairs:
                errors.append(
                    CatalogueImportRowError(
                        file="soh",
                        row=row.row,
                        message=f"Duplicate SOH row for {row.our_ref} at {row.location}",
                    )
                )
                continue
            seen_pairs[pair] = row.row

            sku = await self.sku_crud.get_by_our_ref(row.our_ref)
            if sku is None and row.our_ref not in known_refs:
                errors.append(
                    CatalogueImportRowError(
                        file="soh",
                        row=row.row,
                        message=f"SKU not found: {row.our_ref}",
                    )
                )
                continue

            location = await self.location_crud.get_active_by_name_insensitive(row.location)
            if location is None:
                errors.append(
                    CatalogueImportRowError(
                        file="soh",
                        row=row.row,
                        message=f"Unknown location: {row.location}",
                    )
                )
                continue

            current = 0
            loc_cost = None
            if sku is not None:
                loc_stock = await self.location_stock_crud.get_by_sku_and_location(
                    sku.id,
                    location.id,
                )
                if loc_stock is not None:
                    current = loc_stock.on_hand
                    loc_cost = loc_stock.unit_cost_zar
            delta = row.qty - current
            if delta <= 0:
                continue
            cost = row.unit_cost_zar or inventory_costs.get(row.our_ref) or loc_cost
            if cost is None:
                errors.append(
                    CatalogueImportRowError(
                        file="soh",
                        row=row.row,
                        message="unit cost required to increase stock",
                    )
                )

    async def _apply_inventory(
        self,
        parsed: InventoryCsvParse,
    ) -> tuple[dict[str, uuid.UUID], dict[str, Decimal], int, int]:
        sku_ids: dict[str, uuid.UUID] = {}
        inventory_costs = self._inventory_costs(parsed)
        seen: set[str] = set()
        created_skus = 0
        updated_skus = 0
        for row in parsed.rows:
            if row.our_ref is None or row.our_ref in seen:
                continue
            seen.add(row.our_ref)
            existing = await self.sku_crud.get_by_our_ref(row.our_ref)
            sku = await self._upsert_inventory_row(row)
            sku_ids[row.our_ref] = sku.id
            if existing is None:
                created_skus += 1
            else:
                updated_skus += 1
        return sku_ids, inventory_costs, created_skus, updated_skus

    async def _upsert_inventory_row(self, row: InventoryCsvRow) -> Sku:
        assert row.our_ref is not None
        assert row.name is not None
        assert row.retail_inc_vat is not None
        retail_ex = inc_to_ex(row.retail_inc_vat)
        existing = await self.sku_crud.get_by_our_ref(row.our_ref)
        if existing is not None:
            existing.name = row.name
            existing.retail_ex_vat = retail_ex
            existing.category = row.category
            if row.barcode:
                existing.our_barcode = row.barcode
            return existing
        sku = Sku(
            our_ref=row.our_ref,
            our_barcode=row.barcode or f"csv:{row.our_ref}",
            name=row.name,
            design=f"csv:{row.our_ref}",
            fabric="-",
            category=row.category,
            retail_ex_vat=retail_ex,
        )
        await self.sku_crud.add_and_flush(sku)
        return sku

    async def _apply_soh(
        self,
        parsed: SohCsvParse,
        sku_ids: dict[str, uuid.UUID],
        inventory_costs: dict[str, Decimal],
        user_id: uuid.UUID,
    ) -> None:
        seen_locations: set[uuid.UUID] = set()
        for row in parsed.rows:
            if row.our_ref is None or row.location is None or row.qty is None:
                continue
            sku_id = sku_ids.get(row.our_ref)
            if sku_id is None:
                sku = await self.sku_crud.get_by_our_ref(row.our_ref)
                assert sku is not None
                sku_id = sku.id
            location = await self.location_crud.get_active_by_name_insensitive(row.location)
            assert location is not None
            if location.id not in seen_locations:
                await self.stocktakes.assert_location_unlocked(location.id)
                seen_locations.add(location.id)
            loc_stock = await self.location_stock_crud.get_by_sku_and_location(sku_id, location.id)
            loc_cost = loc_stock.unit_cost_zar if loc_stock is not None else None
            unit_cost = row.unit_cost_zar or inventory_costs.get(row.our_ref) or loc_cost
            await self.stock_movements.set_on_hand(
                sku_id=sku_id,
                location_id=location.id,
                qty=row.qty,
                user_id=user_id,
                source=UnitCostAuditSource.IMPORT,
                note=f"CSV import SET on_hand={row.qty}",
                unit_cost_zar=unit_cost,
            )

    async def _create_update_counts(self, parsed: InventoryCsvParse) -> tuple[int, int]:
        create_count = 0
        update_count = 0
        seen: set[str] = set()
        for row in parsed.rows:
            if row.our_ref is None or row.our_ref in seen:
                continue
            seen.add(row.our_ref)
            existing = await self.sku_crud.get_by_our_ref(row.our_ref)
            if existing is None:
                create_count += 1
            else:
                update_count += 1
        return create_count, update_count

    @staticmethod
    def _inventory_costs(parsed: InventoryCsvParse) -> dict[str, Decimal]:
        costs: dict[str, Decimal] = {}
        for row in parsed.rows:
            if row.our_ref is None or row.cost_zar is None or row.our_ref in costs:
                continue
            costs[row.our_ref] = row.cost_zar
        return costs
