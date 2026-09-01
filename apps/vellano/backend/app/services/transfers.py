from __future__ import annotations

import datetime
import uuid
from typing import Optional

from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location import LocationCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku import SkuCRUD
from app.crud.transfer import TransferCRUD
from app.crud.user import UserCRUD
from app.models.transfer import Transfer, TransferLine, TransferStatus
from app.models.unit_cost_audit import UnitCostAuditSource
from app.models.user import User
from app.permissions import USERS_MANAGE
from app.services.permissions import PermissionService
from app.schemas.transfer import (
    TransferCreate,
    TransferLineResponse,
    TransferReceive,
    TransferResponse,
)
from app.services.location_bins import LocationBinService
from app.services.stock_movements import StockMovementService
from app.services.stocktakes import StocktakeService
from app.services.transfer_note import build_transfer_note_pdf
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


def _display_name(user: User) -> str:
    if user.display_name:
        return user.display_name
    return user.email


class TransferService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = TransferCRUD(db)
        self.location_crud = LocationCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.user_crud = UserCRUD(db)
        self.location_stock_crud = LocationStockCRUD(db)
        self.stock_movements = StockMovementService(db)
        self.bins = LocationBinService(db)
        self.stocktakes = StocktakeService(db)

    async def list(
        self,
        status: Optional[TransferStatus] = None,
        to_location_id: Optional[uuid.UUID] = None,
    ) -> list[TransferResponse]:
        rows = await self.crud.list_all(status=status, to_location_id=to_location_id)
        return [self._to_response(row) for row in rows]

    async def get(self, transfer_id: uuid.UUID) -> TransferResponse:
        return self._to_response(await self._get_or_404(transfer_id))

    async def create(self, data: TransferCreate, user_id: uuid.UUID) -> TransferResponse:
        if data.from_location_id == data.to_location_id:
            raise ValidationError("Source and destination locations must differ")

        from_location = await self._active_location(data.from_location_id, "Source")
        to_location = await self._active_location(data.to_location_id, "Destination")

        lines: list[TransferLine] = []
        for item in data.lines:
            sku = await self.sku_crud.get_by_id(item.sku_id)
            if sku is None:
                raise NotFoundError("SKU not found")
            if item.from_bin_id is not None:
                await self.bins.resolve_for_movement(
                    from_location.id,
                    item.from_bin_id,
                    incoming=False,
                )
            if item.to_bin_id is not None:
                await self.bins.resolve_for_movement(
                    to_location.id,
                    item.to_bin_id,
                    incoming=True,
                )
            lines.append(
                TransferLine(
                    sku_id=sku.id,
                    qty_dispatched=item.qty,
                    qty_received=None,
                    from_bin_id=item.from_bin_id,
                    to_bin_id=item.to_bin_id,
                    unit_cost_zar=None,
                )
            )

        transfer = Transfer(
            transfer_number=await self.crud.get_next_transfer_number(),
            status=TransferStatus.DRAFT,
            from_location_id=from_location.id,
            to_location_id=to_location.id,
            created_by_user_id=user_id,
            notes=data.notes,
            lines=lines,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(transfer)
        return self._to_response(await self._get_or_404(transfer.id))

    async def dispatch(self, transfer_id: uuid.UUID, user_id: uuid.UUID) -> TransferResponse:
        transfer = await self._get_or_404(transfer_id)
        if transfer.status != TransferStatus.DRAFT:
            raise ConflictError("Transfer is not a draft")

        await self.stocktakes.assert_location_unlocked(transfer.from_location_id)
        await self.stocktakes.assert_location_unlocked(transfer.to_location_id)
        from_location = await self._active_location(transfer.from_location_id, "Source")
        await self._active_location(transfer.to_location_id, "Destination")

        now = datetime.datetime.utcnow()
        async with unit_of_work(self.db):
            for line in transfer.lines:
                source_stock = await self.location_stock_crud.get_by_sku_and_location(
                    line.sku_id,
                    from_location.id,
                )
                if source_stock is None or source_stock.unit_cost_zar is None:
                    raise ConflictError("Source location has no unit cost for this SKU")
                line.unit_cost_zar = source_stock.unit_cost_zar
                await self.stock_movements.apply_outgoing_qty(
                    sku_id=line.sku_id,
                    location_id=from_location.id,
                    qty=line.qty_dispatched,
                    user_id=user_id,
                    source=UnitCostAuditSource.RECEIVE,
                    note="Transfer out",
                    bin_id=line.from_bin_id,
                    record_audit=False,
                )
            transfer.status = TransferStatus.IN_TRANSIT
            transfer.dispatched_at = now
            transfer.dispatched_by_user_id = user_id

        return self._to_response(await self._get_or_404(transfer_id))

    async def receive(
        self,
        transfer_id: uuid.UUID,
        data: TransferReceive,
        user_id: uuid.UUID,
    ) -> TransferResponse:
        transfer = await self._get_or_404(transfer_id)
        if transfer.status != TransferStatus.IN_TRANSIT:
            raise ConflictError("Transfer is not in transit")

        await self.stocktakes.assert_location_unlocked(transfer.to_location_id)
        to_location = await self._active_location(transfer.to_location_id, "Destination")

        payload = {item.line_id: item.qty_received for item in data.lines}
        if len(payload) != len(data.lines):
            raise ValidationError("Duplicate transfer line")
        expected_ids = {line.id for line in transfer.lines}
        if set(payload.keys()) != expected_ids:
            raise ValidationError("Receive must include every transfer line")

        user = await self.user_crud.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")

        now = datetime.datetime.utcnow()
        async with unit_of_work(self.db):
            for line in transfer.lines:
                qty_received = payload[line.id]
                if qty_received != line.qty_dispatched:
                    raise ValidationError("qty_received must equal qty_dispatched")
                if line.unit_cost_zar is None:
                    raise ConflictError("Source location has no unit cost for this SKU")
                await self.stock_movements.apply_incoming_qty(
                    sku_id=line.sku_id,
                    location_id=to_location.id,
                    qty=qty_received,
                    unit_cost_zar=line.unit_cost_zar,
                    user_id=user_id,
                    source=UnitCostAuditSource.RECEIVE,
                    note="Transfer in",
                    bin_id=line.to_bin_id,
                    record_audit=False,
                )
                line.qty_received = qty_received
            transfer.status = TransferStatus.RECEIVED
            transfer.received_at = now
            transfer.received_by_user_id = user_id
            transfer.received_display_name = _display_name(user)

        return self._to_response(await self._get_or_404(transfer_id))

    async def cancel(self, transfer_id: uuid.UUID, user_id: uuid.UUID) -> TransferResponse:
        transfer = await self._get_or_404(transfer_id)
        if transfer.status == TransferStatus.RECEIVED:
            raise ConflictError("Cannot cancel a received transfer")
        if transfer.status == TransferStatus.CANCELLED:
            raise ConflictError("Transfer is already cancelled")

        if transfer.status == TransferStatus.IN_TRANSIT:
            if not await PermissionService(self.db).has_permission(user_id, USERS_MANAGE):
                raise ConflictError("Owner access required")
            await self.stocktakes.assert_location_unlocked(transfer.from_location_id)
            from_location = await self._active_location(transfer.from_location_id, "Source")
            async with unit_of_work(self.db):
                for line in transfer.lines:
                    if line.unit_cost_zar is None:
                        raise ConflictError("Source location has no unit cost for this SKU")
                    await self.stock_movements.apply_incoming_qty(
                        sku_id=line.sku_id,
                        location_id=from_location.id,
                        qty=line.qty_dispatched,
                        unit_cost_zar=line.unit_cost_zar,
                        user_id=user_id,
                        source=UnitCostAuditSource.RECEIVE,
                        note="Transfer cancel restock",
                        bin_id=line.from_bin_id,
                        record_audit=False,
                    )
                transfer.status = TransferStatus.CANCELLED
        else:
            async with unit_of_work(self.db):
                transfer.status = TransferStatus.CANCELLED

        return self._to_response(await self._get_or_404(transfer_id))

    async def serve_pdf(self, transfer_id: uuid.UUID) -> Response:
        transfer = await self._get_or_404(transfer_id)
        dispatcher = transfer.dispatched_by
        pdf_bytes = build_transfer_note_pdf(
            transfer_number=transfer.transfer_number,
            status=transfer.status.value,
            from_location_name=transfer.from_location.name,
            to_location_name=transfer.to_location.name,
            dispatcher_name=_display_name(dispatcher) if dispatcher is not None else None,
            dispatched_at=transfer.dispatched_at,
            receiver_name=transfer.received_display_name,
            received_at=transfer.received_at,
            lines=[
                (
                    line.sku.our_ref,
                    line.sku.name,
                    line.qty_dispatched,
                    line.qty_received,
                )
                for line in transfer.lines
            ],
        )
        return Response(content=pdf_bytes, media_type="application/pdf")

    async def _get_or_404(self, transfer_id: uuid.UUID) -> Transfer:
        transfer = await self.crud.get_by_id(transfer_id)
        if transfer is None:
            raise NotFoundError("Transfer not found")
        return transfer

    async def _active_location(self, location_id: uuid.UUID, side: str):
        location = await self.location_crud.get_by_id(location_id)
        if location is None:
            raise NotFoundError(f"{side} location not found")
        if location.is_archived:
            if side == "Source":
                raise ConflictError("Cannot transfer from archived location")
            raise ConflictError("Cannot transfer into archived location")
        return location

    @staticmethod
    def _to_response(row: Transfer) -> TransferResponse:
        return TransferResponse(
            id=row.id,
            transfer_number=row.transfer_number,
            status=row.status,
            from_location_id=row.from_location_id,
            from_location_name=row.from_location.name,
            to_location_id=row.to_location_id,
            to_location_name=row.to_location.name,
            notes=row.notes,
            created_by_user_id=row.created_by_user_id,
            dispatched_at=row.dispatched_at,
            dispatched_by_user_id=row.dispatched_by_user_id,
            received_at=row.received_at,
            received_by_user_id=row.received_by_user_id,
            received_display_name=row.received_display_name,
            lines=[
                TransferLineResponse(
                    id=line.id,
                    sku_id=line.sku_id,
                    sku_our_ref=line.sku.our_ref,
                    sku_name=line.sku.name,
                    qty_dispatched=line.qty_dispatched,
                    qty_received=line.qty_received,
                    from_bin_id=line.from_bin_id,
                    to_bin_id=line.to_bin_id,
                    unit_cost_zar=line.unit_cost_zar,
                )
                for line in row.lines
            ],
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
