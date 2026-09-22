"""Playground BI catalog invariants (no database)."""

from __future__ import annotations

from decimal import Decimal
import pytest

from app.services.playground_bi_catalog import (
    BI_CUSTOMERS,
    BI_MARKER_REF,
    BI_SKUS,
    BI_SUPPLIERS,
    EUR_SUPPLIER_KEYS,
    LOCAL_SUPPLIER_KEYS,
    lead_days_for,
    po_waves,
    pricing_for_role,
    qty_for_role,
    sku_barcode,
)
from app.services.playground_seed import PLAYGROUND_PHOTOS_DIR

pytestmark = pytest.mark.no_db


def test_bi_catalog_scale_and_uniqueness() -> None:
    assert BI_MARKER_REF == "VEL-BI-V1"
    assert 80 <= len(BI_SKUS) <= 120
    assert 8 <= len(BI_SUPPLIERS) <= 15
    assert 25 <= len(BI_CUSTOMERS) <= 40

    refs = [row["our_ref"] for row in BI_SKUS]
    barcodes = [sku_barcode(i) for i in range(1, len(BI_SKUS) + 1)]
    pairs = [(row["design"].lower(), row["fabric"].lower()) for row in BI_SKUS]
    assert BI_MARKER_REF in refs
    assert len(set(refs)) == len(refs)
    assert len(set(barcodes)) == len(barcodes)
    assert len(set(pairs)) == len(pairs)
    assert len({row["key"] for row in BI_SUPPLIERS}) == len(BI_SUPPLIERS)
    assert len({row["name"] for row in BI_CUSTOMERS}) == len(BI_CUSTOMERS)

    categories = {row["category"] for row in BI_SKUS}
    for required in ("Seating", "Dining", "Bedroom", "Outdoor", "Tables", "Decor"):
        assert required in categories

    supplier_keys = {row["key"] for row in BI_SUPPLIERS}
    for row in BI_SKUS:
        assert row["supplier_key"] in supplier_keys
        Decimal(row["retail_ex"])
        po_qty, transfer, sell = qty_for_role(row["role"])
        assert po_qty >= transfer >= sell
        assert po_qty >= 1
        first_wave_qty = po_waves(row["role"])[0][0]
        assert transfer <= first_wave_qty
        lead = lead_days_for(row["supplier_key"], row["category"])
        assert row["lead_days"] == lead
        if row["supplier_key"] in EUR_SUPPLIER_KEYS:
            assert 42 <= lead <= 98
        else:
            assert row["supplier_key"] in LOCAL_SUPPLIER_KEYS
            assert 10 <= lead <= 35


def test_bi_catalog_photos_exist_or_fallback_dir() -> None:
    assert PLAYGROUND_PHOTOS_DIR.is_dir()
    jpgs = list(PLAYGROUND_PHOTOS_DIR.glob("*.jpg"))
    assert len(jpgs) >= 40
    missing = [
        row["photo"] for row in BI_SKUS if not (PLAYGROUND_PHOTOS_DIR / row["photo"]).is_file()
    ]
    # Fallback in the pack reuses any jpg; catalog should mostly point at real files.
    assert len(missing) <= 5


def test_bi_pricing_markup_and_outliers() -> None:
    retail = Decimal("10000.00")
    wholesale, cost = pricing_for_role(retail, "fast")
    assert cost > 0
    assert Decimal("2.0") <= (retail / cost) <= Decimal("2.6")
    assert wholesale < retail

    cheap_wholesale, cheap_cost = pricing_for_role(retail, "cheap")
    assert retail / cheap_cost < Decimal("1.5")
    steep_wholesale, steep_cost = pricing_for_role(retail, "steep")
    assert retail / steep_cost > Decimal("3.5")
    dead_wholesale, _dead_cost = pricing_for_role(retail, "dead")
    assert dead_wholesale > wholesale


def test_bi_po_waves_respect_lead_and_qty() -> None:
    for role in ("fast", "dead", "overstock", "cheap", "steep", "normal"):
        po_qty, transfer, sell = qty_for_role(role)
        waves = po_waves(role)
        assert sum(qty for qty, _ago in waves) == po_qty
        assert waves[0][0] >= transfer
        for _qty, receive_ago in waves:
            assert receive_ago >= 14
