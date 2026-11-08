from __future__ import annotations

import uuid

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.customer_portal_user import CustomerPortalUserCRUD
from app.crud.sku import SkuCRUD
from app.models.customer_portal_user import CustomerPortalUser
from app.schemas.customer_portal import (
    PortalCatalogueItem,
    PortalLoginRequest,
    PortalLoginResponse,
    PortalMeResponse,
    PortalOrderCreate,
    PortalUserCreate,
)
from app.schemas.sales_order import SalesOrderCreate, SalesOrderLineCreate, SalesOrderResponse
from app.services.pricing import resolve_unit_ex_vat
from app.services.portal_identity import PortalPrincipal
from app.services.sales_orders import SalesOrdersService
from app.services.vat import ex_to_inc
from f0rge_core.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError

CUSTOMER_COOKIE_NAME = "firstout_customer_session"


def clear_customer_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=CUSTOMER_COOKIE_NAME,
        path="/",
        secure=settings.cookie_secure,
    )


class CustomerPortalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = CustomerPortalUserCRUD(db)
        self.sku_crud = SkuCRUD(db)
        self.orders = SalesOrdersService(db)

    async def create_user(
        self,
        customer_id: uuid.UUID,
        data: PortalUserCreate,
    ) -> PortalMeResponse:
        raise ValidationError(
            "Invite customers to sign in with Clerk; temporary passwords are retired"
        )

    async def login(self, data: PortalLoginRequest, response: Response) -> PortalLoginResponse:
        raise ValidationError("Sign in with Clerk; local portal password login has been retired")

    async def logout(self, response: Response) -> None:
        clear_customer_session_cookie(response)

    async def me(self, principal: PortalPrincipal) -> PortalMeResponse:
        user = await self._require_user(principal.portal_user_id)
        return self._to_me(user).model_copy(
            update={"access_id": principal.access_id, "organisation_id": principal.organisation_id}
        )

    async def catalogue(self, portal_user_id: uuid.UUID) -> list[PortalCatalogueItem]:
        user = await self._require_user(portal_user_id)
        skus = await self.sku_crud.list_all()
        items: list[PortalCatalogueItem] = []
        for sku in skus:
            try:
                unit_ex = await resolve_unit_ex_vat(self.db, sku, user.customer)
            except ValidationError:
                continue
            items.append(
                PortalCatalogueItem(
                    id=sku.id,
                    our_ref=sku.our_ref,
                    name=sku.name,
                    unit_ex_vat=unit_ex,
                    unit_inc_vat=ex_to_inc(unit_ex),
                )
            )
        return items

    async def place_order(
        self,
        portal_user_id: uuid.UUID,
        data: PortalOrderCreate,
    ) -> SalesOrderResponse:
        user = await self._require_user(portal_user_id)
        if user.customer.on_hold:
            raise ConflictError("Customer is on hold")
        return await self.orders.create_draft(
            SalesOrderCreate(
                customer_id=user.customer_id,
                lines=[
                    SalesOrderLineCreate(sku_id=line.sku_id, qty=line.qty, notes=line.notes)
                    for line in data.lines
                ],
                notes=data.notes,
            ),
            user_id=None,
        )

    async def list_orders(self, portal_user_id: uuid.UUID) -> list[SalesOrderResponse]:
        user = await self._require_user(portal_user_id)
        rows = await self.orders.crud.list_for_customer(user.customer_id)
        return [await self.orders._to_response(row) for row in rows]

    async def _require_user(self, portal_user_id: uuid.UUID) -> CustomerPortalUser:
        user = await self.crud.get_by_id(portal_user_id)
        if user is None or user.is_disabled:
            raise UnauthorizedError("Invalid session")
        if user.customer.customer_type != "trade":
            raise UnauthorizedError("Invalid session")
        return user

    async def _team_id(self) -> uuid.UUID:
        from app.crud.user import TeamCRUD

        team = await TeamCRUD(self.db).get_first()
        if team is None:
            raise NotFoundError("Team not found")
        return team.id

    @staticmethod
    def _to_me(user: CustomerPortalUser) -> PortalMeResponse:
        return PortalMeResponse(
            id=user.id,
            email=user.email,
            customer_id=user.customer_id,
            customer_name=user.customer.name,
            price_tier=user.customer.price_tier,
        )
