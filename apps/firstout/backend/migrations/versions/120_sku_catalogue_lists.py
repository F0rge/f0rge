"""Managed categories and materials, colour names, selling rules and reorder settings.

Revision ID: 120_sku_catalogue_lists
Revises: 119_sku_second_detail_photo

Additive (P-020): ``skus.category`` and ``skus.fabric`` stay. Per team, the backfill
creates one category per distinct SKU category (case-insensitive, most frequent spelling
wins) and per ``category_account_maps`` name, links the SKUs and rewrites their category
text to that spelling; seeds the default materials and guesses each SKU's main material
and colour name from its own text, leaving null whenever the guess is not clear.

The backfill leaves ``updated_at`` alone: nothing it writes reaches the shop feed (the
shop section is still keyed by the lower-cased name, which the rewrite does not change).
Downgrade drops the new tables and columns; the category text keeps its canonical spelling.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from collections import Counter
from typing import Optional

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

from app.models.catalogue_list import DEFAULT_MATERIALS

revision = "120_sku_catalogue_lists"
down_revision = "119_sku_second_detail_photo"
branch_labels = None
depends_on = None

_TENANT_VALUE = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
_NEW_TABLES = ("sku_categories", "materials", "sku_materials")
_FAMILIES = "'fabric', 'leather', 'wood', 'stone', 'metal', 'glass', 'woven', 'other'"

# Frozen copy of ops_commerce.SHOP_CATEGORIES at this revision: lower(name) -> shop section.
_SHOP_SECTIONS = {
    "sofas": "sofas-armchairs",
    "armchairs": "sofas-armchairs",
    "dining room": "dining-room",
    "bedroom": "bedroom",
    "coffee and lamp tables": "coffee-console-tables",
    "consoles and tv units": "coffee-console-tables",
}

# A colour name is only kept when it contains one of these words. Frozen for this backfill.
_COLOUR_WORDS = re.compile(
    r"\b(?:navy|blue|charcoal|gunmetal|gr[ae]y|dove|taupe|latte|moc[ch]a|rust|terracotta|red"
    r"|beige|natural|brown|yellow|mustard|green|sage|olive|pink|blush|ivory|cream|white|black"
    r"|sand|oat|stone|camel|tan|cognac|chocolate|ochre|emerald|teal|burgundy|plum|gold|silver"
    r"|copper|bronze|ink)\b"
)
_PLACEHOLDER = re.compile(r"^(?:-*|unspecified|csv:.*)$")
_WORD = re.compile(r"^[a-z][a-z'-]*$")


def fold(text: Optional[str]) -> str:
    """Lower-case without accents: "Bouclé" and "boucle" compare equal."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower().strip()


_MATERIAL_PATTERNS = [
    (name, re.compile(rf"\b{re.escape(fold(name))}\b")) for name, _family in DEFAULT_MATERIALS
]


def materials_in(text: Optional[str]) -> set[str]:
    folded = fold(text)
    return {name for name, pattern in _MATERIAL_PATTERNS if pattern.search(folded)}


def main_material(
    fabric: Optional[str], design: Optional[str], name: Optional[str]
) -> Optional[str]:
    """The first of fabric, design and name that mentions a material decides; two differing
    materials in that text ("Walnut & Brass") are ambiguous and give none."""
    for text in (fabric, design, name):
        found = materials_in(text)
        if found:
            return found.pop() if len(found) == 1 else None
    return None


def colour_name(fabric: Optional[str], material: Optional[str]) -> Optional[str]:
    """``fabric`` minus the main material word, when that leaves one to three plain words
    with a recognisable colour in them. A null is better than a wrong name."""
    folded = fold(fabric)
    if _PLACEHOLDER.match(folded):
        return None
    if material:
        folded = re.sub(rf"\b{re.escape(fold(material))}\b", " ", folded)
    words = folded.split()
    if not 1 <= len(words) <= 3 or not all(_WORD.match(word) for word in words):
        return None
    remainder = " ".join(words)
    if materials_in(remainder) or not _COLOUR_WORDS.search(remainder):
        return None
    result = " ".join(word.capitalize() for word in words)
    return result if len(result) <= 64 else None


def _canonical_categories(sku_spellings: list[str], map_names: list[str]) -> dict[str, str]:
    """lower(name) -> canonical spelling: the most frequent SKU spelling (ties: the
    alphabetically first), else the account map's spelling."""
    counts: dict[str, Counter[str]] = {}
    for spelling in sku_spellings:
        counts.setdefault(spelling.lower(), Counter())[spelling] += 1
    canonical = {
        key: min(counter.items(), key=lambda item: (-item[1], item[0]))[0]
        for key, counter in counts.items()
    }
    for name in sorted(map_names):
        canonical.setdefault(name.lower(), name)
    return canonical


def _team_column() -> sa.Column:
    return sa.Column(
        "team_id",
        UUID(as_uuid=True),
        sa.ForeignKey("teams.id", ondelete="RESTRICT"),
        nullable=False,
        server_default=sa.text(_TENANT_VALUE),
    )


def _timestamps() -> list[sa.Column]:
    # Naive UTC, like every TimestampMixin table.
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    ]


def _isolate(table: str) -> None:
    op.create_index(f"ix_{table}_team_id", table, ["team_id"])
    predicate = f"team_id = {_TENANT_VALUE}"
    op.execute(
        f"CREATE POLICY organisation_isolation ON {table} FOR ALL USING ({predicate}) WITH CHECK ({predicate})"
    )
    op.execute(f"""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM pg_class WHERE oid='public.roles'::regclass
                   AND relrowsecurity AND relforcerowsecurity) THEN
            ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
            ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
        END IF;
    END $$""")


def _create_tables() -> None:
    op.create_table(
        "sku_categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _team_column(),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True)),
        sa.Column("shop_category", sa.String(64)),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("archived_at", sa.DateTime()),
        *_timestamps(),
        sa.UniqueConstraint("team_id", "id", name="uq_sku_categories_team_id_id"),
        sa.UniqueConstraint(
            "team_id", "id", "parent_id", name="uq_sku_categories_team_id_id_parent"
        ),
        sa.ForeignKeyConstraint(
            ["team_id", "parent_id"],
            ["sku_categories.team_id", "sku_categories.id"],
            name="fk_sku_categories_parent_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("parent_id <> id", name="ck_sku_categories_not_own_parent"),
        sa.CheckConstraint(
            "shop_category IS NULL OR parent_id IS NULL", name="ck_sku_categories_shop_top_level"
        ),
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_sku_categories_top_name_active_lower ON sku_categories "
        "(team_id, lower(name)) WHERE parent_id IS NULL AND NOT is_archived"
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_sku_categories_sub_name_active_lower ON sku_categories "
        "(team_id, parent_id, lower(name)) WHERE parent_id IS NOT NULL AND NOT is_archived"
    )

    op.create_table(
        "materials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _team_column(),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("family", sa.String(16), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("archived_at", sa.DateTime()),
        *_timestamps(),
        sa.UniqueConstraint("team_id", "id", name="uq_materials_team_id_id"),
        sa.CheckConstraint(f"family IN ({_FAMILIES})", name="ck_materials_family"),
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_materials_name_active_lower ON materials "
        "(team_id, lower(name)) WHERE NOT is_archived"
    )

    # 080 gave skus a (team_id, id) key as tenant_ref_*; create one only where it is missing.
    if not any(
        item["column_names"] == ["team_id", "id"]
        for item in sa.inspect(op.get_bind()).get_unique_constraints("skus")
    ):
        op.create_unique_constraint("uq_skus_team_id_id", "skus", ["team_id", "id"])
    op.create_table(
        "sku_materials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _team_column(),
        sa.Column("sku_id", UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("team_id", "id", name="uq_sku_materials_team_id_id"),
        sa.UniqueConstraint(
            "team_id", "sku_id", "material_id", name="uq_sku_materials_sku_material"
        ),
        # A plain FK ignores RLS: both rows must belong to the link's organisation.
        sa.ForeignKeyConstraint(
            ["team_id", "sku_id"],
            ["skus.team_id", "skus.id"],
            name="fk_sku_materials_sku_tenant",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["team_id", "material_id"],
            ["materials.team_id", "materials.id"],
            name="fk_sku_materials_material_tenant",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("position >= 0", name="ck_sku_materials_position"),
    )
    for table in _NEW_TABLES:
        _isolate(table)


def _add_columns() -> None:
    for column in (
        sa.Column("category_id", UUID(as_uuid=True)),
        sa.Column("subcategory_id", UUID(as_uuid=True)),
        sa.Column("colour_name", sa.String(64)),
        sa.Column("main_material_id", UUID(as_uuid=True)),
        sa.Column("sell_multiple", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("min_sell_qty", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("order_up_to", sa.Integer()),
        sa.Column("do_not_reorder", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    ):
        op.add_column("skus", column)
    op.create_foreign_key(
        "fk_skus_category_tenant",
        "skus",
        "sku_categories",
        ["team_id", "category_id"],
        ["team_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_skus_subcategory_tenant",
        "skus",
        "sku_categories",
        ["team_id", "subcategory_id", "category_id"],
        ["team_id", "id", "parent_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_skus_main_material_tenant",
        "skus",
        "materials",
        ["team_id", "main_material_id"],
        ["team_id", "id"],
        ondelete="RESTRICT",
    )
    for name, condition in (
        ("ck_skus_subcategory_needs_category", "subcategory_id IS NULL OR category_id IS NOT NULL"),
        ("ck_skus_sell_multiple", "sell_multiple >= 1"),
        # CASE: a zero multiple must fail the check, not raise division by zero.
        (
            "ck_skus_min_sell_qty",
            "min_sell_qty >= 1 AND CASE WHEN sell_multiple >= 1 "
            "THEN min_sell_qty % sell_multiple = 0 ELSE false END",
        ),
        ("ck_skus_order_up_to", "order_up_to >= 1"),
    ):
        op.create_check_constraint(name, "skus", condition)

    op.add_column("sku_supplier_prices", sa.Column("min_order_qty", sa.Integer()))
    op.add_column("sku_supplier_prices", sa.Column("pack_multiple", sa.Integer()))
    op.create_check_constraint(
        "ck_sku_supplier_prices_min_order_qty", "sku_supplier_prices", "min_order_qty >= 1"
    )
    op.create_check_constraint(
        "ck_sku_supplier_prices_pack_multiple", "sku_supplier_prices", "pack_multiple >= 1"
    )


def _backfill_team(bind: sa.Connection, team: uuid.UUID) -> None:
    spellings = (
        bind.execute(
            sa.text("""SELECT btrim(category) FROM skus
            WHERE team_id = :team AND btrim(coalesce(category, '')) <> ''"""),
            {"team": team},
        )
        .scalars()
        .all()
    )
    map_names = (
        bind.execute(
            sa.text("""SELECT btrim(category) FROM category_account_maps
            WHERE team_id = :team AND btrim(category) <> ''"""),
            {"team": team},
        )
        .scalars()
        .all()
    )
    for key, name in _canonical_categories(spellings, map_names).items():
        category_id = uuid.uuid4()
        bind.execute(
            sa.text("""INSERT INTO sku_categories
                (id, team_id, name, shop_category, created_at, updated_at)
                VALUES (:id, :team, :name, :shop, timezone('utc', now()), timezone('utc', now()))"""),
            {"id": category_id, "team": team, "name": name, "shop": _SHOP_SECTIONS.get(key)},
        )
        bind.execute(
            sa.text("""UPDATE skus SET category_id = :id, category = :name
                WHERE team_id = :team AND lower(btrim(category)) = :key"""),
            {"id": category_id, "name": name, "team": team, "key": key},
        )

    material_ids = {}
    for name, family in DEFAULT_MATERIALS:
        material_ids[name] = uuid.uuid4()
        bind.execute(
            sa.text("""INSERT INTO materials (id, team_id, name, family, created_at, updated_at)
                VALUES (:id, :team, :name, :family, timezone('utc', now()), timezone('utc', now()))"""),
            {"id": material_ids[name], "team": team, "name": name, "family": family},
        )

    rows = bind.execute(
        sa.text("SELECT id, fabric, design, name FROM skus WHERE team_id = :team"),
        {"team": team},
    ).all()
    updates = []
    for row in rows:
        material = main_material(row.fabric, row.design, row.name)
        colour = colour_name(row.fabric, material)
        if material or colour:
            updates.append(
                {
                    "id": row.id,
                    "team": team,
                    "material": material_ids.get(material),
                    "colour": colour,
                }
            )
    if updates:
        bind.execute(
            sa.text("""UPDATE skus SET main_material_id = :material, colour_name = :colour
                WHERE id = :id AND team_id = :team"""),
            updates,
        )


def upgrade() -> None:
    _create_tables()
    _add_columns()
    bind = op.get_bind()
    # Forced RLS hides every row from the non-superuser owner unless the tenant is set;
    # every statement also filters by team, since without forced RLS the policy does not narrow.
    for team in bind.execute(sa.text("SELECT id FROM teams ORDER BY id")).scalars().all():
        bind.execute(
            sa.text("SELECT set_config('app.tenant_id', :team, true)"), {"team": str(team)}
        )
        _backfill_team(bind, team)
    bind.execute(sa.text("SELECT set_config('app.tenant_id', '', true)"))


def downgrade() -> None:
    for name in ("ck_sku_supplier_prices_pack_multiple", "ck_sku_supplier_prices_min_order_qty"):
        op.drop_constraint(name, "sku_supplier_prices", type_="check")
    op.drop_column("sku_supplier_prices", "pack_multiple")
    op.drop_column("sku_supplier_prices", "min_order_qty")
    for name in (
        "ck_skus_order_up_to",
        "ck_skus_min_sell_qty",
        "ck_skus_sell_multiple",
        "ck_skus_subcategory_needs_category",
    ):
        op.drop_constraint(name, "skus", type_="check")
    for name in (
        "fk_skus_main_material_tenant",
        "fk_skus_subcategory_tenant",
        "fk_skus_category_tenant",
    ):
        op.drop_constraint(name, "skus", type_="foreignkey")
    for column in (
        "do_not_reorder",
        "order_up_to",
        "min_sell_qty",
        "sell_multiple",
        "main_material_id",
        "colour_name",
        "subcategory_id",
        "category_id",
    ):
        op.drop_column("skus", column)
    op.drop_table("sku_materials")
    op.execute("ALTER TABLE skus DROP CONSTRAINT IF EXISTS uq_skus_team_id_id")
    op.drop_table("materials")
    op.drop_table("sku_categories")
