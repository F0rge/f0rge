from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.account import AccountCRUD
from app.crud.bank_rule import BankRuleCRUD
from app.models.account import Account
from app.models.bank_rule import BankRule
from app.schemas.bank_rule import BankRuleCreate, BankRuleResponse, BankRuleUpdate
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError
from f0rge_db.crud import unit_of_work


class BankRuleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = BankRuleCRUD(db)
        self.account_crud = AccountCRUD(db)

    async def list(self, bank_account_id: Optional[uuid.UUID] = None) -> list[BankRuleResponse]:
        return [self._to_response(rule) for rule in await self.crud.list_all(bank_account_id)]

    async def create(self, data: BankRuleCreate) -> BankRuleResponse:
        pattern = self._normalized_pattern(data.pattern)
        await self._require_bank_account(data.bank_account_id)
        await self._require_target_account(data.target_account_id, data.bank_account_id)
        await self._require_unique_pattern(data.bank_account_id, pattern)
        rule = BankRule(
            bank_account_id=data.bank_account_id,
            pattern=pattern,
            target_account_id=data.target_account_id,
        )
        try:
            async with unit_of_work(self.db):
                await self.crud.add_and_flush(rule)
        except IntegrityError as exc:
            raise ConflictError("A bank rule with this pattern already exists") from exc
        return self._to_response(await self._get_or_404(rule.id))

    async def update(self, rule_id: uuid.UUID, data: BankRuleUpdate) -> BankRuleResponse:
        rule = await self._get_or_404(rule_id)
        if data.pattern is not None:
            pattern = self._normalized_pattern(data.pattern)
            await self._require_unique_pattern(rule.bank_account_id, pattern, exclude_id=rule.id)
            rule.pattern = pattern
        if data.target_account_id is not None:
            await self._require_target_account(data.target_account_id, rule.bank_account_id)
            rule.target_account_id = data.target_account_id
        if data.is_active is not None:
            rule.is_active = data.is_active
        try:
            await self.crud.commit_refresh(rule)
        except IntegrityError as exc:
            raise ConflictError("A bank rule with this pattern already exists") from exc
        return self._to_response(await self._get_or_404(rule.id))

    async def delete(self, rule_id: uuid.UUID) -> None:
        rule = await self._get_or_404(rule_id)
        await self.crud.delete_and_commit(rule)

    async def _get_or_404(self, rule_id: uuid.UUID) -> BankRule:
        rule = await self.crud.get_by_id(rule_id)
        if rule is None:
            raise NotFoundError("Bank rule not found")
        return rule

    async def _require_bank_account(self, account_id: uuid.UUID) -> Account:
        account = await self.account_crud.get_by_id(account_id)
        if account is None:
            raise NotFoundError("Account not found")
        if not account.is_bank:
            raise ValidationError("Account is not a bank reconciliation target")
        return account

    async def _require_target_account(
        self, account_id: uuid.UUID, bank_account_id: uuid.UUID
    ) -> Account:
        account = await self.account_crud.get_by_id(account_id)
        if account is None:
            raise NotFoundError("Account not found")
        if account.id == bank_account_id:
            raise ValidationError("Target account cannot be the bank account")
        return account

    async def _require_unique_pattern(
        self,
        bank_account_id: uuid.UUID,
        pattern: str,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> None:
        existing = await self.crud.get_by_account_pattern(
            bank_account_id, pattern, exclude_id=exclude_id
        )
        if existing is not None:
            raise ConflictError("A bank rule with this pattern already exists")

    @staticmethod
    def _normalized_pattern(pattern: str) -> str:
        stripped = pattern.strip()
        if not stripped:
            raise ValidationError("Pattern is required")
        return stripped

    @staticmethod
    def _to_response(rule: BankRule) -> BankRuleResponse:
        return BankRuleResponse(
            id=rule.id,
            bank_account_id=rule.bank_account_id,
            pattern=rule.pattern,
            target_account_id=rule.target_account_id,
            is_active=rule.is_active,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )
