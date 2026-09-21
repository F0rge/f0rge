from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import (
    get_current_user_id,
    get_location_bin_service,
    get_location_service,
    require_location_mutate,
)
from app.schemas.location import LocationCreate, LocationResponse, LocationUpdate
from app.schemas.location_bin import (
    BinCreate,
    BinGridCreate,
    BinUpdate,
    LocationBinResponse,
)
from app.services.location_bins import LocationBinService
from app.services.locations import LocationService

locations_router = APIRouter(prefix="/api/v1/locations", tags=["locations"])


@locations_router.get("", response_model=list[LocationResponse])
async def list_locations(
    _: uuid.UUID = Depends(get_current_user_id),
    service: LocationService = Depends(get_location_service),
):
    return await service.list()


@locations_router.post("", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    body: LocationCreate,
    _: uuid.UUID = Depends(require_location_mutate),
    service: LocationService = Depends(get_location_service),
):
    return await service.create(body)


@locations_router.patch("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: uuid.UUID,
    body: LocationUpdate,
    _: uuid.UUID = Depends(require_location_mutate),
    service: LocationService = Depends(get_location_service),
):
    return await service.update(location_id, body)


@locations_router.get("/{location_id}/bins", response_model=list[LocationBinResponse])
async def list_location_bins(
    location_id: uuid.UUID,
    _: uuid.UUID = Depends(get_current_user_id),
    service: LocationBinService = Depends(get_location_bin_service),
):
    return await service.list(location_id)


@locations_router.post(
    "/{location_id}/bins",
    response_model=LocationBinResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_location_bin(
    location_id: uuid.UUID,
    body: BinCreate,
    _: uuid.UUID = Depends(require_location_mutate),
    service: LocationBinService = Depends(get_location_bin_service),
):
    return await service.create(location_id, body)


@locations_router.post(
    "/{location_id}/bins/grid",
    response_model=list[LocationBinResponse],
)
async def generate_location_bin_grid(
    location_id: uuid.UUID,
    body: BinGridCreate,
    _: uuid.UUID = Depends(require_location_mutate),
    service: LocationBinService = Depends(get_location_bin_service),
):
    return await service.generate_grid(location_id, body)


@locations_router.patch(
    "/{location_id}/bins/{bin_id}",
    response_model=LocationBinResponse,
)
async def update_location_bin(
    location_id: uuid.UUID,
    bin_id: uuid.UUID,
    body: BinUpdate,
    _: uuid.UUID = Depends(require_location_mutate),
    service: LocationBinService = Depends(get_location_bin_service),
):
    return await service.update(location_id, bin_id, body)
