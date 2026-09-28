from __future__ import annotations

import hmac
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.ops_commerce import OpsCommerceCRUD
from app.schemas.ops_commerce import OpsProductResponse, OpsProductsResponse
from app.services.vat import ex_to_inc


class OpsCommerceService:
    def __init__(self, db: AsyncSession) -> None:
        self.crud = OpsCommerceCRUD(db)

    async def products(
        self,
        *,
        authorization: Optional[str],
        requested_company: Optional[str],
        request_host: str,
    ) -> OpsProductsResponse:
        if (
            not settings.ops_commerce_token
            or not settings.ops_commerce_company_id
            or not settings.ops_commerce_allowed_host
        ):
            raise HTTPException(status_code=503, detail="Ops Commerce is not configured")
        expected = f"Bearer {settings.ops_commerce_token}"
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Invalid service credential")
        if request_host != settings.ops_commerce_allowed_host:
            raise HTTPException(status_code=403, detail="Wrong operational host")
        try:
            company_id = uuid.UUID(settings.ops_commerce_company_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=503, detail="Invalid Ops Commerce configuration"
            ) from exc
        if requested_company != str(company_id):
            raise HTTPException(status_code=403, detail="Wrong operational company")
        if not await self.crud.has_company(company_id):
            raise HTTPException(status_code=503, detail="Operational company is unavailable")

        snapshots = await self.crud.published_products()
        return OpsProductsResponse(
            company_id=company_id,
            products=[
                OpsProductResponse(
                    source_sku_id=sku.id,
                    sku=sku.sku,
                    name=sku.name,
                    price_minor_zar=int(ex_to_inc(sku.retail_ex_vat) * 100),
                    available_quantity=sku.available_quantity,
                    revision=self._utc_revision(sku.revision),
                    observed_at=self._as_utc(sku.observed_at),
                    product_group_id=sku.product_group_id,
                    product_title=sku.product_title,
                    options=sku.options,
                    acknowledged_commitment_ids=sku.acknowledged_commitment_ids,
                )
                for sku in snapshots
            ],
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )

    @classmethod
    def _utc_revision(cls, value: datetime) -> str:
        return cls._as_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")
