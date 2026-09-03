"""Playground seed tests."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.location import LocationCRUD
from app.crud.purchase_order import LocationStockCRUD
from app.crud.sku import SkuCRUD
from app.crud.supplier import SupplierCRUD
from app.crud.customer import CustomerCRUD
from app.crud.layby import LaybyCRUD
from app.services.playground_seed import (
    CHAIR_SKU_REF,
    MARKER_SKU_REF,
    PACK_MARKER_REF,
    PLAYGROUND_SUPPLIER_NAME,
    PROFORMA_INVOICE_NUMBER,
    SOFA_PACK_MARKER_REF,
    PlaygroundSeedService,
)
from app.services.playground_bi_catalog import (
    BI_CUSTOMERS,
    BI_MARKER_REF,
    BI_SKUS,
    BI_SUPPLIERS,
)
from app.services.proformas import ProformaService


@pytest.fixture
def enable_playground_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.playground_seed.settings.seed_playground", True)


async def test_playground_seed_creates_demo_path_and_is_idempotent(
    async_db: AsyncSession,
    enable_playground_seed: None,
) -> None:
    service = PlaygroundSeedService(async_db)
    supplier_crud = SupplierCRUD(async_db)
    sku_crud = SkuCRUD(async_db)
    location_crud = LocationCRUD(async_db)
    location_stock_crud = LocationStockCRUD(async_db)

    await service.seed_if_enabled()

    suppliers = await supplier_crud.list_all()
    playground_suppliers = [s for s in suppliers if s.name == PLAYGROUND_SUPPLIER_NAME]
    assert len(playground_suppliers) == 1

    table_sku = await sku_crud.get_by_our_ref(MARKER_SKU_REF)
    chair_sku = await sku_crud.get_by_our_ref(CHAIR_SKU_REF)
    assert table_sku is not None
    assert chair_sku is not None

    proformas = await ProformaService(async_db).list()
    playground_proformas = [p for p in proformas if p.invoice_number == PROFORMA_INVOICE_NUMBER]
    assert len(playground_proformas) == 1

    kramerville = await location_crud.get_active_by_name_insensitive("Kramerville")
    bedfordview = await location_crud.get_active_by_name_insensitive("Bedfordview")
    assert kramerville is not None
    assert bedfordview is not None

    kramerville_table = await location_stock_crud.get_by_sku_and_location(
        table_sku.id,
        kramerville.id,
    )
    kramerville_chair = await location_stock_crud.get_by_sku_and_location(
        chair_sku.id,
        kramerville.id,
    )
    bedfordview_table = await location_stock_crud.get_by_sku_and_location(
        table_sku.id,
        bedfordview.id,
    )

    assert kramerville_table is not None
    assert kramerville_table.on_hand == 1
    assert kramerville_chair is not None
    assert kramerville_chair.on_hand == 2
    assert bedfordview_table is not None
    assert bedfordview_table.on_hand == 0

    sofa = await sku_crud.get_by_our_ref(PACK_MARKER_REF)
    assert sofa is not None
    assert sofa.category == "Seating"
    laybys = await LaybyCRUD(async_db).list_all()
    assert len(laybys) >= 4

    london = await sku_crud.get_by_our_ref(SOFA_PACK_MARKER_REF)
    assert london is not None
    assert london.photo_storage_key
    assert london.category == "Seating"

    vel_sofas = [s for s in await sku_crud.list_all() if s.our_ref.startswith("VEL-SOFA-")]
    assert len(vel_sofas) >= 10

    bi_marker = await sku_crud.get_by_our_ref(BI_MARKER_REF)
    assert bi_marker is not None
    assert bi_marker.photo_storage_key
    bi_skus = [s for s in await sku_crud.list_all() if s.our_ref.startswith("VEL-BI-")]
    assert len(bi_skus) == len(BI_SKUS)
    assert len(bi_skus) >= 80
    suppliers_all = await supplier_crud.list_all()
    assert len(suppliers_all) >= len(BI_SUPPLIERS)
    customers_all = await CustomerCRUD(async_db).list_all()
    assert len(customers_all) >= len(BI_CUSTOMERS)
    laybys_all = await LaybyCRUD(async_db).list_all()
    assert len(laybys_all) >= 10

    first_london_id = london.id
    first_vel_sofa_count = len(vel_sofas)
    first_bi_id = bi_marker.id
    first_bi_count = len(bi_skus)

    first_supplier_id = playground_suppliers[0].id
    first_table_id = table_sku.id
    first_proforma_id = playground_proformas[0].id

    await service.seed_if_enabled()

    suppliers_after = await supplier_crud.list_all()
    playground_suppliers_after = [s for s in suppliers_after if s.name == PLAYGROUND_SUPPLIER_NAME]
    assert len(playground_suppliers_after) == 1
    assert playground_suppliers_after[0].id == first_supplier_id

    table_after = await sku_crud.get_by_our_ref(MARKER_SKU_REF)
    assert table_after is not None
    assert table_after.id == first_table_id

    proformas_after = await ProformaService(async_db).list()
    playground_proformas_after = [
        p for p in proformas_after if p.invoice_number == PROFORMA_INVOICE_NUMBER
    ]
    assert len(playground_proformas_after) == 1
    assert playground_proformas_after[0].id == first_proforma_id

    london_after = await sku_crud.get_by_our_ref(SOFA_PACK_MARKER_REF)
    assert london_after is not None
    assert london_after.id == first_london_id
    vel_sofas_after = [s for s in await sku_crud.list_all() if s.our_ref.startswith("VEL-SOFA-")]
    assert len(vel_sofas_after) == first_vel_sofa_count

    bi_after = await sku_crud.get_by_our_ref(BI_MARKER_REF)
    assert bi_after is not None
    assert bi_after.id == first_bi_id
    bi_skus_after = [s for s in await sku_crud.list_all() if s.our_ref.startswith("VEL-BI-")]
    assert len(bi_skus_after) == first_bi_count
