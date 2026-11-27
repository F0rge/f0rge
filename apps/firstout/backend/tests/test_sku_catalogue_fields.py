"""SKU categories, materials, colour name, finish label and selling/reorder rules,
on every path that writes a SKU."""

from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.catalogue_list import SkuCategory
from app.models.team import Team
from app.services.curated_catalogue import CuratedCatalogueService
from app.services.curated_catalogue_archive import read_catalogue_archive
from f0rge_core.exceptions import ValidationError
from tests.catalogue_lists import ensure_category, ensure_material
from tests.conftest import OWNER_EMAIL, authenticate_as
from tests.test_curated_catalogue import _bundle, _jpeg
from tests.test_po_pending_lines import _po
from tests.test_purchase_orders import _create_supplier

SKUS = "/api/v1/skus"


def _payload(ref: str, **extra: object) -> dict:
    return {"our_ref": ref, "name": f"Item {ref}", "design": f"Design {ref}", **extra}


def _errors(response) -> dict[str, str]:
    assert response.status_code == 422, response.text
    return {".".join(str(p) for p in e["loc"][1:]): e["msg"] for e in response.json()["detail"]}


async def _create(client: AsyncClient, ref: str, **extra: object) -> dict:
    response = await client.post(SKUS, json=_payload(ref, **extra))
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
async def lists(owner_client: AsyncClient) -> dict:
    sofas = await ensure_category(owner_client, "Sofas")
    dining = await ensure_category(owner_client, "Dining room")
    corner = await ensure_category(owner_client, "Corner sofas", parent_id=sofas.id)
    chairs = await ensure_category(owner_client, "Chairs", parent_id=dining.id)
    return {
        "sofas": sofas,
        "dining": dining,
        "corner": corner,
        "chairs": chairs,
        "boucle": await ensure_material(owner_client, "Bouclé", "fabric"),
        "oak": await ensure_material(owner_client, "Oak", "wood"),
        "brass": await ensure_material(owner_client, "Brass", "metal"),
    }


async def test_create_with_lists_returns_names_and_derived_label(owner_client, lists) -> None:
    body = await _create(
        owner_client,
        "CF-1",
        category_id=str(lists["sofas"].id),
        subcategory_id=str(lists["corner"].id),
        colour_name="  Oat ",
        main_material_id=str(lists["boucle"].id),
        other_material_ids=[str(lists["oak"].id), str(lists["brass"].id)],
        sell_multiple=2,
        reorder_min=2,
        order_up_to=6,
        do_not_reorder=True,
    )
    assert body["category"] == "Sofas"
    assert body["category_id"] == str(lists["sofas"].id)
    assert body["subcategory"] == "Corner sofas"
    assert body["colour_name"] == "Oat"
    assert body["main_material"] == {
        "id": str(lists["boucle"].id),
        "name": "Bouclé",
        "family": "fabric",
        "is_archived": False,
    }
    assert [m["name"] for m in body["other_materials"]] == ["Oak", "Brass"]
    assert body["other_material_ids"] == [str(lists["oak"].id), str(lists["brass"].id)]
    assert body["fabric"] == "Oat Bouclé"
    # The minimum follows the multiple when not sent.
    assert (body["sell_multiple"], body["min_sell_qty"]) == (2, 2)
    assert (body["reorder_min"], body["order_up_to"], body["do_not_reorder"]) == (2, 6, True)

    # Reordering other materials replaces the list in place (no unique-key clash).
    patched = await owner_client.patch(
        f"{SKUS}/{body['id']}",
        json={"other_material_ids": [str(lists["brass"].id), str(lists["oak"].id)]},
    )
    assert patched.status_code == 200, patched.text
    assert [m["name"] for m in patched.json()["other_materials"]] == ["Brass", "Oak"]


async def test_create_without_finish_inputs_stores_placeholder(owner_client, lists) -> None:
    assert (await _create(owner_client, "CF-PLAIN"))["fabric"] == "-"
    legacy = await _create(owner_client, "CF-LEGACY", fabric="Walnut veneer")
    assert legacy["fabric"] == "Walnut veneer"
    derived = await _create(
        owner_client, "CF-WINS", fabric="Ignored", main_material_id=str(lists["oak"].id)
    )
    assert derived["fabric"] == "Oak"


async def test_finish_label_on_update(owner_client, lists) -> None:
    sku = await _create(owner_client, "CF-UPD", fabric="Old label")
    url = f"{SKUS}/{sku['id']}"
    only_fabric = await owner_client.patch(url, json={"fabric": "Newer label"})
    assert only_fabric.json()["fabric"] == "Newer label"
    coloured = await owner_client.patch(url, json={"colour_name": "Sage"})
    assert coloured.json()["fabric"] == "Sage"
    material = await owner_client.patch(url, json={"main_material_id": str(lists["oak"].id)})
    assert material.json()["fabric"] == "Sage Oak"
    # A stored colour or material wins over a sent fabric.
    ignored = await owner_client.patch(url, json={"fabric": "Typed"})
    assert ignored.json()["fabric"] == "Sage Oak"
    cleared = await owner_client.patch(url, json={"colour_name": "", "main_material_id": None})
    assert cleared.status_code == 200
    assert cleared.json()["colour_name"] is None
    assert cleared.json()["fabric"] == "-"


async def test_duplicate_design_colour_material_conflict(owner_client, lists) -> None:
    first = dict(design="Arc", colour_name="Oat", main_material_id=str(lists["boucle"].id))
    await _create(owner_client, "CF-DUP-1", **first)
    clash = await owner_client.post(SKUS, json={**_payload("CF-DUP-2"), **first})
    assert clash.status_code == 409
    assert clash.json()["detail"] == "Another SKU already has this design, colour and material."
    other = await _create(owner_client, "CF-DUP-3", design="Arc", colour_name="Sand")
    patched = await owner_client.patch(
        f"{SKUS}/{other['id']}",
        json={"colour_name": "oat", "main_material_id": str(lists["boucle"].id)},
    )
    assert patched.status_code == 409
    assert patched.json()["detail"] == "Another SKU already has this design, colour and material."


async def test_category_rules_name_their_field(owner_client, lists) -> None:
    sku = await _create(
        owner_client,
        "CF-CAT",
        category_id=str(lists["sofas"].id),
        subcategory_id=str(lists["corner"].id),
    )
    url = f"{SKUS}/{sku['id']}"
    wrong_parent = await owner_client.patch(url, json={"subcategory_id": str(lists["chairs"].id)})
    assert "subcategory_id" in _errors(wrong_parent)
    sub_as_category = await owner_client.patch(url, json={"category_id": str(lists["corner"].id)})
    assert "category_id" in _errors(sub_as_category)
    missing = await owner_client.patch(url, json={"category_id": str(uuid.uuid4())})
    assert _errors(missing) == {"category_id": "Category not found"}

    # Changing category clears a sub-category that no longer fits, and syncs the name.
    moved = await owner_client.patch(url, json={"category_id": str(lists["dining"].id)})
    assert moved.status_code == 200, moved.text
    assert (moved.json()["category"], moved.json()["subcategory_id"]) == ("Dining room", None)
    both = await owner_client.patch(
        url,
        json={"category_id": str(lists["sofas"].id), "subcategory_id": str(lists["corner"].id)},
    )
    assert (both.json()["category"], both.json()["subcategory"]) == ("Sofas", "Corner sofas")
    cleared = await owner_client.patch(url, json={"category_id": None})
    assert cleared.status_code == 200, cleared.text
    assert (cleared.json()["category"], cleared.json()["subcategory_id"]) == (None, None)


async def test_archived_lists_cannot_be_newly_assigned_but_stay(owner_client, lists) -> None:
    sku = await _create(
        owner_client,
        "CF-ARCH",
        category_id=str(lists["sofas"].id),
        main_material_id=str(lists["oak"].id),
    )
    old_category = await ensure_category(owner_client, "Retired", archived=True)
    old_material = await ensure_material(owner_client, "Cane", "woven", archived=True)
    url = f"{SKUS}/{sku['id']}"
    refused = await owner_client.patch(
        url,
        json={
            "category_id": str(old_category.id),
            "main_material_id": str(old_material.id),
            "other_material_ids": [str(old_material.id)],
        },
    )
    assert set(_errors(refused)) == {"category_id", "main_material_id", "other_material_ids"}

    # Archived after assignment: the SKU keeps them and other edits still save.
    lists["sofas"].is_archived = True
    lists["oak"].is_archived = True
    await owner_client.test_db.flush()
    kept = await owner_client.patch(url, json={"name": "Still editable", "colour_name": "Ink"})
    assert kept.status_code == 200, kept.text
    assert kept.json()["category"] == "Sofas"
    assert kept.json()["main_material"]["is_archived"] is True
    assert kept.json()["fabric"] == "Ink Oak"


async def test_material_rules(owner_client, lists) -> None:
    oak, brass = str(lists["oak"].id), str(lists["brass"].id)
    twice = await owner_client.post(SKUS, json=_payload("CF-M1", other_material_ids=[oak, oak]))
    assert "other_material_ids" in _errors(twice)
    both = await owner_client.post(
        SKUS, json=_payload("CF-M2", main_material_id=oak, other_material_ids=[oak, brass])
    )
    assert "other_material_ids" in _errors(both)
    sku = await _create(owner_client, "CF-M3", other_material_ids=[oak])
    promote = await owner_client.patch(f"{SKUS}/{sku['id']}", json={"main_material_id": oak})
    assert "main_material_id" in _errors(promote)
    unknown = await owner_client.post(
        SKUS, json=_payload("CF-M4", main_material_id=str(uuid.uuid4()))
    )
    assert _errors(unknown) == {"main_material_id": "Material not found"}


async def test_selling_and_reorder_rules(owner_client, lists) -> None:
    off_multiple = await owner_client.post(
        SKUS, json=_payload("CF-S1", sell_multiple=2, min_sell_qty=3)
    )
    assert _errors(off_multiple) == {"min_sell_qty": "Minimum quantity must be a multiple of 2"}
    zero = await owner_client.post(SKUS, json=_payload("CF-S2", min_sell_qty=0))
    assert "min_sell_qty" in _errors(zero)

    sku = await _create(owner_client, "CF-S3", sell_multiple=2, min_sell_qty=6)
    url = f"{SKUS}/{sku['id']}"
    # Only the multiple changes: the stored minimum rises to the next valid multiple.
    raised = await owner_client.patch(url, json={"sell_multiple": 4})
    assert (raised.json()["sell_multiple"], raised.json()["min_sell_qty"]) == (4, 8)
    kept = await owner_client.patch(url, json={"sell_multiple": 2})
    assert kept.json()["min_sell_qty"] == 8
    bad = await owner_client.patch(url, json={"min_sell_qty": 5})
    assert "min_sell_qty" in _errors(bad)
    null_multiple = await owner_client.patch(url, json={"sell_multiple": None})
    assert "sell_multiple" in _errors(null_multiple)

    low = await owner_client.patch(url, json={"reorder_min": 5, "order_up_to": 4})
    assert "order_up_to" in _errors(low)
    ok = await owner_client.patch(url, json={"reorder_min": 5, "order_up_to": 9})
    assert ok.status_code == 200
    above = await owner_client.patch(url, json={"reorder_min": 10})
    assert "reorder_min" in _errors(above)
    sellable = await owner_client.patch(url, json={"is_sellable": False, "do_not_reorder": True})
    assert (sellable.json()["is_sellable"], sellable.json()["do_not_reorder"]) == (False, True)


async def test_legacy_category_name_input(owner_client, lists) -> None:
    resolved = await _create(owner_client, "CF-L1", category="  sofas ")
    assert (resolved["category"], resolved["category_id"]) == ("Sofas", str(lists["sofas"].id))
    unknown = await owner_client.post(SKUS, json=_payload("CF-L2", category="Lamps"))
    assert _errors(unknown) == {"category": "Unknown category 'Lamps'. Add it in Settings first."}
    disagree = await owner_client.post(
        SKUS, json=_payload("CF-L3", category="Sofas", category_id=str(lists["dining"].id))
    )
    assert "category" in _errors(disagree)
    agree = await _create(
        owner_client, "CF-L4", category="Sofas", category_id=str(lists["sofas"].id)
    )
    assert agree["category_id"] == str(lists["sofas"].id)
    count = await owner_client.test_db.scalar(
        select(func.count()).select_from(SkuCategory).where(func.lower(SkuCategory.name) == "lamps")
    )
    assert count == 0


async def test_archived_sku_new_fields_stay_locked(owner_client, lists) -> None:
    sku = await _create(owner_client, "CF-ARCHIVED")
    from app.models.sku import Sku

    row = await owner_client.test_db.get(Sku, uuid.UUID(sku["id"]))
    row.is_archived = True
    await owner_client.test_db.flush()
    for change in (
        {"category_id": str(lists["sofas"].id)},
        {"sell_multiple": 2},
        {"other_material_ids": [str(lists["oak"].id)]},
    ):
        refused = await owner_client.patch(f"{SKUS}/{sku['id']}", json=change)
        assert refused.status_code == 409
    prices = await owner_client.put(f"{SKUS}/{sku['id']}/supplier-prices", json={"rows": []})
    assert prices.status_code == 409


async def test_writes_need_catalogue_mutate(async_client, owner_client, lists) -> None:
    sku = await _create(owner_client, "CF-PERM")
    await authenticate_as(async_client, "warehouse@example.com")
    denied = await async_client.patch(f"{SKUS}/{sku['id']}", json={"sell_multiple": 2})
    assert denied.status_code == 403
    created = await async_client.post(SKUS, json=_payload("CF-PERM-2"))
    assert created.status_code == 403
    async_client.cookies.clear()
    async_client.headers.pop("Authorization", None)
    anonymous = await async_client.patch(f"{SKUS}/{sku['id']}", json={"sell_multiple": 2})
    assert anonymous.status_code == 401
    await authenticate_as(async_client, OWNER_EMAIL)


# CSV import ----------------------------------------------------------------------------


async def _import(client: AsyncClient, csv_text: str, step: str):
    return await client.post(
        f"/api/v1/imports/{step}",
        files={"inventory": ("inventory.csv", io.BytesIO(csv_text.encode()), "text/csv")},
    )


async def test_csv_import_resolves_and_refuses_categories(owner_client, lists) -> None:
    long_name = "x" * 65
    bad = (
        "SKU,Name,Category,Sub category,Retail Price\n"
        "CSV-CF-1,Known,sofas,corner SOFAS,115.00\n"
        "CSV-CF-2,Unknown,Lamps,,115.00\n"
        f"CSV-CF-3,Long,{long_name},,115.00\n"
        "CSV-CF-4,Wrong sub,Sofas,Chairs,115.00\n"
    )
    preview = await _import(owner_client, bad, "preview")
    assert preview.status_code == 200
    messages = {(e["row"], e["message"]) for e in preview.json()["errors"]}
    assert (3, "Unknown category 'Lamps'. Add it in Settings first.") in messages
    assert (4, "Category must be 64 characters or fewer") in messages
    assert (5, "Unknown sub-category 'Chairs'. Add it in Settings first.") in messages
    assert not any(row == 2 for row, _ in messages)
    commit = await _import(owner_client, bad, "commit")
    assert commit.status_code == 400
    # Preview and commit agree: the commit refuses with the first preview error.
    assert commit.json()["detail"] == preview.json()["errors"][0]["message"]

    good = "SKU,Name,Category,Sub category,Retail Price\nCSV-CF-1,Known,sofas,corner SOFAS,115.00\n"
    assert (await _import(owner_client, good, "commit")).status_code == 200
    found = (await owner_client.get(SKUS, params={"q": "CSV-CF-1"})).json()[0]
    assert (found["category"], found["subcategory"]) == ("Sofas", "Corner sofas")
    assert found["category_id"] == str(lists["sofas"].id)

    # Without the column a sub-category that still fits stays; a new category clears it.
    same = "SKU,Name,Category,Retail Price\nCSV-CF-1,Known,Sofas,115.00\n"
    assert (await _import(owner_client, same, "commit")).status_code == 200
    kept = (await owner_client.get(f"{SKUS}/{found['id']}")).json()
    assert kept["subcategory"] == "Corner sofas"
    moved = "SKU,Name,Category,Retail Price\nCSV-CF-1,Known,Dining room,115.00\n"
    assert (await _import(owner_client, moved, "commit")).status_code == 200
    after = (await owner_client.get(f"{SKUS}/{found['id']}")).json()
    assert (after["category"], after["subcategory_id"]) == ("Dining room", None)


# Purchase order create-SKU, intake, curated import ------------------------------------


async def test_po_line_create_sku_uses_lists(owner_client, lists) -> None:
    supplier_id = await _create_supplier(owner_client, "CF Supplier")
    body = await _po(
        owner_client,
        supplier_id,
        [{"description": "Arc sofa", "supplier_code": "ARC", "qty": 1, "factory_unit_amount": "9"}],
    )
    url = f"/api/v1/purchase-orders/{body['id']}/lines/{body['lines'][0]['id']}/sku"
    base = {"our_ref": "CF-PO", "our_barcode": "CF-PO", "name": "Arc", "design": "Arc"}
    unknown = await owner_client.post(url, json={**base, "category": "Lamps"})
    assert _errors(unknown) == {"category": "Unknown category 'Lamps'. Add it in Settings first."}
    created = await owner_client.post(
        url,
        json={
            **base,
            "category_id": str(lists["sofas"].id),
            "colour_name": "Oat",
            "main_material_id": str(lists["boucle"].id),
        },
    )
    assert created.status_code == 200, created.text
    line = created.json()["lines"][0]
    assert line["fabric"] == "Oat Bouclé"
    sku = (await owner_client.get(f"{SKUS}/{line['sku_id']}")).json()
    assert (sku["category"], sku["colour_name"]) == ("Sofas", "Oat")


async def test_intake_category_hint_is_matched_never_created(owner_client, monkeypatch) -> None:
    await ensure_category(owner_client, "Cushions")

    async def hint(*_args, **_kwargs):
        return {"name": "Cushion", "design": "Square", "category": state["category"]}

    state = {"category": "cushions"}
    monkeypatch.setattr("app.services.document_intake.extract.suggest_sku_fields", hint)
    url = "/api/v1/document-intake/sku-suggestions"
    request = {"description": "Square cushion", "supplier_code": "SQ", "hint": "cushions"}
    matched = await owner_client.post(url, json=request)
    assert matched.status_code == 200, matched.text
    assert matched.json()["category"] == "Cushions"
    assert matched.json()["category_id"] is not None
    state["category"] = "Throws"
    unmatched = await owner_client.post(url, json=request)
    assert (unmatched.json()["category"], unmatched.json()["category_id"]) == (None, None)
    count = await owner_client.test_db.scalar(
        select(func.count())
        .select_from(SkuCategory)
        .where(func.lower(SkuCategory.name) == "throws")
    )
    assert count == 0


async def test_curated_import_reads_shop_section_from_category(owner_client, lists) -> None:
    # A name that SHOP_CATEGORIES does not know, but a row with a shop section, qualifies...
    lounge = await ensure_category(owner_client, "Lounge", shop_category="sofas-armchairs")
    on_shop = await _create(owner_client, "CF-SHOP-1", category_id=str(lounge.id))
    # ...and a name it does know, on a row without one, does not.
    lists["sofas"].shop_category = None
    await owner_client.test_db.flush()
    off_shop = await _create(owner_client, "CF-SHOP-2", category_id=str(lists["sofas"].id))
    db = owner_client.test_db
    team_id = await db.scalar(select(Team.id).limit(1))
    service = CuratedCatalogueService(db)

    def manifest(sku: dict):
        photos = (_jpeg(11), _jpeg(22), _jpeg(33))
        return read_catalogue_archive(io.BytesIO(_bundle((sku["id"], sku["our_ref"], photos))))

    accepted = await service._catalogue_skus(team_id, manifest(on_shop).manifest, scope="sku")
    assert uuid.UUID(on_shop["id"]) in accepted
    with pytest.raises(ValidationError, match="no storefront category"):
        await service._catalogue_skus(team_id, manifest(off_shop).manifest, scope="sku")


# Search ---------------------------------------------------------------------------------


async def test_search_hits_carry_selling_fields_and_escape_wildcards(owner_client, lists) -> None:
    sku = await _create(
        owner_client,
        "SRCH_100%",
        category_id=str(lists["sofas"].id),
        sell_multiple=2,
        min_sell_qty=4,
    )
    await owner_client.patch(f"{SKUS}/{sku['id']}", json={"retail_inc_vat": "115.00"})
    await _create(owner_client, "SRCHX1000")
    hits = (await owner_client.get("/api/v1/search", params={"q": "SRCH_100%"})).json()["skus"]
    assert [hit["our_ref"] for hit in hits] == ["SRCH_100%"]
    hit = hits[0]
    assert hit["category"] == "Sofas"
    assert (hit["has_photo"], hit["is_kit"], hit["available"]) == (False, False, 0)
    assert hit["retail_inc_vat"] == "115.00"
    assert (hit["sell_multiple"], hit["min_sell_qty"]) == (2, 4)
    # "_" is literal too: it must not match the X in SRCHX1000.
    underscore = (await owner_client.get("/api/v1/search", params={"q": "SRCH_1"})).json()
    assert [hit["our_ref"] for hit in underscore["skus"]] == ["SRCH_100%"]


@pytest.mark.no_db
def test_packing_sheet_labels_finish_and_hides_placeholder() -> None:
    from app.services.packing_sheet import build_packing_sheet_pdf
    from tests.test_po_supplier_document import _pdf_text

    text = _pdf_text(
        build_packing_sheet_pdf(
            "PO-0001",
            [
                ("REF-1", "BAR-1", "Arc sofa", "Oat Bouclé", 1, 1),
                ("REF-2", "BAR-2", "Plain stool", "-", 1, 1),
            ],
        )
    )
    assert "Finish: Oat Bouclé" in text
    assert "Fabric" not in text
    assert text.count("Finish:") == 1


# Finish label survives resends; startup category re-link; accent folding -----------------


async def test_resending_unchanged_colour_or_material_keeps_legacy_label(owner_client, lists):
    # A backfilled SKU whose label came from the old free-text fabric.
    sku = await _create(owner_client, "CF-KEEP", design="Arc", fabric="Oat Bouclé Special")
    await _create(owner_client, "CF-KEEP-DASH", design="Arc")  # already "-" for this design
    url = f"{SKUS}/{sku['id']}"
    for resend in (
        {"colour_name": None, "retail_inc_vat": "100.00"},
        {"main_material_id": None},
        {"colour_name": "", "main_material_id": None},
    ):
        kept = await owner_client.patch(url, json=resend)
        assert kept.status_code == 200, kept.text
        assert kept.json()["fabric"] == "Oat Bouclé Special"

    coloured = await owner_client.patch(url, json={"colour_name": "Oat"})
    assert coloured.json()["fabric"] == "Oat"
    same = await owner_client.patch(url, json={"colour_name": "Oat", "fabric": "Ignored"})
    assert same.json()["fabric"] == "Oat"  # unchanged value, and the derived label wins
    material = await owner_client.patch(url, json={"main_material_id": str(lists["boucle"].id)})
    assert material.json()["fabric"] == "Oat Bouclé"
    resent = await owner_client.patch(
        url, json={"colour_name": "Oat", "main_material_id": str(lists["boucle"].id)}
    )
    assert resent.json()["fabric"] == "Oat Bouclé"

    # The legacy rule still applies when fabric is sent to a SKU with neither set.
    legacy = await _create(owner_client, "CF-KEEP-LEGACY", fabric="Old")
    retyped = await owner_client.patch(
        f"{SKUS}/{legacy['id']}", json={"colour_name": None, "fabric": "Retyped"}
    )
    assert retyped.json()["fabric"] == "Retyped"


async def test_startup_relink_repairs_old_backend_category_writes(owner_client, lists) -> None:
    from app.models.sku import Sku
    from app.services.sku_classification import relink_sku_categories

    db = owner_client.test_db

    def old_style(ref: str, category, **extra) -> Sku:
        # What the previous backend writes: the text only.
        return Sku(
            our_ref=ref,
            our_barcode=ref,
            name=ref,
            design=ref,
            fabric="-",
            category=category,
            **extra,
        )

    unlinked = old_style("RL-1", " sofas ")
    moved = old_style(
        "RL-2", "Dining room", category_id=lists["sofas"].id, subcategory_id=lists["corner"].id
    )
    unknown = old_style("RL-3", "Lamps")
    cleared = old_style("RL-4", None, category_id=lists["sofas"].id)
    fine = old_style(
        "RL-5", "Sofas", category_id=lists["sofas"].id, subcategory_id=lists["corner"].id
    )
    other = Team(name="Relink other organisation", slug="relink-other-org")
    db.add(other)
    await db.flush()
    foreign = old_style("RL-FOREIGN", "Sofas", team_id=other.id)
    db.add_all([unlinked, moved, unknown, cleared, fine, foreign])
    await db.flush()

    assert await relink_sku_categories(db) == (3, 1)
    for row in (unlinked, moved, unknown, cleared, fine, foreign):
        await db.refresh(row)
    assert (unlinked.category_id, unlinked.category) == (lists["sofas"].id, "Sofas")
    assert (moved.category_id, moved.subcategory_id) == (lists["dining"].id, None)
    assert (unknown.category_id, unknown.category) == (None, "Lamps")
    assert (cleared.category_id, cleared.subcategory_id) == (None, None)
    assert (fine.category_id, fine.subcategory_id) == (lists["sofas"].id, lists["corner"].id)
    assert foreign.category_id is None
    # Idempotent: only the unknown name is reported again.
    assert await relink_sku_categories(db) == (0, 1)
    count = await db.scalar(
        select(func.count()).select_from(SkuCategory).where(func.lower(SkuCategory.name) == "lamps")
    )
    assert count == 0


async def test_category_names_match_without_accents(owner_client) -> None:
    decor = await ensure_category(owner_client, "Décor")
    sku = await _create(owner_client, "CF-ACCENT", category="decor")
    assert (sku["category"], sku["category_id"]) == ("Décor", str(decor.id))
    csv = "SKU,Name,Category,Retail Price\nCSV-ACCENT,Vase,DECOR,115.00\n"
    assert (await _import(owner_client, csv, "preview")).json()["errors"] == []
