from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_contact_service,
    get_current_user_id,
    require_books_mutate,
)
from app.schemas.contact import ContactCreate, ContactResponse
from app.services.contacts import ContactService

contacts_router = APIRouter(prefix="/api/v1/contacts", tags=["contacts"])


@contacts_router.get("", response_model=list[ContactResponse])
async def list_contacts(
    _: uuid.UUID = Depends(get_current_user_id),
    service: ContactService = Depends(get_contact_service),
):
    return await service.list()


@contacts_router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    body: ContactCreate,
    _: uuid.UUID = Depends(require_books_mutate),
    service: ContactService = Depends(get_contact_service),
):
    return await service.create_customer(body)
