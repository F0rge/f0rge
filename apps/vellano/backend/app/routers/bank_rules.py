from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_bank_rule_service,
    get_current_user_id,
    require_books_mutate,
)
from app.schemas.bank_rule import BankRuleCreate, BankRuleResponse, BankRuleUpdate
from app.services.bank_rules import BankRuleService

bank_rules_router = APIRouter(prefix="/api/v1/bank-rules", tags=["bank-rules"])


@bank_rules_router.get("", response_model=list[BankRuleResponse])
async def list_bank_rules(
    bank_account_id: Optional[uuid.UUID] = None,
    _: uuid.UUID = Depends(get_current_user_id),
    service: BankRuleService = Depends(get_bank_rule_service),
):
    return await service.list(bank_account_id)


@bank_rules_router.post("", response_model=BankRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_bank_rule(
    body: BankRuleCreate,
    _: uuid.UUID = Depends(require_books_mutate),
    service: BankRuleService = Depends(get_bank_rule_service),
):
    return await service.create(body)


@bank_rules_router.patch("/{rule_id}", response_model=BankRuleResponse)
async def update_bank_rule(
    rule_id: uuid.UUID,
    body: BankRuleUpdate,
    _: uuid.UUID = Depends(require_books_mutate),
    service: BankRuleService = Depends(get_bank_rule_service),
):
    return await service.update(rule_id, body)


@bank_rules_router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bank_rule(
    rule_id: uuid.UUID,
    _: uuid.UUID = Depends(require_books_mutate),
    service: BankRuleService = Depends(get_bank_rule_service),
):
    return await service.delete(rule_id)
