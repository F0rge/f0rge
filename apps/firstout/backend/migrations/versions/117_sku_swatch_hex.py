"""Give each SKU an optional finish colour and backfill it from the SKU's own text.

Revision ID: 117_sku_swatch_hex
Revises: 116_sku_detail_photo
"""

from __future__ import annotations

import re
from typing import Optional

import sqlalchemy as sa
from alembic import op

revision = "117_sku_swatch_hex"
down_revision = "116_sku_detail_photo"
branch_labels = None
depends_on = None

_CHECK = "ck_skus_swatch_hex"

# Upholstery and body colours beat metal finishes: "Gold Legs & Black Fabric" is a black chair.
# Within a tier the colour written first wins, and the longest phrase wins at the same spot.
# Frozen copy for this backfill; staff edit the colour in Firstout from now on.
_COLOURS = (
    (r"ink blue", "#2f3d5c"),
    (r"navy", "#27314a"),
    (r"blue", "#4f6684"),
    (r"charcoal", "#3c3d3f"),
    (r"gunmetal", "#4d5054"),
    (r"gr[ae]y", "#8c8b88"),
    (r"dove", "#b5aea4"),
    (r"starry", "#6b6f78"),
    (r"taupe", "#8c7f70"),
    (r"latte", "#c3a98c"),
    (r"moc[ch]a", "#6b4f3f"),
    (r"rust", "#9a4e2f"),
    (r"yellow|mustard", "#c9a23a"),
    (r"green|sage|olive", "#5e6e55"),
    (r"pink|blush", "#d4b2aa"),
    (r"ivory|cream", "#ece5d6"),
    (r"white|wht", "#f1efea"),
    (r"black|blk", "#1e1e1e"),
    (r"marble", "#e4e0d8"),
    (r"mahog[ao]ny|mah", "#5a2e22"),
)
_FINISHES = (
    (r"rose ?go?ld", "#b88c80"),
    (r"brushed gold", "#b09a6c"),
    (r"gold|gld|gilded", "#b8955a"),
    (r"brass", "#a6894f"),
    (r"silver|silve|slv|sil|chrome|s-s|s-steel|stainless|alum(?:inium)?", "#b9bbbd"),
    (r"acrylic", "#dde3e4"),
)


def _tier(entries: tuple[tuple[str, str], ...]) -> list[tuple[re.Pattern[str], str]]:
    return [(re.compile(rf"\b(?:{pattern})\b"), hex_) for pattern, hex_ in entries]


_TIERS = (_tier(_COLOURS), _tier(_FINISHES))


def swatch_for(text: Optional[str]) -> Optional[str]:
    lowered = (text or "").lower()
    for tier in _TIERS:
        hits = [
            (match.start(), -len(match.group()), hex_)
            for pattern, hex_ in tier
            for match in pattern.finditer(lowered)
        ]
        if hits:
            return min(hits)[2]
    return None


def sku_swatch(fabric: Optional[str], design: Optional[str], name: Optional[str]) -> Optional[str]:
    for text in (fabric, design, name):
        found = swatch_for(text)
        if found:
            return found
    return None


def upgrade() -> None:
    op.add_column("skus", sa.Column("swatch_hex", sa.String(7), nullable=True))
    op.create_check_constraint(
        _CHECK, "skus", "swatch_hex IS NULL OR swatch_hex ~ '^#[0-9a-f]{6}$'"
    )
    bind = op.get_bind()
    # Forced RLS hides every row from the non-superuser owner unless the tenant is set.
    for team in bind.execute(sa.text("SELECT id FROM teams")).scalars().all():
        bind.execute(
            sa.text("SELECT set_config('app.tenant_id', :team, true)"), {"team": str(team)}
        )
        rows = bind.execute(
            sa.text("SELECT id, fabric, design, name FROM skus WHERE team_id = :team"),
            {"team": team},
        ).all()
        updates = [
            {"id": row.id, "team": team, "hex": hex_}
            for row in rows
            if (hex_ := sku_swatch(row.fabric, row.design, row.name))
        ]
        if updates:
            # Bump updated_at so the storefront feed revision moves for coloured SKUs.
            bind.execute(
                sa.text(
                    "UPDATE skus SET swatch_hex = :hex, updated_at = timezone('utc', now()) "
                    "WHERE id = :id AND team_id = :team"
                ),
                updates,
            )
    bind.execute(sa.text("SELECT set_config('app.tenant_id', '', true)"))


def downgrade() -> None:
    op.drop_constraint(_CHECK, "skus", type_="check")
    op.drop_column("skus", "swatch_hex")
