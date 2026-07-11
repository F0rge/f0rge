from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.onboarding_setup import OnboardingSetupService


def get_onboarding_setup_service(db: AsyncSession = Depends(get_db)) -> OnboardingSetupService:
    return OnboardingSetupService(db)
