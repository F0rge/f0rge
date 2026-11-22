from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from uuid import UUID, uuid4
from zipfile import ZipFile

import pytest
from httpx import AsyncClient
from PIL import Image
from f0rge_core.exceptions import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.sku import Sku
from app.models.team import Team
from app.services.curated_catalogue_archive import read_catalogue_archive
from tests.conftest import authenticate_as, create_test_staff


IMPORT = "/api/v1/skus/curated-catalogue"
FEED = "/api/v1/ops-commerce/v1/products"


def _jpeg(red: int) -> bytes:
    photo = io.BytesIO()
    Image.new("RGB", (65, 65), (red, 0, 12)).save(photo, format="JPEG")
    return photo.getvalue()


def _bundle(
    *edited: tuple[str, str, tuple[bytes, bytes, bytes]],
    retained: tuple[str, str] | None = None,
    wrong_digest: bool = False,
    extra_file: bool = False,
    colour_names: dict[str, str] | None = None,
    retain_setting: bool = False,
) -> bytes:
    package = io.BytesIO()
    variants = []
    skus = []
    with ZipFile(package, "w") as archive:
        for sku_id, code, photos in edited:
            gallery = []
            for slot, image in enumerate(photos, start=1):
                filename = f"{code}-{slot}.jpg"
                archive.writestr(filename, image)
                gallery.append(
                    {
                        "filename": filename,
                        "sha256": "0" * 64
                        if wrong_digest and slot == 1
                        else hashlib.sha256(image).hexdigest(),
                    }
                )
            name = "Arched Chair"
            skus.append(
                dict(
                    sku_id=sku_id,
                    our_ref=code,
                    name=name,
                    fabric=f"Upholstery {code}",
                    width_cm=74.5,
                    depth_cm=85,
                    notes="Internal swatch reference",
                    piece_count=2,
                    gallery=gallery,
                )
            )
            if retain_setting:
                skus[-1]["retain_current_photo_as_setting"] = True
            colour = (colour_names or {}).get(code, code)
            variants.append({"sku_id": sku_id, "options": {"Colour": colour}})
        if retained is not None:
            skus.append({"sku_id": retained[0], "our_ref": retained[1]})
        if extra_file:
            archive.writestr("../unsafe.jpg", _jpeg(30))
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "skus": skus,
                    "groups": [{"title": "Arched Chair", "variants": variants}]
                    if len(variants) > 1
                    else [],
                }
            ),
        )
    return package.getvalue()


@pytest.mark.no_db
def test_archive_checks_bytes_and_rejects_paths() -> None:
    first = (str(uuid4()), "FIRST", (_jpeg(37), _jpeg(54), _jpeg(71)))
    retained = (str(uuid4()), "RETAINED")
    actual = read_catalogue_archive(io.BytesIO(_bundle(first, retained=retained)))
    assert tuple(actual.images.values()) == first[2]
    assert actual.manifest.skus[0].piece_count == 2
    with pytest.raises(ValidationError, match="checksum"):
        read_catalogue_archive(io.BytesIO(_bundle(first, retained=retained, wrong_digest=True)))
    with pytest.raises(ValidationError, match="unsupported"):
        read_catalogue_archive(io.BytesIO(_bundle(first, retained=retained, extra_file=True)))


@pytest.mark.asyncio
async def test_apply_is_scoped_repeatable_and_adds_gallery_to_only_the_opt_in_feed(
    owner_client: AsyncClient,
    async_db: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    company_id = (await async_db.execute(select(Team.id))).scalar_one()
    monkeypatch.setattr(settings, "ops_commerce_company_id", str(company_id))
    monkeypatch.setattr(settings, "ops_commerce_token", "curated-test-token")
    monkeypatch.setattr(settings, "ops_commerce_allowed_host", "test")
    monkeypatch.setattr(settings, "ops_commerce_auto_publish_enabled", True)
    monkeypatch.setattr(settings, "bucket_name", None)
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    headers = {
        "Authorization": "Bearer curated-test-token",
        "X-Ops-Company-ID": str(company_id),
    }

    async def create(code: str, *, legacy_photo: bool = False) -> str:
        created = await owner_client.post(
            "/api/v1/skus",
            json={
                "our_ref": code,
                "name": f"Original {code}",
                "design": code,
                "fabric": "Legacy fabric",
                "category": "Armchairs",
                "carton_count": 3,
            },
        )
        assert created.status_code == 201, created.text
        sku_id = created.json()["id"]
        price = await owner_client.patch(
            f"/api/v1/skus/{sku_id}", json={"retail_ex_vat": "1400.00"}
        )
        assert price.status_code == 200, price.text
        if legacy_photo:
            uploaded = await owner_client.post(
                f"/api/v1/skus/{sku_id}/photo",
                files={"photo": ("old.jpg", _jpeg(150), "image/jpeg")},
            )
            assert uploaded.status_code == 200, uploaded.text
        return sku_id

    first_id = await create("RED")
    second_id = await create("ORANGE")
    retained_id = await create("RETAINED", legacy_photo=True)
    excluded_id = await create("EXCLUDED", legacy_photo=True)
    first = (first_id, "RED", (_jpeg(20), _jpeg(31), _jpeg(42)))
    second = (second_id, "ORANGE", (_jpeg(88), _jpeg(99), _jpeg(110)))
    retained = (retained_id, "RETAINED")
    package = _bundle(first, second, retained=retained)
    before = (await owner_client.get(FEED, headers=headers)).json()
    assert [p["sku"] for p in before["products"]] == ["EXCLUDED", "RETAINED"]
    original_image = await owner_client.get(f"{FEED}/{retained_id}/photo", headers=headers)
    assert original_image.status_code == 200

    async def import_file(data: bytes, *, apply: bool = False, scope: str | None = None):
        fields = {"dry_run": "false" if apply else "true"}
        if scope is not None:
            fields["scope"] = scope
        return await owner_client.post(
            IMPORT,
            files={"archive": ("review.zip", data, "application/zip")},
            data=fields,
        )

    denied = await import_file(_bundle(first, second, retained=(excluded_id, "WRONG")), apply=True)
    assert denied.status_code == 400, denied.text
    assert not list(tmp_path.rglob("curated"))
    preview = await import_file(package)
    assert preview.status_code == 200, preview.text
    assert preview.json() == {
        "applied": False,
        "selected_skus": 3,
        "gallery_images": 6,
        "groups": 1,
        "held_without_price": [],
    }
    assert not list(tmp_path.rglob("curated"))
    assert (await owner_client.get(f"/api/v1/skus/{first_id}")).json()["name"] == "Original RED"
    applied = await import_file(package, apply=True)
    assert applied.status_code == 200, applied.text
    assert applied.json()["applied"] is True

    details = (await owner_client.get(f"/api/v1/skus/{first_id}")).json()
    assert details["name"] == "Arched Chair"
    assert details["width_cm"] == 74.5
    assert details["depth_cm"] == 85
    assert details["fabric"] == "Upholstery RED"
    assert details["notes"] == "Internal swatch reference"
    assert details["piece_count"] == 2
    assert details["carton_count"] == 3
    assert details["is_kit"] is False
    assert details["gallery_photo_count"] == 3

    response = await owner_client.get(f"{FEED}?catalogue_version=2", headers=headers)
    assert response.status_code == 200, response.text
    v2 = response.json()
    assert v2["curated_catalogue"] is True
    products = {product["sku"]: product for product in v2["products"]}
    assert set(products) == {"RED", "ORANGE", "RETAINED"}
    red = products["RED"]
    assert red["product_group_id"] == products["ORANGE"]["product_group_id"]
    assert red["options"] == {"Colour": "RED"}
    assert red["gallery_photo_tokens"] == [hashlib.sha256(image).hexdigest() for image in first[2]]
    assert red["dimensions_cm"] == {"width": 74.5, "depth": 85, "height": None, "diameter": None}
    assert red["piece_count"] == 2
    assert "notes" not in red
    assert products["RETAINED"]["name"] == "Original RETAINED"
    assert "gallery_photo_tokens" not in products["RETAINED"]
    assert products["RETAINED"]["dimensions_cm"] is None
    assert products["RETAINED"]["piece_count"] is None
    old_feed = (await owner_client.get(FEED, headers=headers)).json()
    for key in ("gallery_photo_tokens", "dimensions_cm", "piece_count"):
        assert all(key not in product for product in old_feed["products"])
    assert "curated_catalogue" not in old_feed
    for slot, image in enumerate(first[2], start=1):
        assert (
            await owner_client.get(f"{FEED}/{first_id}/photo?slot={slot}", headers=headers)
        ).content == image
        assert (
            await owner_client.get(f"/api/v1/skus/{first_id}/photo?slot={slot}")
        ).content == image
    assert (
        await owner_client.get(f"{FEED}/{retained_id}/photo", headers=headers)
    ).content == original_image.content
    assert (
        await owner_client.get(f"{FEED}/{excluded_id}/photo", headers=headers)
    ).status_code == 404
    assert (
        await owner_client.get(f"{FEED}/{retained_id}/photo?slot=2", headers=headers)
    ).status_code == 404

    repeated = await import_file(package, apply=True)
    assert repeated.status_code == 200, repeated.text
    refreshed = (await owner_client.get(f"{FEED}?catalogue_version=2", headers=headers)).json()
    replayed = next(row for row in refreshed["products"] if row["sku"] == "RED")
    assert replayed["product_group_id"] == red["product_group_id"]
    assert replayed["gallery_photo_tokens"] == red["gallery_photo_tokens"]
    assert len(list(tmp_path.rglob("curated/*.jpg"))) == 6
    sku = await async_db.get(Sku, UUID(first_id))
    assert sku is not None and sku.photo_storage_key is None

    # A replacement can take over the same option in the existing family.
    replacement_id = await create("CHERRY")
    replacement = (replacement_id, "CHERRY", (_jpeg(48), _jpeg(60), _jpeg(72)))
    update = _bundle(replacement, second, retained=retained, colour_names={"CHERRY": "RED"})
    updated = await import_file(update, apply=True)
    assert updated.status_code == 200, updated.text
    result = (await owner_client.get(f"{FEED}?catalogue_version=2", headers=headers)).json()
    changed = {row["sku"]: row for row in result["products"]}
    assert set(changed) == {"CHERRY", "ORANGE", "RETAINED"}
    assert changed["CHERRY"]["product_group_id"] == red["product_group_id"]
    assert changed["CHERRY"]["options"] == {"Colour": "RED"}

    legacy_details = await owner_client.patch(
        f"/api/v1/skus/{retained_id}", json={"width_cm": 180, "piece_count": 2}
    )
    assert legacy_details.status_code == 200, legacy_details.text
    with_legacy_details = (
        await owner_client.get(f"{FEED}?catalogue_version=2", headers=headers)
    ).json()
    retained_row = next(row for row in with_legacy_details["products"] if row["sku"] == "RETAINED")
    assert retained_row["dimensions_cm"]["width"] == 180
    assert retained_row["piece_count"] == 2
    assert "gallery_photo_tokens" not in retained_row

    cleared = await owner_client.patch(
        f"/api/v1/skus/{retained_id}", json={"width_cm": None, "piece_count": None}
    )
    assert cleared.status_code == 200, cleared.text
    cleared_feed = (await owner_client.get(f"{FEED}?catalogue_version=2", headers=headers)).json()
    retained_row = next(row for row in cleared_feed["products"] if row["sku"] == "RETAINED")
    assert retained_row["dimensions_cm"] is None
    assert retained_row["piece_count"] is None

    studio_photos = (_jpeg(86), _jpeg(94), _jpeg(102))
    single = _bundle((retained_id, "RETAINED", studio_photos), retain_setting=True)
    same_as_setting = (retained_id, "RETAINED", (original_image.content, *studio_photos[:2]))
    legacy_sku = await async_db.get(Sku, UUID(retained_id), populate_existing=True)
    assert legacy_sku is not None and legacy_sku.photo_storage_key
    legacy_storage_key = legacy_sku.photo_storage_key

    # A scope selection mistake cannot replace the workspace catalogue with this archive.
    assert (await import_file(single, apply=True)).status_code == 400
    assert (await import_file(package, apply=True, scope="sku")).status_code == 400
    excluded_gallery = _bundle((excluded_id, "EXCLUDED", studio_photos), retain_setting=True)
    assert (await import_file(excluded_gallery, apply=True, scope="sku")).status_code == 400
    missing_original = _bundle((second_id, "ORANGE", studio_photos), retain_setting=True)
    assert (await import_file(missing_original, scope="sku")).status_code == 400
    for apply in (False, True):
        duplicate = await import_file(
            _bundle(same_as_setting, retain_setting=True), apply=apply, scope="sku"
        )
        assert duplicate.status_code == 400 and "distinct" in duplicate.text
    preview = await import_file(single, scope="sku")
    assert preview.status_code == 200, preview.text
    assert preview.json()["gallery_images"] == 4
    assert not list(tmp_path.rglob("setting/*.jpg"))
    assert (
        await owner_client.get(f"{FEED}/{retained_id}/photo?slot=4", headers=headers)
    ).status_code == 404

    for _ in range(2):
        applied = await import_file(single, apply=True, scope="sku")
        assert applied.status_code == 200, applied.text
        assert applied.json()["gallery_images"] == 4
    reread = await async_db.get(Sku, UUID(retained_id), populate_existing=True)
    assert reread is not None and reread.photo_storage_key == legacy_storage_key
    assert Path(legacy_storage_key).read_bytes() == original_image.content
    assert len(list(tmp_path.rglob("setting/*.jpg"))) == 1
    # Even later reviews that leave the setting alone cannot duplicate it in studio.
    for scope in ("catalogue", "sku"):
        for apply in (False, True):
            duplicate = await import_file(_bundle(same_as_setting), scope=scope, apply=apply)
            assert duplicate.status_code == 400 and "distinct" in duplicate.text

    opted_in_feed = (
        await owner_client.get(
            f"{FEED}?catalogue_version=2&include_setting_photo=true", headers=headers
        )
    ).json()
    products = {row["sku"]: row for row in opted_in_feed["products"]}
    assert set(products) == {"CHERRY", "ORANGE", "RETAINED"}
    assert products["CHERRY"]["product_group_id"] == products["ORANGE"]["product_group_id"]
    assert products["CHERRY"]["product_group_id"] == red["product_group_id"]
    assert products["CHERRY"]["setting_photo_token"] is None
    updated_sku = products["RETAINED"]
    assert updated_sku["name"] == "Arched Chair"
    assert updated_sku["setting_photo_token"] == hashlib.sha256(original_image.content).hexdigest()
    assert updated_sku["gallery_photo_tokens"] == [
        hashlib.sha256(photo).hexdigest() for photo in studio_photos
    ]
    for query in ("catalogue_version=2", "include_setting_photo=true"):
        legacy_feed = (await owner_client.get(f"{FEED}?{query}", headers=headers)).json()
        assert all("setting_photo_token" not in row for row in legacy_feed["products"])

    for slot, photo in enumerate((*studio_photos, original_image.content), start=1):
        response = await owner_client.get(
            f"{FEED}/{retained_id}/photo?slot={slot}", headers=headers
        )
        assert response.status_code == 200 and response.content == photo
        staff = await owner_client.get(f"/api/v1/skus/{retained_id}/photo?slot={slot}")
        assert staff.status_code == 200 and staff.content == photo
    assert (await owner_client.get(f"/api/v1/skus/{retained_id}")).json()[
        "gallery_photo_count"
    ] == 4
    assert (
        await owner_client.get(f"{FEED}/{excluded_id}/photo?slot=4", headers=headers)
    ).status_code == 404

    # Editing a selected member's studio gallery does not unlink the member.
    grouped_update = await import_file(
        _bundle((second_id, "ORANGE", studio_photos)), apply=True, scope="sku"
    )
    assert grouped_update.status_code == 200, grouped_update.text
    updated_group_feed = (
        await owner_client.get(f"{FEED}?catalogue_version=2", headers=headers)
    ).json()
    orange = next(row for row in updated_group_feed["products"] if row["sku"] == "ORANGE")
    assert orange["product_group_id"] == red["product_group_id"]
    assert orange["options"] == {"Colour": "ORANGE"}


@pytest.mark.asyncio
async def test_buyer_cannot_preflight_or_apply_workspace_catalogue(
    owner_client: AsyncClient,
) -> None:
    email = "curated-catalogue-buyer@example.com"
    await create_test_staff(owner_client, email=email, role="buyer")
    assert (await authenticate_as(owner_client, email)).status_code == 200
    for scope in ("catalogue", "sku"):
        for dry_run in ("true", "false"):
            response = await owner_client.post(
                IMPORT,
                files={"archive": ("review.zip", b"invalid zip", "application/zip")},
                data={"dry_run": dry_run, "scope": scope},
            )
            assert response.status_code == 403
