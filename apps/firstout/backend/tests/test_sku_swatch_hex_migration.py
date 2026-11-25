"""117 colours every team's SKUs from their text, even under forced RLS on a non-superuser owner."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.test_fractional_inventory_migration import migrate

pytestmark = pytest.mark.no_db
PREVIOUS = "116_sku_detail_photo"
SWATCH = "117_sku_swatch_hex"

_spec = importlib.util.spec_from_file_location(
    "migration_117",
    Path(__file__).resolve().parents[1] / "migrations" / "versions" / f"{SWATCH}.py",
)
assert _spec and _spec.loader
_migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_migration)
sku_swatch = _migration.sku_swatch

# (fabric, design, name) -> expected hex, from real catalogue naming styles.
CASES = [
    (("", "", "Eva H-Board RoseGld KS 206-172cm"), "#b88c80"),
    (("", "", "Lotus Coffee Table Brushed Gold 120-100-39 cm"), "#b09a6c"),
    (("", "", "Amahle Dining Chair Ink Blue -Silver Frame"), "#2f3d5c"),
    (("", "", "Nandi Armchair Gold Legs & Black Fabric"), "#1e1e1e"),
    (("", "", "Casablanca D-Chr Slv S-S Grey PU"), "#8c8b88"),
    (("", "", "Kinita C-Table Gold S-S 120x60x40"), "#b8955a"),
    (("", "", "Cascais Rd. D Tbl Wht - Grey 150 x 74"), "#f1efea"),
    (("", "", "Avanzi L-Shape Sofa Gunmetal Grey"), "#4d5054"),
    (("", "", "Biles Swivel Chr Fab 88-88-82cm"), None),
    (("Velvet Navy", "Alexa Grey", "Alexa White"), "#27314a"),
    (("Solo 111", "Hathaway Taupe", "Hathaway Black"), "#8c7f70"),
]


@pytest.mark.parametrize(("fields", "expected"), CASES)
def test_swatch_rule(fields: tuple[str, str, str], expected: str) -> None:
    assert sku_swatch(*fields) == expected


async def test_backfill_reaches_each_team_under_forced_rls(second_postgres_url: str) -> None:
    url = second_postgres_url
    migrate(url, PREVIOUS)
    admin = create_async_engine(url, poolclass=NullPool)
    role = "swatch_migration_owner_" + uuid.uuid4().hex[:10]
    password = "synthetic-" + uuid.uuid4().hex
    seeds = {
        "Francoise Swivel Armchair Grey": "#8c8b88",
        "Lotus Coffee Table Brushed Gold": "#b09a6c",
        "Romero Console 105x40x77cm": None,
    }
    teams = [uuid.uuid4(), uuid.uuid4()]
    try:
        async with admin.begin() as conn:
            for team in teams:
                await conn.execute(
                    sa.text("""INSERT INTO teams(id,name,slug,status,created_at,updated_at)
                        VALUES (:id,'Synthetic swatch team',:slug,'active',now(),now())"""),
                    {"id": team, "slug": f"swatch-{team.hex}"},
                )
                for name in seeds:
                    ref = "SW-" + uuid.uuid4().hex[:10]
                    await conn.execute(
                        sa.text("""INSERT INTO skus(id,team_id,our_ref,our_barcode,name,design,
                            fabric,created_at,updated_at)
                            VALUES (:id,:team,:ref,:ref,:name,:ref,'',
                            '2026-01-01','2026-01-01')"""),
                        {"id": uuid.uuid4(), "team": team, "ref": ref, "name": name},
                    )
        # The release migrates as the table owner, not a superuser, with RLS forced.
        async with admin.begin() as conn:
            await conn.execute(
                sa.text(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
            )
            await conn.execute(sa.text(f"GRANT CREATE, USAGE ON SCHEMA public TO {role}"))
            await conn.execute(sa.text(f"GRANT ALL ON ALL TABLES IN SCHEMA public TO {role}"))
            for table in ("skus", "alembic_version"):
                await conn.execute(sa.text(f"ALTER TABLE {table} OWNER TO {role}"))
            await conn.execute(sa.text("ALTER TABLE skus ENABLE ROW LEVEL SECURITY"))
            await conn.execute(sa.text("ALTER TABLE skus FORCE ROW LEVEL SECURITY"))

        owner_url = make_url(url).set(username=role, password=password)
        migrate(owner_url.render_as_string(hide_password=False), SWATCH)

        async with admin.connect() as conn:
            rows = (
                await conn.execute(
                    sa.text("SELECT team_id, name, swatch_hex, updated_at > created_at FROM skus")
                )
            ).all()
        assert sorted(rows) == sorted(
            (team, name, hex_, hex_ is not None) for team in teams for name, hex_ in seeds.items()
        )

        for bad in ("#ABCDEF", "#abc", "grey"):
            with pytest.raises(IntegrityError):
                async with admin.begin() as conn:
                    await conn.execute(sa.text("UPDATE skus SET swatch_hex = :hex"), {"hex": bad})

        migrate(url, PREVIOUS, command="downgrade")
        async with admin.connect() as conn:
            assert not await conn.scalar(
                sa.text("""SELECT count(*) FROM information_schema.columns
                    WHERE table_name = 'skus' AND column_name = 'swatch_hex'""")
            )
    finally:
        await admin.dispose()
