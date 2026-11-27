"""Managed catalogue lists: categories (with sub-categories) and materials."""

from __future__ import annotations

import typing
import uuid

import pytest
import sqlalchemy as sa
from httpx import AsyncClient

from app.models.catalogue_list import MATERIAL_FAMILIES, Material, SkuCategory, SkuMaterial
from app.models.category_account_map import CategoryAccountMap
from app.models.sku import Sku
from app.schemas.catalogue_list import MaterialFamily
from app.services.catalogue_lists import fold_name
from app.services.category_posting import CategoryPostingService
from tests.conftest import authenticate_as, create_test_staff


async def _category(client: AsyncClient, name: str, **fields) -> dict:
    resp = await client.post("/api/v1/categories", json={"name": name, **fields})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _material(client: AsyncClient, name: str, family: str = "fabric") -> dict:
    resp = await client.post("/api/v1/materials", json={"name": name, "family": family})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _sku(client: AsyncClient, ref: str, **fields) -> Sku:
    sku = Sku(
        our_ref=ref,
        our_barcode=ref,
        name=f"List test {ref}",
        design=f"Design {ref}",
        fabric="-",
        retail_ex_vat=100,
        **fields,
    )
    client.test_db.add(sku)
    await client.test_db.commit()  # survive a refused request's rollback
    return sku


async def _tree(client: AsyncClient, lifecycle: str = "active") -> dict:
    resp = await client.get("/api/v1/categories", params={"lifecycle": lifecycle})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _find(tree: dict, category_id: str) -> dict:
    for top in tree["categories"]:
        if top["id"] == category_id:
            return top
        for sub in top["subcategories"]:
            if sub["id"] == category_id:
                return sub
    raise AssertionError(f"{category_id} not in tree")


# --- Categories -------------------------------------------------------------------------


async def test_tree_shape_counts_accounts_and_shop_sections(owner_client: AsyncClient) -> None:
    # "Seating" is mapped by the seeded ledger map (sales 4010); "Lighting" is not.
    seating = await _category(owner_client, "Seating", shop_category="sofas-armchairs")
    lighting = await _category(owner_client, "Lighting")
    lounge = await _category(owner_client, "Lounge chairs", parent_id=seating["id"])
    await _sku(owner_client, "LIST-1", category="Seating", category_id=uuid.UUID(seating["id"]))
    await _sku(
        owner_client,
        "LIST-2",
        category="Seating",
        category_id=uuid.UUID(seating["id"]),
        subcategory_id=uuid.UUID(lounge["id"]),
    )
    await _sku(
        owner_client,
        "LIST-3",
        category="Seating",
        category_id=uuid.UUID(seating["id"]),
        is_archived=True,
    )

    tree = await _tree(owner_client)
    node = _find(tree, seating["id"])
    assert node["sku_count"] == 2  # the archived SKU is not counted
    assert node["parent_id"] is None
    assert node["shop_category"] == "sofas-armchairs"
    assert node["sales_account"]["code"] == "4010"
    assert node["sales_account"]["name"]
    assert [sub["name"] for sub in node["subcategories"]] == ["Lounge chairs"]
    sub = node["subcategories"][0]
    assert sub["sku_count"] == 1 and sub["parent_id"] == seating["id"]
    assert sub["shop_category"] is None and sub["subcategories"] == []
    assert sub["sales_account"] == node["sales_account"]  # a sub-category posts with its parent
    assert _find(tree, lighting["id"])["sales_account"] is None
    assert {section["slug"] for section in tree["shop_sections"]} == {
        "sofas-armchairs",
        "dining-room",
        "bedroom",
        "coffee-console-tables",
    }
    assert all(section["label"] for section in tree["shop_sections"])


async def test_create_sub_category_refusals(owner_client: AsyncClient) -> None:
    top = await _category(owner_client, "Tables")
    sub = await _category(owner_client, "Side tables", parent_id=top["id"])

    grandchild = await owner_client.post(
        "/api/v1/categories", json={"name": "Nested", "parent_id": sub["id"]}
    )
    assert grandchild.status_code == 409
    assert "sub-categories cannot have their own" in grandchild.json()["detail"]

    missing = await owner_client.post(
        "/api/v1/categories", json={"name": "Orphan", "parent_id": str(uuid.uuid4())}
    )
    assert missing.status_code == 404

    archived = await _category(owner_client, "Old range")
    await owner_client.patch(f"/api/v1/categories/{archived['id']}", json={"is_archived": True})
    under_archived = await owner_client.post(
        "/api/v1/categories", json={"name": "Child", "parent_id": archived["id"]}
    )
    assert under_archived.status_code == 409 and "archived" in under_archived.json()["detail"]


async def test_duplicate_names_are_case_and_accent_insensitive_per_level(
    owner_client: AsyncClient,
) -> None:
    top = await _category(owner_client, "Décor")
    for name in ("décor", "DECOR", " Decor "):
        dup = await owner_client.post("/api/v1/categories", json={"name": name})
        assert dup.status_code == 409, name
        assert "already called" in dup.json()["detail"]
    other = await _category(owner_client, "Lamps")
    # The same sub-category name may exist under two different categories, but not twice.
    await _category(owner_client, "Small", parent_id=top["id"])
    await _category(owner_client, "Small", parent_id=other["id"])
    dup_sub = await owner_client.post(
        "/api/v1/categories", json={"name": "SMALL", "parent_id": top["id"]}
    )
    assert dup_sub.status_code == 409
    # A sub-category name does not block a top-level name.
    await _category(owner_client, "Small")
    rename = await owner_client.patch(f"/api/v1/categories/{other['id']}", json={"name": "Decor"})
    assert rename.status_code == 409 and "already called" in rename.json()["detail"]


async def test_rename_cascades_to_skus_and_ledger_map(owner_client: AsyncClient) -> None:
    db = owner_client.test_db
    seating = await _category(owner_client, "Seating")
    sku = await _sku(
        owner_client, "LIST-R1", category="Seating", category_id=uuid.UUID(seating["id"])
    )
    archived_sku = await _sku(
        owner_client,
        "LIST-R2",
        category="Seating",
        category_id=uuid.UUID(seating["id"]),
        is_archived=True,
    )
    stamp = (sku.updated_at, archived_sku.updated_at)

    resp = await owner_client.patch(
        f"/api/v1/categories/{seating['id']}", json={"name": "Lounge seating"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Lounge seating"
    assert resp.json()["sales_account"]["code"] == "4010"

    for row in (sku, archived_sku):
        await db.refresh(row)
        assert row.category == "Lounge seating"
    # The shop feed does not carry the category name; a rename must not touch revisions.
    assert (sku.updated_at, archived_sku.updated_at) == stamp
    maps = (await db.execute(sa.select(CategoryAccountMap.category))).scalars().all()
    assert "Lounge seating" in maps and "Seating" not in maps
    assert await CategoryPostingService(db).sales_code_for_sku(sku) == "4010"


async def test_rename_refused_when_ledger_map_name_is_taken(owner_client: AsyncClient) -> None:
    # "Storage" has a seeded ledger map but no category row here.
    seating = await _category(owner_client, "Seating")
    sku = await _sku(
        owner_client, "LIST-R3", category="Seating", category_id=uuid.UUID(seating["id"])
    )
    resp = await owner_client.patch(f"/api/v1/categories/{seating['id']}", json={"name": "Storage"})
    assert resp.status_code == 409
    assert "Category posting already has an entry" in resp.json()["detail"]
    await owner_client.test_db.refresh(sku)
    assert sku.category == "Seating"  # rolled back with the refusal


async def test_rename_case_only_keeps_ledger_map(owner_client: AsyncClient) -> None:
    seating = await _category(owner_client, "Seating")
    resp = await owner_client.patch(f"/api/v1/categories/{seating['id']}", json={"name": "SEATING"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["sales_account"]["code"] == "4010"


async def test_archive_restore_and_refusals(owner_client: AsyncClient) -> None:
    top = await _category(owner_client, "Bedroom")
    sub = await _category(owner_client, "Headboards", parent_id=top["id"])
    spare = await _category(owner_client, "Spare", parent_id=top["id"])
    sku = await _sku(
        owner_client,
        "LIST-A1",
        category="Bedroom",
        category_id=uuid.UUID(top["id"]),
        subcategory_id=uuid.UUID(sub["id"]),
    )

    refused = await owner_client.patch(
        f"/api/v1/categories/{sub['id']}", json={"is_archived": True}
    )
    assert refused.status_code == 409
    assert refused.json()["detail"].startswith("1 active SKU use this sub-category")
    refused_top = await owner_client.patch(
        f"/api/v1/categories/{top['id']}", json={"is_archived": True}
    )
    assert refused_top.status_code == 409 and "1 active SKU" in refused_top.json()["detail"]

    sku.is_archived = True  # archived SKUs keep the category and do not block archiving
    await owner_client.test_db.flush()
    archived = await owner_client.patch(
        f"/api/v1/categories/{top['id']}", json={"is_archived": True}
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["is_archived"] is True
    assert all(child["is_archived"] for child in archived.json()["subcategories"])

    active_ids = {row["id"] for row in (await _tree(owner_client))["categories"]}
    assert top["id"] not in active_ids
    archived_tree = await _tree(owner_client, "archived")
    assert _find(archived_tree, spare["id"])["is_archived"] is True
    everything = await _tree(owner_client, "all")
    assert _find(everything, top["id"])["is_archived"] is True

    # A sub-category cannot come back before its category.
    early = await owner_client.patch(
        f"/api/v1/categories/{spare['id']}", json={"is_archived": False}
    )
    assert early.status_code == 409 and "Restore it first" in early.json()["detail"]

    # Restoring re-checks the name: a new "Bedroom" took it meanwhile.
    await _category(owner_client, "BEDROOM")
    blocked = await owner_client.patch(
        f"/api/v1/categories/{top['id']}", json={"is_archived": False}
    )
    assert blocked.status_code == 409 and "already called" in blocked.json()["detail"]
    restored = await owner_client.patch(
        f"/api/v1/categories/{top['id']}", json={"is_archived": False, "name": "Bedroom classic"}
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["is_archived"] is False
    assert restored.json()["name"] == "Bedroom classic"
    assert (
        await owner_client.patch(f"/api/v1/categories/{spare['id']}", json={"is_archived": False})
    ).status_code == 200


async def test_category_cannot_move(owner_client: AsyncClient) -> None:
    first = await _category(owner_client, "Dining")
    second = await _category(owner_client, "Outdoor")
    sub = await _category(owner_client, "Benches", parent_id=first["id"])
    for target, body in (
        (sub, {"parent_id": second["id"]}),
        (sub, {"parent_id": None}),
        (second, {"parent_id": first["id"]}),
    ):
        resp = await owner_client.patch(f"/api/v1/categories/{target['id']}", json=body)
        assert resp.status_code == 409, body
        assert "cannot move" in resp.json()["detail"]
    same = await owner_client.patch(
        f"/api/v1/categories/{sub['id']}", json={"parent_id": first["id"], "name": "Bench seats"}
    )
    assert same.status_code == 200 and same.json()["name"] == "Bench seats"


async def test_shop_category_set_clear_and_validation(owner_client: AsyncClient) -> None:
    db = owner_client.test_db
    top = await _category(owner_client, "Sofas")
    sub = await _category(owner_client, "Corner sofas", parent_id=top["id"])
    sku = await _sku(owner_client, "LIST-S1", category="Sofas", category_id=uuid.UUID(top["id"]))
    before = sku.updated_at

    unknown = await owner_client.patch(
        f"/api/v1/categories/{top['id']}", json={"shop_category": "kitchens"}
    )
    assert unknown.status_code == 422
    assert unknown.json() == {
        "detail": [
            {
                "type": "value_error",
                "loc": ["body", "shop_category"],
                "msg": "Unknown shop section 'kitchens'.",
                "input": None,
            }
        ]
    }
    on_sub = await owner_client.patch(
        f"/api/v1/categories/{sub['id']}", json={"shop_category": "sofas-armchairs"}
    )
    assert on_sub.status_code == 422
    assert on_sub.json()["detail"][0]["loc"] == ["body", "shop_category"]
    assert on_sub.json()["detail"][0]["msg"] == "Only a top-level category can have a shop section."
    on_new_sub = await owner_client.post(
        "/api/v1/categories",
        json={"name": "Daybeds", "parent_id": top["id"], "shop_category": "bedroom"},
    )
    assert on_new_sub.status_code == 422
    assert on_new_sub.json()["detail"][0]["loc"] == ["body", "shop_category"]

    set_resp = await owner_client.patch(
        f"/api/v1/categories/{top['id']}", json={"shop_category": "sofas-armchairs"}
    )
    assert set_resp.status_code == 200 and set_resp.json()["shop_category"] == "sofas-armchairs"
    await db.refresh(sku)
    assert sku.updated_at > before  # the shop feed sees the new section

    untouched = await owner_client.patch(f"/api/v1/categories/{top['id']}", json={"name": "Sofas"})
    assert untouched.json()["shop_category"] == "sofas-armchairs"
    cleared = await owner_client.patch(
        f"/api/v1/categories/{top['id']}", json={"shop_category": None}
    )
    assert cleared.status_code == 200 and cleared.json()["shop_category"] is None


async def test_name_validation(owner_client: AsyncClient) -> None:
    assert (await owner_client.post("/api/v1/categories", json={"name": "  "})).status_code == 422
    too_long = await owner_client.post("/api/v1/categories", json={"name": "x" * 65})
    assert too_long.status_code == 422
    stripped = await _category(owner_client, "  Rugs  ")
    assert stripped["name"] == "Rugs"
    missing = await owner_client.patch(f"/api/v1/categories/{uuid.uuid4()}", json={"name": "X"})
    assert missing.status_code == 404


# --- Materials --------------------------------------------------------------------------


def test_material_family_literal_matches_model() -> None:
    assert typing.get_args(MaterialFamily) == MATERIAL_FAMILIES


def test_fold_name() -> None:
    assert fold_name(" Bouclé ") == fold_name("BOUCLE") == "boucle"


async def test_material_create_rename_family_archive_restore(owner_client: AsyncClient) -> None:
    db = owner_client.test_db
    boucle = await _material(owner_client, "Bouclé")
    assert boucle["family"] == "fabric" and boucle["is_archived"] is False
    assert boucle["sku_count"] == 0

    for name in ("Boucle", "BOUCLÉ"):
        dup = await owner_client.post("/api/v1/materials", json={"name": name, "family": "fabric"})
        assert dup.status_code == 409 and "already called" in dup.json()["detail"], name
    bad_family = await owner_client.post("/api/v1/materials", json={"name": "Cork", "family": "x"})
    assert bad_family.status_code == 422

    oak = await _material(owner_client, "Oak", "wood")
    main = await _sku(owner_client, "LIST-M1", main_material_id=uuid.UUID(boucle["id"]))
    other = await _sku(owner_client, "LIST-M2", main_material_id=uuid.UUID(oak["id"]))
    db.add(SkuMaterial(sku_id=other.id, material_id=uuid.UUID(boucle["id"]), position=0))
    await _sku(owner_client, "LIST-M3", main_material_id=uuid.UUID(boucle["id"]), is_archived=True)
    # Main and other on the same SKU count once.
    db.add(SkuMaterial(sku_id=main.id, material_id=uuid.UUID(boucle["id"]), position=0))
    await db.flush()

    listed = (await owner_client.get("/api/v1/materials")).json()
    by_id = {row["id"]: row for row in listed}
    assert by_id[boucle["id"]]["sku_count"] == 2
    assert by_id[oak["id"]]["sku_count"] == 1
    families = [MATERIAL_FAMILIES.index(row["family"]) for row in listed]
    assert families == sorted(families)

    renamed = await owner_client.patch(
        f"/api/v1/materials/{oak['id']}", json={"name": "Smoked oak", "family": "other"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Smoked oak" and renamed.json()["family"] == "other"
    taken = await owner_client.patch(f"/api/v1/materials/{oak['id']}", json={"name": "boucle"})
    assert taken.status_code == 409

    archived = await owner_client.patch(
        f"/api/v1/materials/{boucle['id']}", json={"is_archived": True}
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["is_archived"] is True and archived.json()["sku_count"] == 2
    await db.refresh(main)
    assert main.main_material_id == uuid.UUID(boucle["id"])  # SKUs keep it
    active_ids = {row["id"] for row in (await owner_client.get("/api/v1/materials")).json()}
    assert boucle["id"] not in active_ids
    archived_rows = (
        await owner_client.get("/api/v1/materials", params={"lifecycle": "archived"})
    ).json()
    assert [row["id"] for row in archived_rows] == [boucle["id"]]

    # The name is free while archived; restoring re-checks it.
    replacement = await _material(owner_client, "Boucle")
    blocked = await owner_client.patch(
        f"/api/v1/materials/{boucle['id']}", json={"is_archived": False}
    )
    assert blocked.status_code == 409
    await owner_client.patch(f"/api/v1/materials/{replacement['id']}", json={"is_archived": True})
    restored = await owner_client.patch(
        f"/api/v1/materials/{boucle['id']}", json={"is_archived": False}
    )
    assert restored.status_code == 200 and restored.json()["is_archived"] is False
    assert (
        await owner_client.patch(f"/api/v1/materials/{uuid.uuid4()}", json={"name": "X"})
    ).status_code == 404


# --- Permissions ------------------------------------------------------------------------


async def test_anonymous_is_refused(async_client: AsyncClient) -> None:
    for method, path, body in (
        ("GET", "/api/v1/categories", None),
        ("POST", "/api/v1/categories", {"name": "Anon"}),
        ("PATCH", f"/api/v1/categories/{uuid.uuid4()}", {"name": "Anon"}),
        ("GET", "/api/v1/materials", None),
        ("POST", "/api/v1/materials", {"name": "Anon", "family": "other"}),
        ("PATCH", f"/api/v1/materials/{uuid.uuid4()}", {"name": "Anon"}),
    ):
        resp = await async_client.request(method, path, json=body)
        assert resp.status_code == 401, (method, path)


async def test_staff_without_catalogue_mutate_can_read_only(
    async_client: AsyncClient, owner_client: AsyncClient
) -> None:
    category = await _category(owner_client, "Readable")
    material = await _material(owner_client, "Readable", "other")
    await create_test_staff(owner_client, email="till-lists@example.com", role="till")
    async_client.headers.pop("Authorization", None)
    assert (await authenticate_as(async_client, "till-lists@example.com")).status_code == 200

    assert (await async_client.get("/api/v1/categories")).status_code == 200
    assert (await async_client.get("/api/v1/materials")).status_code == 200
    for method, path, body in (
        ("POST", "/api/v1/categories", {"name": "Till"}),
        ("PATCH", f"/api/v1/categories/{category['id']}", {"name": "Till"}),
        ("POST", "/api/v1/materials", {"name": "Till", "family": "other"}),
        ("PATCH", f"/api/v1/materials/{material['id']}", {"is_archived": True}),
    ):
        resp = await async_client.request(method, path, json=body)
        assert resp.status_code == 403, (method, path)


# --- New tenants ------------------------------------------------------------------------


async def test_tenant_signup_seeds_default_lists(async_db) -> None:
    from app.crud.ops_commerce import SHOP_CATEGORIES
    from app.models.catalogue_list import DEFAULT_MATERIALS
    from app.schemas.tenant_signup import SignupIntent
    from app.services.chart_of_accounts import CATEGORY_MAPS
    from app.services.clerk import ClerkSession
    from app.services.tenant_signup import TenantSignupService
    from f0rge_db.organisation import tenant_id_ctx
    from tests.test_tenant_signup import provider

    token = tenant_id_ctx.set(None)
    try:
        team = await TenantSignupService(async_db, provider()).create(
            ClerkSession("user_new"), SignupIntent(name="Lists business", slug="lists-business")
        )
    finally:
        tenant_id_ctx.reset(token)
    categories = (
        (await async_db.execute(sa.select(SkuCategory).where(SkuCategory.team_id == team["id"])))
        .scalars()
        .all()
    )
    assert sorted(row.name for row in categories) == sorted(row[0] for row in CATEGORY_MAPS)
    assert all(row.parent_id is None and not row.is_archived for row in categories)
    assert all(row.shop_category == SHOP_CATEGORIES.get(row.name.lower()) for row in categories)
    materials = (
        (await async_db.execute(sa.select(Material).where(Material.team_id == team["id"])))
        .scalars()
        .all()
    )
    assert sorted((row.name, row.family) for row in materials) == sorted(DEFAULT_MATERIALS)


@pytest.fixture(autouse=True)
def _signup_enabled(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "tenant_signup_enabled", True)
    monkeypatch.setattr(settings, "public_app_url", "https://app.firstout.co.za")
    monkeypatch.setattr(settings, "clerk_secret_key", "")


# --- Team filter, independent of RLS ----------------------------------------------------


async def test_queries_filter_by_team_without_rls(owner_client: AsyncClient) -> None:
    """The plain test database has no RLS policies, so only the team filter narrows here."""
    from app.models.account import Account, AccountType
    from app.models.team import Team

    db = owner_client.test_db
    other = Team(name="Other company", slug="lists-other-company", clerk_org_id="org_lists_other")
    db.add(other)
    await db.flush()
    foreign_top = SkuCategory(team_id=other.id, name="Lighting")
    foreign_material = Material(team_id=other.id, name="Cork", family="other")
    db.add_all(
        [
            foreign_top,
            foreign_material,
            # Same code as our seeded 4010, and a map for a name only we use as a category.
            Account(
                team_id=other.id, code="4010", name="Other company sales", type=AccountType.INCOME
            ),
            Account(team_id=other.id, code="4999", name="Other lighting", type=AccountType.INCOME),
            CategoryAccountMap(
                team_id=other.id,
                category="Lighting",
                sales_code="4999",
                cogs_code="4999",
                stock_adj_code="4999",
                count_var_code="4999",
            ),
        ]
    )
    await db.flush()
    db.add(SkuCategory(team_id=other.id, name="Pendants", parent_id=foreign_top.id))
    db.add(
        Sku(
            team_id=other.id,
            our_ref="LIST-OTHER",
            our_barcode="LIST-OTHER",
            name="Other company lamp",
            design="Other lamp",
            fabric="-",
            retail_ex_vat=100,
            category="Lighting",
            category_id=foreign_top.id,
            main_material_id=foreign_material.id,
        )
    )
    await db.commit()

    # Duplicate-name checks see only this team: the other company's names are free here.
    lighting = await _category(owner_client, "Lighting")
    cork = await _material(owner_client, "Cork", "other")
    seating = await _category(owner_client, "Seating")

    tree = await _tree(owner_client, "all")
    assert str(foreign_top.id) not in str(tree)
    node = _find(tree, lighting["id"])
    assert node["sales_account"] is None  # the other company's "Lighting" map is not ours
    assert node["sku_count"] == 0 and node["subcategories"] == []
    assert _find(tree, seating["id"])["sales_account"]["name"] != "Other company sales"
    materials = (await owner_client.get("/api/v1/materials?lifecycle=all")).json()
    assert str(foreign_material.id) not in str(materials)
    assert next(row for row in materials if row["id"] == cork["id"])["sku_count"] == 0

    # Get-by-id (behind every PATCH and the parent lookup) cannot reach the other company.
    for path in (
        f"/api/v1/categories/{foreign_top.id}",
        f"/api/v1/materials/{foreign_material.id}",
    ):
        resp = await owner_client.patch(path, json={"name": "Taken over"})
        assert resp.status_code == 404, resp.text
    child = await owner_client.post(
        "/api/v1/categories", json={"name": "Child", "parent_id": str(foreign_top.id)}
    )
    assert child.status_code == 404

    # Rename and archive cascades touch only this team's SKUs and ledger map.
    renamed = await owner_client.patch(
        f"/api/v1/categories/{lighting['id']}", json={"name": "Lamps"}
    )
    assert renamed.status_code == 200, renamed.text
    other_sku = await db.scalar(sa.select(Sku).where(Sku.our_ref == "LIST-OTHER"))
    await db.refresh(other_sku)
    other_map = await db.scalar(
        sa.select(CategoryAccountMap).where(CategoryAccountMap.team_id == other.id)
    )
    await db.refresh(other_map)
    assert other_sku.category == "Lighting" and other_map.category == "Lighting"
    archived = await owner_client.patch(
        f"/api/v1/categories/{renamed.json()['id']}", json={"is_archived": True}
    )
    assert archived.status_code == 200, archived.text
    await db.refresh(foreign_top)
    assert foreign_top.is_archived is False


# --- Material rename keeps finish labels true -------------------------------------------


async def test_material_rename_rebuilds_finish_labels(owner_client: AsyncClient) -> None:
    from app.models.team import Team

    db = owner_client.test_db
    oak = await _material(owner_client, "Oak", "wood")
    oak_id = uuid.UUID(oak["id"])
    derived = await _sku(owner_client, "LIST-F1", colour_name="Natural", main_material_id=oak_id)
    derived.design, derived.fabric = "Arc", "Natural Oak"
    archived = await _sku(owner_client, "LIST-F2", main_material_id=oak_id, is_archived=True)
    archived.design, archived.fabric = "Arc", "Oak"
    legacy = await _sku(owner_client, "LIST-F3", main_material_id=oak_id)
    legacy.fabric = "Hathaway veneer"  # never derived: left alone
    # Another team's SKU with its own "Oak" material keeps its label.
    other = Team(name="Other finish co", slug="lists-finish-other", clerk_org_id="org_lists_finish")
    db.add(other)
    await db.flush()
    other_oak = Material(team_id=other.id, name="Oak", family="wood")
    db.add(other_oak)
    await db.flush()
    foreign = Sku(
        team_id=other.id,
        our_ref="LIST-F-OTHER",
        our_barcode="LIST-F-OTHER",
        name="Other",
        design="Arc",
        fabric="Natural Oak",
        colour_name="Natural",
        retail_ex_vat=100,
        main_material_id=other_oak.id,
    )
    db.add(foreign)
    await db.commit()
    stamps = {row.id: row.updated_at for row in (derived, archived)}

    renamed = await owner_client.patch(f"/api/v1/materials/{oak['id']}", json={"name": "White oak"})
    assert renamed.status_code == 200, renamed.text
    for row in (derived, archived, legacy, foreign):
        await db.refresh(row)
    assert derived.fabric == "Natural White oak"
    assert archived.fabric == "White oak"
    assert legacy.fabric == "Hathaway veneer"
    assert foreign.fabric == "Natural Oak"
    # The shop feed sends neither the label nor material names: revisions stay.
    assert {row.id: row.updated_at for row in (derived, archived)} == stamps

    # A second SKU with the same design, colour and material is now refused.
    duplicate = await owner_client.post(
        "/api/v1/skus",
        json={
            "our_ref": "LIST-F4",
            "our_barcode": "LIST-F4",
            "name": "Arc chair",
            "design": "Arc",
            "colour_name": "Natural",
            "main_material_id": oak["id"],
            "retail_ex_vat": "100.00",
        },
    )
    assert duplicate.status_code == 409, duplicate.text
    assert "Another SKU already has this design, colour and material." in duplicate.text


async def test_material_rename_that_would_collide_is_refused(owner_client: AsyncClient) -> None:
    db = owner_client.test_db
    oak = await _material(owner_client, "Oak", "wood")
    ash = await _material(owner_client, "Ash", "wood")
    on_oak = await _sku(
        owner_client, "LIST-C1", colour_name="Natural", main_material_id=uuid.UUID(oak["id"])
    )
    on_oak.design, on_oak.fabric = "Arc", "Natural Oak"
    # A hand-typed label equal to what renaming Oak to "Walnut" would produce for LIST-C1.
    clash = await _sku(owner_client, "LIST-C2", main_material_id=uuid.UUID(ash["id"]))
    clash.design, clash.fabric = "Arc", "Natural Walnut"
    await db.commit()

    refused = await owner_client.patch(f"/api/v1/materials/{oak['id']}", json={"name": "Walnut"})
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == (
        "Renaming to 'Walnut' would give SKUs the same design, colour and material: "
        "LIST-C1 and LIST-C2. Change one of them first."
    )
    await db.refresh(on_oak)
    assert on_oak.fabric == "Natural Oak"
    names = {row["name"] for row in (await owner_client.get("/api/v1/materials")).json()}
    assert "Oak" in names and "Walnut" not in names
