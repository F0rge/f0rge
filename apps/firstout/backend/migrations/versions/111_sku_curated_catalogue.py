"""Store SKU details, curated membership, and immutable gallery references.

Revision ID: 111_sku_curated_catalogue
Revises: 110_sku_storefront_hidden
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "111_sku_curated_catalogue"
down_revision = "110_sku_storefront_hidden"
branch_labels = None
depends_on = None

DIMENSIONS = ("width_cm", "depth_cm", "height_cm", "diameter_cm")


def upgrade() -> None:
    for dimension in DIMENSIONS:
        op.add_column("skus", sa.Column(dimension, sa.Numeric(8, 2)))
    op.add_column("skus", sa.Column("notes", sa.Text()))
    op.add_column("skus", sa.Column("piece_count", sa.Integer()))
    op.add_column("skus", sa.Column("gallery_photo_keys", ARRAY(sa.Text())))
    op.add_column(
        "skus",
        sa.Column(
            "storefront_catalogue_selected", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "teams",
        sa.Column(
            "storefront_curated_catalogue", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_check_constraint(
        "ck_skus_positive_dimensions",
        "skus",
        "width_cm > 0 AND depth_cm > 0 AND height_cm > 0 AND diameter_cm > 0",
    )
    op.create_check_constraint("ck_skus_positive_piece_count", "skus", "piece_count >= 1")
    op.create_check_constraint(
        "ck_skus_three_gallery_photos",
        "skus",
        "cardinality(gallery_photo_keys) = 3 AND array_position(gallery_photo_keys, NULL) IS NULL",
    )


def downgrade() -> None:
    op.drop_column("teams", "storefront_curated_catalogue")
    op.drop_constraint("ck_skus_three_gallery_photos", "skus", type_="check")
    op.drop_constraint("ck_skus_positive_piece_count", "skus", type_="check")
    op.drop_constraint("ck_skus_positive_dimensions", "skus", type_="check")
    for column in ("storefront_catalogue_selected", "gallery_photo_keys", "piece_count", "notes"):
        op.drop_column("skus", column)
    for dimension in DIMENSIONS:
        op.drop_column("skus", dimension)
