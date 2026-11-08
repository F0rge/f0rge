from __future__ import annotations

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.supplier import SupplierCRUD
from app.models.supplier import Supplier
from app.schemas.supplier import SupplierCreate, SupplierResponse
from f0rge_core.exceptions import ConflictError


class SupplierService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = SupplierCRUD(db)

    async def list(self) -> list[SupplierResponse]:
        suppliers = await self.crud.list_all()
        return [SupplierResponse.model_validate(s) for s in suppliers]

    async def create(self, data: SupplierCreate) -> SupplierResponse:
        currency = (data.default_currency or "").strip().upper() or "USD"
        existing = await self.crud.get_by_name_insensitive(data.name)
        if existing is not None:
            raise ConflictError("A supplier with this name already exists")

        supplier = Supplier(
            name=data.name,
            default_currency=currency,
            vat_number=normalize_vat_number(data.vat_number),
            address=(data.address or "").strip() or None,
        )
        await self.crud.add_and_flush(supplier)
        try:
            await self.crud.commit_refresh(supplier)
        except IntegrityError as exc:
            raise ConflictError("A supplier with this name already exists") from exc
        reloaded = await self.crud.get_by_id(supplier.id)
        assert reloaded is not None
        return SupplierResponse.model_validate(reloaded)

    @staticmethod
    def normalize_currency(value: Optional[str]) -> str:
        return (value or "").strip().upper() or "USD"


def normalize_vat_number(value: Optional[str]) -> Optional[str]:
    """Strip spaces and dashes so '498 765 4321' matches '4987654321'."""
    if value is None:
        return None
    cleaned = "".join(ch for ch in value.upper() if ch.isalnum())
    return cleaned or None
