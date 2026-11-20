"""Standalone warehouse transfers available to a staff member through MCP."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.transfer import TransferCRUD
from app.models.location_bin import LocationBin
from app.models.mcp_token import McpToken
from app.models.transfer import Transfer
from app.permissions import STOCK_TRANSFER, TILL_SELL
from app.schemas.transfer import (
    TransferCreate,
    TransferLineCreate,
    TransferReceive,
    TransferReceiveLine,
    TransferResponse,
)
from app.services.mcp_action_types import Action
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
    await _check_standalone_transfer(db, token, args.transfer_id)
    transfer = await TransferService(db).stage_dispatch(args.transfer_id, token.user_id)
    return _receipt(transfer)


async def _receive(db: AsyncSession, token: McpToken, args: ReceiveArguments) -> dict:
    await _check_standalone_transfer(db, token, args.transfer_id)
    transfer = await TransferService(db).stage_receipt(
        args.transfer_id, TransferReceive(lines=args.lines), token.user_id
    )
    return _receipt(transfer)


async def cancel_draft(db: AsyncSession, token: McpToken, args: Any) -> dict:
    await _standalone_transfer(db, token, args.transfer_id)
    return _receipt(await TransferService(db).stage_cancel_draft(args.transfer_id))


async def _movement_bins(
    db: AsyncSession, transfer: Transfer, bin_ids: set[uuid.UUID]
) -> tuple[dict, dict]:
    # Keep both named and default bins stable through the stock movement.
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


async def _standalone_transfer(
    db: AsyncSession, token: McpToken, transfer_id: uuid.UUID
) -> Transfer:
    """Lock a transfer in the token's business. Pick-linked transfers stay in the warehouse."""
    transfer = await TransferCRUD(db).get_by_id(transfer_id, for_update=True)
    if transfer is None or transfer.team_id != token.team_id:
        raise NotFoundError("Transfer not found")
    if transfer.pick_id is not None:
        raise ConflictError("Complete transfers linked to a pick in the warehouse")
    return transfer


async def _check_standalone_transfer(
    db: AsyncSession, token: McpToken, transfer_id: uuid.UUID
) -> None:
    """Apply MCP scope and bin checks under the same lock as the domain transition."""
    transfer = await _standalone_transfer(db, token, transfer_id)
    if len(transfer.lines) > 50:
        raise ValidationError("Process transfers with more than 50 lines in the warehouse")

    bin_ids = {
        bin_id
        for line in transfer.lines
        for bin_id in (line.from_bin_id, line.to_bin_id)
        if bin_id is not None
    }
    by_id, defaults = await _movement_bins(db, transfer, bin_ids)
    for line in transfer.lines:
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
        description="Dispatch a standalone draft transfer now. This removes stock at the source.",
        arguments=DispatchArguments,
        permissions=(STOCK_TRANSFER,),
        handler=_dispatch,
        effect="write",
    ),
    Action(
        name="transfers_receive",
        tab="Warehouse / Transfers",
        description="Receive a standalone transfer in transit now. Supply the actual counted quantity for every line. This adds stock at the destination.",
        arguments=ReceiveArguments,
        permissions=(STOCK_TRANSFER, TILL_SELL),
        handler=_receive,
        effect="write",
    ),
)
