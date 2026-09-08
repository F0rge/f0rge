from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.account import AccountCRUD
from app.models.account import Account, AccountType, default_tax_treatment
from app.schemas.account import AccountCreate, AccountResponse, AccountUpdate
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class AccountService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = AccountCRUD(db)

    async def list(self) -> list[AccountResponse]:
        accounts = await self.crud.list_all()
        balances = await self.crud.get_balances()
        return [
            self._to_response(account, balances.get(account.id, Decimal(0))) for account in accounts
        ]

    async def create(self, data: AccountCreate) -> AccountResponse:
        existing = await self.crud.get_by_code(data.code)
        if existing is not None:
            raise ConflictError("An account with this code already exists")

        tax_treatment = data.tax_treatment
        if tax_treatment is None:
            tax_treatment = default_tax_treatment(data.type)
        self._require_bank_flag_allowed(data.type, data.is_bank)
        account = Account(
            code=data.code,
            name=data.name,
            type=data.type,
            is_system=False,
            is_bank=data.is_bank,
            tax_treatment=tax_treatment,
        )
        async with unit_of_work(self.db):
            await self.crud.add_and_flush(account)
            try:
                await self.crud.commit_refresh(account)
            except IntegrityError as exc:
                raise ConflictError("An account with this code already exists") from exc

        return self._to_response(account, Decimal(0))

    async def update(self, account_id: uuid.UUID, data: AccountUpdate) -> AccountResponse:
        account = await self.crud.get_by_id(account_id)
        if account is None:
            raise NotFoundError("Account not found")

        if data.name is not None:
            account.name = data.name
        if data.is_archived is not None:
            account.is_archived = data.is_archived
        if data.tax_treatment is not None:
            account.tax_treatment = data.tax_treatment
        if data.is_bank is not None:
            self._require_bank_flag_allowed(account.type, data.is_bank)
            account.is_bank = data.is_bank

        await self.crud.commit_refresh(account)
        balances = await self.crud.get_balances()
        return self._to_response(account, balances.get(account.id, Decimal(0)))

    @staticmethod
    def _to_response(account: Account, balance_zar: Decimal) -> AccountResponse:
        return AccountResponse(
            id=account.id,
            code=account.code,
            name=account.name,
            type=account.type,
            is_system=account.is_system,
            is_archived=account.is_archived,
            is_bank=account.is_bank,
            tax_treatment=account.tax_treatment,
            balance_zar=balance_zar,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )

    @staticmethod
    def _require_bank_flag_allowed(account_type: AccountType, is_bank: bool) -> None:
        if is_bank and account_type != AccountType.ASSET:
            raise ValidationError("Only asset accounts can be bank reconciliation targets")
