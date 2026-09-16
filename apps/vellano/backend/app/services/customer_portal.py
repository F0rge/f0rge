from __future__ import annotations

import datetime
import uuid

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.crud.customer_portal_user import CustomerPortalUserCRUD
from app.crud.sku import SkuCRUD
from app.crud.team_settings import TeamSettingsCRUD
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
from app.services.auth import (
    hash_password,
    validate_password,
    verify_password,
)
from app.tenancy.context import tenant_ctx
from app.services.pricing import resolve_unit_ex_vat
from app.services.sales_orders import SalesOrdersService
from app.services.vat import ex_to_inc
from f0rge_core.exceptions import ConflictError, NotFoundError, UnauthorizedError, ValidationError
from f0rge_db.crud import unit_of_work
import jwt

JWT_ALGORITHM = "HS256"
CUSTOMER_COOKIE_NAME = "vellano_customer_session"
CUSTOMER_TOKEN_TYP = "customer"


def create_customer_access_token(
    portal_user_id: uuid.UUID, ttl_hours: int, tenant_id: uuid.UUID
) -> str:
    from app.services.auth import _require_jwt_secret

    now = datetime.datetime.utcnow()
    payload = {
        "sub": str(portal_user_id),
        "tid": str(tenant_id),
        "typ": CUSTOMER_TOKEN_TYP,
        "iat": now,
        "exp": now + datetime.timedelta(hours=ttl_hours),
    }
    return jwt.encode(payload, _require_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_customer_access_token(token: str) -> uuid.UUID:
    from app.services.auth import _require_jwt_secret
    from f0rge_core.exceptions import UnauthorizedError as AuthError

    try:
        payload = jwt.decode(token, _require_jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid session") from exc
    if payload.get("typ") != CUSTOMER_TOKEN_TYP:
        raise AuthError("Invalid session")
    if not payload.get("tid"):
        raise AuthError("Invalid session")
    sub = payload.get("sub")
    if not sub:
        raise AuthError("Invalid session")
    try:
        return uuid.UUID(str(sub))
    except ValueError as exc:
        raise AuthError("Invalid session") from exc


def set_customer_session_cookie(response: Response, token: str, *, max_age: int) -> None:
    response.set_cookie(
        key=CUSTOMER_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        secure=settings.cookie_secure,
        max_age=max_age,
    )


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
        from app.crud.customer import CustomerCRUD

        customer = await CustomerCRUD(self.db).get_by_id(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found")
        if customer.customer_type != "trade":
            raise ValidationError("Portal login is only for trade customers")
        validate_password(data.password)
        existing = await self.crud.get_by_email(data.email)
        if existing is not None:
            raise ConflictError("Portal user already exists")
        user = CustomerPortalUser(
            customer_id=customer.id,
            email=data.email,
            password_hash=hash_password(data.password),
            is_disabled=False,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(user)
        reloaded = await self.crud.get_by_id(user.id)
        assert reloaded is not None
        return self._to_me(reloaded)

    async def login(self, data: PortalLoginRequest, response: Response) -> PortalLoginResponse:
        user = await self.crud.get_by_email(data.email.strip().lower())
        if user is None or not verify_password(data.password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")
        if user.is_disabled:
            raise UnauthorizedError("Invalid email or password")
        if user.customer.customer_type != "trade":
            raise UnauthorizedError("Invalid email or password")
        team_settings = await TeamSettingsCRUD(self.db).get_or_create_for_team(
            await self._team_id()
        )
        ttl_hours = int(team_settings.session_ttl_hours)
        ctx = tenant_ctx.get()
        if ctx is None:
            raise UnauthorizedError("Invalid session")
        token = create_customer_access_token(user.id, ttl_hours, ctx.id)
        set_customer_session_cookie(response, token, max_age=ttl_hours * 3600)
        return PortalLoginResponse(email=user.email, customer_name=user.customer.name)

    async def logout(self, response: Response) -> None:
        clear_customer_session_cookie(response)

    async def me(self, portal_user_id: uuid.UUID) -> PortalMeResponse:
        user = await self._require_user(portal_user_id)
        return self._to_me(user)

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
        return [self.orders._to_response(row) for row in rows]

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
