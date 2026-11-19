"""Standalone warehouse transfers available to a staff member through MCP."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.transfer import TransferCRUD
from app.models.location_bin import LocationBin
from app.models.mcp_token import McpToken
from app.models.transfer import Transfer, TransferStatus
from app.permissions import STOCK_TRANSFER, TILL_SELL
from app.schemas.transfer import (
    TransferCreate,
    TransferLineCreate,
    TransferReceive,
    TransferReceiveLine,
    TransferResponse,
)
from app.services.mcp_domains import Action
from app.services.transfers import TransferService
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError


class TransferDraftLine(TransferLineCreate):
    model_config = ConfigDict(extra="forbid")


class TransferDraftArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_location_id: uuid.UUID
    to_location_id: uuid.UUID
    lines: list[TransferDraftLine] = Field(min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=500)


class DispatchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transfer_id: uuid.UUID


class CountedLine(TransferReceiveLine):
    model_config = ConfigDict(extra="forbid")


class ReceiveArguments(DispatchArguments):
    lines: list[CountedLine] = Field(min_length=1, max_length=50)


def _receipt(transfer: TransferResponse) -> dict:
    return {
        "transfer_id": str(transfer.id),
        "transfer_number": transfer.transfer_number,
        "status": transfer.status.value,
        "href": "/transfers",
    }


async def _draft(db: AsyncSession, token: McpToken, args: TransferDraftArguments) -> dict:
    transfer = await TransferService(db).stage_draft(
        TransferCreate(**args.model_dump()), token.user_id
    )
    return _receipt(transfer)


async def _dispatch(db: AsyncSession, token: McpToken, args: DispatchArguments) -> dict:
    transfer = await TransferService(db).stage_dispatch(args.transfer_id, token.user_id)
    return _receipt(transfer)


async def _receive(db: AsyncSession, token: McpToken, args: ReceiveArguments) -> dict:
    transfer = await TransferService(db).stage_receipt(
        args.transfer_id, TransferReceive(lines=args.lines), token.user_id
    )
    return _receipt(transfer)


def _quantity(value: Decimal) -> str:
    return format(value.normalize(), "f")


async def _review_bins(
    db: AsyncSession, transfer: Transfer, bin_ids: set[uuid.UUID]
) -> tuple[dict, dict]:
    # Lock the resolved default as well as named bins until the approved movement
    # finishes. A change of default between request and confirmation changes the snapshot.
    rows = await db.scalars(
        select(LocationBin)
        .where(
            LocationBin.team_id == transfer.team_id,
            LocationBin.location_id.in_([transfer.from_location_id, transfer.to_location_id]),
            or_(LocationBin.id.in_(bin_ids), LocationBin.is_default.is_(True)),
        )
        .order_by(LocationBin.id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    by_id = {row.id: row for row in rows}
    defaults = {
        row.location_id: row for row in by_id.values() if row.is_default and not row.is_archived
    }
    return by_id, defaults


async def preview_transfer(
    db: AsyncSession, token: McpToken, action_name: str, args: DispatchArguments
) -> dict:
    """Rebuild the same review inside the confirmation transaction before moving stock."""
    transfer = await TransferCRUD(db).get_by_id(args.transfer_id, for_update=True)
    if transfer is None or transfer.team_id != token.team_id:
        raise NotFoundError("Transfer not found")
    if transfer.pick_id is not None:
        raise ConflictError("Complete transfers linked to a pick in the warehouse")
    if len(transfer.lines) > 50:
        raise ValidationError("Review transfers with more than 50 lines in the warehouse")

    counted = {}
    if action_name == "transfers_receive" and isinstance(args, ReceiveArguments):
        if transfer.status != TransferStatus.IN_TRANSIT:
            raise ConflictError("Transfer is not in transit")
        counted = {item.line_id: item.qty_received for item in args.lines}
        if len(counted) != len(args.lines) or counted.keys() != {
            line.id for line in transfer.lines
        }:
            raise ValidationError("Enter one counted quantity for each transfer line")
        if any(counted[line.id] != line.qty_dispatched for line in transfer.lines):
            raise ValidationError("The counts differ from dispatch. Resolve this in the warehouse")
    elif action_name == "transfers_dispatch":
        if transfer.status != TransferStatus.DRAFT:
            raise ConflictError("Transfer is not a draft")
    else:
        raise ValidationError("Unsupported transfer review")

    bin_ids = {
        bin_id
        for line in transfer.lines
        for bin_id in (line.from_bin_id, line.to_bin_id)
        if bin_id is not None
    }
    by_id, defaults = await _review_bins(db, transfer, bin_ids)
    lines = []
    for line in sorted(transfer.lines, key=lambda line: line.id):
        source = (
            by_id.get(line.from_bin_id)
            if line.from_bin_id
            else defaults.get(transfer.from_location_id)
        )
        dest = (
            by_id.get(line.to_bin_id) if line.to_bin_id else defaults.get(transfer.to_location_id)
        )
        if not source or not dest or dest.is_archived:
            raise ConflictError(
                "Select active destination and available source bins in the warehouse"
            )
        detail = {
            "line_id": str(line.id),
            "sku_id": str(line.sku_id),
            "sku": line.sku.our_ref,
            "name": line.sku.name,
            "quantity": _quantity(line.qty_dispatched),
            "from_bin_id": str(source.id),
            "from_bin": source.code,
            "to_bin_id": str(dest.id),
            "to_bin": dest.code,
        }
        if counted:
            detail["counted_quantity"] = _quantity(counted[line.id])
        lines.append(detail)

    return {
        "transfer_id": str(transfer.id),
        "transfer_number": transfer.transfer_number,
        "status": transfer.status.value,
        "from_location_id": str(transfer.from_location_id),
        "from_location": transfer.from_location.name,
        "to_location_id": str(transfer.to_location_id),
        "to_location": transfer.to_location.name,
        "lines": lines,
    }


TRANSFER_ACTIONS = (
    Action(
        name="transfers_create_draft",
        tab="Warehouse / Transfers",
        description="Draft a numbered transfer between locations. Stock stays in place.",
        arguments=TransferDraftArguments,
        permissions=(STOCK_TRANSFER,),
        handler=_draft,
        effect="write",
    ),
    Action(
        name="transfers_dispatch",
        tab="Warehouse / Transfers",
        description="Request dispatch of a draft transfer. Confirmation removes stock at the source.",
        arguments=DispatchArguments,
        permissions=(STOCK_TRANSFER,),
        handler=_dispatch,
        effect="review",
    ),
    Action(
        name="transfers_receive",
        tab="Warehouse / Transfers",
        description="Request receipt of a transfer in transit using actual counts for every line. Confirmation adds stock at its destination.",
        arguments=ReceiveArguments,
        permissions=(STOCK_TRANSFER, TILL_SELL),
        handler=_receive,
        effect="review",
    ),
)
