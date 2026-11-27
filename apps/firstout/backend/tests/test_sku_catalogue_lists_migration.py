"""120 adds managed categories and materials under RLS and backfills every team's SKUs,
even when the release runs as a non-superuser owner with RLS forced."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.test_fractional_inventory_migration import migrate

pytestmark = pytest.mark.no_db
PREVIOUS = "119_sku_second_detail_photo"
LISTS = "120_sku_catalogue_lists"
NEW_TABLES = ("materials", "sku_categories", "sku_materials")

_spec = importlib.util.spec_from_file_location(
    "migration_120",
    Path(__file__).resolve().parents[1] / "migrations" / "versions" / f"{LISTS}.py",
)
assert _spec and _spec.loader
_migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migration)

# (fabric, design, name) -> (main material, colour name)
GUESSES = [
    (("Beige Boucle", "Lyon", "Lyon Armchair"), ("Bouclé", "Beige")),
    (("Velvet Navy", "Alexa", "Alexa Chair"), ("Velvet", "Navy")),
    (("Natural Oak", "Oslo", "Oslo Bed"), ("Oak", "Natural")),
    (("-", "Oslo", "Oslo Oak Dining Chair"), ("Oak", None)),
    (("Unspecified", "Siena", "Siena Glass Side Table"), ("Glass", None)),
    (("csv:AB1", "csv:AB1", "Rio Sideboard"), (None, None)),
    # "Ash" followed by a colour is the colour, so velvet is the only material.
    (("Ash Grey Velvet", "Fez", "Fez Ottoman"), ("Velvet", None)),
    (("Solo 111", "Hathaway Taupe", "Hathaway Sofa"), (None, None)),
    (("", "Rio", "Rio Sideboard Walnut & Brass"), (None, None)),
    (("Oat", "Tula", "Tula Sofa"), (None, "Oat")),
    (("Rosé Pink Velvet", "Siena", "Siena Chair"), ("Velvet", "Rosé Pink")),
    (("Light Grey", "Oslo", "Oslo Sofa"), (None, "Light Grey")),
    # A qualifier beside the material word means it is not that material.
    (("Faux Leather Black", "Fez", "Fez Leather Chair"), (None, None)),
    (("PU Leather Brown", "Fez", "Fez Chair"), (None, None)),
    (("Leather Look Tan", "Fez", "Fez Chair"), (None, None)),
    (("Linen Look Grey", "Lyon", "Lyon Linen Sofa"), (None, None)),
    (("Vegan Leather", "", ""), (None, None)),
    # A material word used as a colour is not the material.
    (("Steel Blue", "Tula", "Tula Chair"), (None, None)),
    (("Walnut Brown", "Rio", "Rio Sideboard"), (None, None)),
    (("Ash Grey", "Rio", "Rio Sideboard"), (None, None)),
    # Leftover words that are not colours give no colour name.
    (("Glass Top Black", "Kiva", "Kiva Table"), ("Glass", None)),
    (("Velvet Navy 2", "Alexa", "Alexa Chair"), ("Velvet", None)),
]


def test_frozen_materials_match_the_model_at_this_revision() -> None:
    from app.models.catalogue_list import DEFAULT_MATERIALS

    assert _migration._MATERIALS == DEFAULT_MATERIALS


@pytest.mark.parametrize(("fields", "expected"), GUESSES)
def test_material_and_colour_rule(fields, expected) -> None:
    material = _migration.main_material(*fields)
    assert (material, _migration.colour_name(fields[0], material)) == expected


def _upgrade_on(connection: sa.Connection, revision: str) -> None:
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["connection"] = connection
    command.upgrade(config, revision)


async def _insert_sku(conn, team, category, fabric, design, name="Synthetic piece"):
    sku = uuid.uuid4()
    ref = "CL-" + uuid.uuid4().hex[:10]
    await conn.execute(
        sa.text("""INSERT INTO skus(id,team_id,our_ref,our_barcode,name,design,fabric,category,
            created_at,updated_at)
            VALUES (:id,:team,:ref,:ref,:name,:design,:fabric,:category,
            '2026-01-01','2026-01-01')"""),
        {
            "id": sku,
            "team": team,
            "ref": ref,
            "name": name,
            "design": design,
            "fabric": fabric,
            "category": category,
        },
    )
    return sku


async def test_backfill_policy_constraints_and_downgrade(second_postgres_url: str) -> None:
    url = second_postgres_url
    migrate(url, PREVIOUS)
    admin = create_async_engine(url, poolclass=NullPool)
    role = "catalogue_lists_owner_" + uuid.uuid4().hex[:10]
    password = "synthetic-" + uuid.uuid4().hex
    a, b = uuid.uuid4(), uuid.uuid4()
    skus: dict[str, uuid.UUID] = {}
    try:
        async with admin.begin() as conn:
            for team in (a, b):
                await conn.execute(
                    sa.text("""INSERT INTO teams(id,name,slug,status,created_at,updated_at)
                        VALUES (:id,'Synthetic lists team',:slug,'active',now(),now())"""),
                    {"id": team, "slug": f"lists-{team.hex}"},
                )
            for key, category, fabric, design, name in (
                ("sofa1", "Sofas", "Beige Boucle", "Lyon", "Lyon Sofa"),
                ("sofa2", "Sofas", "Velvet Navy", "Alexa", "Alexa Sofa"),
                ("sofa3", " sofas ", "-", "Oslo", "Oslo Oak Sofa"),
                ("dining", "dining room", "Unspecified", "Siena", "Siena Glass Table"),
                ("lamp", "Lamps", "csv:AB1", "csv:AB1", "Rio Lamp"),
                ("none", None, "Ash Grey Velvet", "Fez", "Fez Ottoman"),
            ):
                skus[key] = await _insert_sku(conn, a, category, fabric, design, name)
            skus["b"] = await _insert_sku(conn, b, "sofas", "Grey Linen", "Lyon", "Lyon Sofa")
            for team, category in ((a, "Seating"), (a, "SOFAS"), (b, "Outdoor")):
                await conn.execute(
                    sa.text("""INSERT INTO category_account_maps
                        (id,team_id,category,sales_code,cogs_code,stock_adj_code,count_var_code,
                         created_at,updated_at)
                        VALUES (gen_random_uuid(),:team,:category,'4010','5010','5110','5210',
                         now(),now())"""),
                    {"team": team, "category": category},
                )
        # The release migrates as the table owner, not a superuser, with RLS forced.
        async with admin.begin() as conn:
            await conn.execute(
                sa.text(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
            )
            await conn.execute(sa.text(f"GRANT CREATE, USAGE ON SCHEMA public TO {role}"))
            await conn.execute(sa.text(f"GRANT ALL ON ALL TABLES IN SCHEMA public TO {role}"))
            for table in (
                "skus",
                "sku_supplier_prices",
                "category_account_maps",
                "alembic_version",
            ):
                await conn.execute(sa.text(f"ALTER TABLE {table} OWNER TO {role}"))
            for table in ("roles", "skus", "category_account_maps"):
                await conn.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
                await conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

        owner = create_async_engine(
            make_url(url).set(username=role, password=password), poolclass=NullPool
        )
        try:
            async with owner.begin() as conn:
                await conn.run_sync(_upgrade_on, LISTS)
                assert await conn.scalar(
                    sa.text("SELECT current_setting('app.tenant_id', true)")
                ) in ("", None)
        finally:
            await owner.dispose()

        async with admin.connect() as conn:
            policies = (
                await conn.execute(
                    sa.text("""SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, p.polname
                        FROM pg_class c JOIN pg_policy p ON p.polrelid = c.oid
                        WHERE c.relname IN ('sku_categories', 'materials', 'sku_materials')
                        ORDER BY c.relname""")
                )
            ).all()
            assert policies == [(t, True, True, "organisation_isolation") for t in NEW_TABLES]

            categories = (
                await conn.execute(
                    sa.text("""SELECT team_id, name, shop_category, parent_id FROM sku_categories
                        WHERE team_id IN (:a, :b)"""),
                    {"a": a, "b": b},
                )
            ).all()
            # One per spelling-insensitive name: SKU spellings by frequency, then account maps.
            assert sorted(categories, key=lambda row: (row[0] != a, row[1])) == [
                (a, "Lamps", None, None),
                (a, "Seating", None, None),
                (a, "Sofas", "sofas-armchairs", None),
                (a, "dining room", "dining-room", None),
                (b, "Outdoor", None, None),
                (b, "sofas", "sofas-armchairs", None),
            ]
            rows = {
                row.id: row
                for row in (
                    await conn.execute(
                        sa.text("""SELECT s.id, s.team_id, s.category, c.name AS category_name,
                                c.team_id AS category_team, m.name AS material,
                                m.team_id AS material_team, s.colour_name, s.sell_multiple,
                                s.min_sell_qty, s.order_up_to, s.do_not_reorder,
                                s.updated_at = s.created_at AS untouched
                            FROM skus s
                            LEFT JOIN sku_categories c ON c.id = s.category_id
                            LEFT JOIN materials m ON m.id = s.main_material_id""")
                    )
                ).all()
            }
            expected = {
                "sofa1": ("Sofas", "Bouclé", "Beige"),
                "sofa2": ("Sofas", "Velvet", "Navy"),
                "sofa3": ("Sofas", "Oak", None),
                "dining": ("dining room", "Glass", None),
                "lamp": ("Lamps", None, None),
                "none": (None, "Velvet", None),
                "b": ("sofas", "Linen", "Grey"),
            }
            for key, (category, material, colour) in expected.items():
                row = rows[skus[key]]
                # The text always equals the linked category's name, within the SKU's team.
                assert (row.category, row.category_name, row.material, row.colour_name) == (
                    category,
                    category,
                    material,
                    colour,
                ), key
                assert row.category_team in (None, row.team_id)
                assert row.material_team in (None, row.team_id)
                # Existing SKUs keep selling and reordering as before.
                assert (row.sell_multiple, row.min_sell_qty, row.order_up_to) == (1, 1, None)
                assert row.do_not_reorder is False and row.untouched
            assert await conn.scalar(
                sa.text("SELECT count(*) FROM materials WHERE team_id = :b"), {"b": b}
            ) == len(_migration._MATERIALS)

        async def refused(statement: str, **params) -> None:
            with pytest.raises(IntegrityError):
                async with admin.begin() as conn:
                    await conn.execute(sa.text(statement), params)

        await refused(
            "UPDATE skus SET sell_multiple = 2, min_sell_qty = 3 WHERE id = :id", id=skus["sofa1"]
        )
        await refused("UPDATE skus SET sell_multiple = 0 WHERE id = :id", id=skus["sofa1"])
        await refused("UPDATE skus SET order_up_to = 0 WHERE id = :id", id=skus["sofa1"])
        insert_category = """INSERT INTO sku_categories
            (id, team_id, name, parent_id, created_at, updated_at)
            VALUES (:id, :team, :name, :parent, now(), now())"""
        await refused(insert_category, id=uuid.uuid4(), team=a, name="SOFAS", parent=None)
        await refused(
            "INSERT INTO materials (id, team_id, name, family, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :team, 'boucLÉ', 'fabric', now(), now())",
            team=a,
        )
        await refused(
            "INSERT INTO materials (id, team_id, name, family, created_at, updated_at) "
            "VALUES (gen_random_uuid(), :team, 'Cork', 'bark', now(), now())",
            team=a,
        )

        async with admin.begin() as conn:
            ids = dict(
                (
                    await conn.execute(
                        sa.text("SELECT name, id FROM sku_categories WHERE team_id = :a"), {"a": a}
                    )
                ).all()
            )
            sofas, dining = ids["Sofas"], ids["dining room"]
            # Archived names may repeat; active ones may not.
            await conn.execute(
                sa.text(
                    "UPDATE sku_categories SET is_archived = true, archived_at = now() "
                    "WHERE id = :id"
                ),
                {"id": dining},
            )
            await conn.execute(
                sa.text(insert_category),
                {"id": uuid.uuid4(), "team": a, "name": "Dining Room", "parent": None},
            )
            three_seaters = uuid.uuid4()
            await conn.execute(
                sa.text(insert_category),
                {"id": three_seaters, "team": a, "name": "Three-seaters", "parent": sofas},
            )
            # A sub-category's name is unique under its own parent only.
            await conn.execute(
                sa.text(insert_category),
                {"id": uuid.uuid4(), "team": a, "name": "Three-seaters", "parent": dining},
            )
            await conn.execute(
                sa.text(
                    "UPDATE skus SET subcategory_id = :sub, sell_multiple = 2, "
                    "min_sell_qty = 4 WHERE id = :id"
                ),
                {"sub": three_seaters, "id": skus["sofa1"]},
            )
        await refused(insert_category, id=uuid.uuid4(), team=a, name="three-SEATERS", parent=sofas)
        # The sub-category must belong to the SKU's category, and needs one.
        await refused(
            "UPDATE skus SET subcategory_id = :sub WHERE id = :id",
            sub=three_seaters,
            id=skus["dining"],
        )
        await refused(
            "UPDATE skus SET subcategory_id = :sub WHERE id = :id",
            sub=three_seaters,
            id=skus["none"],
        )
        # Another team's category or material cannot be linked.
        await refused("UPDATE skus SET category_id = :cat WHERE id = :id", cat=sofas, id=skus["b"])
        await refused(
            "INSERT INTO sku_materials (id, team_id, sku_id, material_id, position, created_at, "
            "updated_at) SELECT gen_random_uuid(), :b, :sku, id, 0, now(), now() FROM materials "
            "WHERE team_id = :a LIMIT 1",
            a=a,
            b=b,
            sku=skus["b"],
        )
        await refused("UPDATE sku_categories SET parent_id = id WHERE id = :id", id=three_seaters)

        migrate(url, PREVIOUS, command="downgrade")
        async with admin.connect() as conn:
            assert not await conn.scalar(
                sa.text("""SELECT count(*) FROM information_schema.tables
                    WHERE table_name IN ('sku_categories', 'materials', 'sku_materials')""")
            )
            assert not await conn.scalar(
                sa.text("""SELECT count(*) FROM information_schema.columns
                    WHERE (table_name = 'skus' AND column_name IN ('category_id', 'subcategory_id',
                        'colour_name', 'main_material_id', 'sell_multiple', 'min_sell_qty',
                        'order_up_to', 'do_not_reorder'))
                       OR (table_name = 'sku_supplier_prices'
                           AND column_name IN ('min_order_qty', 'pack_multiple'))""")
            )
            assert (
                await conn.scalar(
                    sa.text("SELECT category FROM skus WHERE id = :id"), {"id": skus["sofa3"]}
                )
                == "Sofas"
            )
        migrate(url, LISTS)
        async with admin.connect() as conn:
            assert (
                await conn.scalar(
                    sa.text("SELECT count(*) FROM skus WHERE category_id IS NOT NULL")
                )
                == 6
            )
    finally:
        await admin.dispose()


async def test_unicode_case_folding_follows_postgres(second_postgres_url: str) -> None:
    """Names Python and Postgres lower-case differently ("DİNİNG ROOM") are grouped, linked
    and kept unique by Postgres alone: no SKU loses its shop section and no duplicate
    category aborts the release."""
    url = second_postgres_url
    migrate(url, PREVIOUS)
    admin = create_async_engine(url, poolclass=NullPool)
    alone, collide = uuid.uuid4(), uuid.uuid4()
    try:
        async with admin.begin() as conn:
            for team in (alone, collide):
                await conn.execute(
                    sa.text("""INSERT INTO teams(id,name,slug,status,created_at,updated_at)
                        VALUES (:id,'Synthetic unicode team',:slug,'active',now(),now())"""),
                    {"id": team, "slug": f"unicode-{team.hex}"},
                )
            await _insert_sku(conn, alone, "DİNİNG ROOM", "-", "Lone", "Lone Table")
            await _insert_sku(conn, collide, "DİNİNG ROOM", "-", "Pair A", "Pair Table")
            await _insert_sku(conn, collide, "Dining Room", "-", "Pair B", "Pair Table")
            await _insert_sku(conn, collide, "Σοφάς", "-", "Sigma", "Sigma Sofa")
            # What the shop feed before 120 made of each SKU, by its own SQL expression.
            before = dict(
                (
                    await conn.execute(
                        sa.text("""SELECT id, CASE lower(trim(category))
                                WHEN 'dining room' THEN 'dining-room' END
                            FROM skus WHERE team_id IN (:a, :b)"""),
                        {"a": alone, "b": collide},
                    )
                ).all()
            )
            groups = await conn.scalar(
                sa.text("""SELECT count(DISTINCT (team_id, lower(btrim(category))))
                    FROM skus WHERE team_id IN (:a, :b)"""),
                {"a": alone, "b": collide},
            )

        migrate(url, LISTS)
        async with admin.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text("""SELECT s.id, s.category, c.name, c.shop_category
                        FROM skus s LEFT JOIN sku_categories c ON c.id = s.category_id
                        WHERE s.team_id IN (:a, :b)"""),
                    {"a": alone, "b": collide},
                )
            ).all()
            assert len(rows) == 4
            for sku, category, name, shop in rows:
                assert name is not None and category == name
                assert shop == before[sku]
            assert (
                await conn.scalar(
                    sa.text("SELECT count(*) FROM sku_categories WHERE team_id IN (:a, :b)"),
                    {"a": alone, "b": collide},
                )
                == groups
            )
    finally:
        await admin.dispose()
