from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.hypotheses import HypothesisService
from app.services.n_of_1 import NOf1Service


def get_hypothesis_service(db: AsyncSession = Depends(get_db)) -> HypothesisService:
    return HypothesisService(db)


def get_n_of_1_service(db: AsyncSession = Depends(get_db)) -> NOf1Service:
    return NOf1Service(db)
