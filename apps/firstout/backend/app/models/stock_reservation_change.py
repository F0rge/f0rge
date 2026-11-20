from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DDL, DateTime, PrimaryKeyConstraint, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.stock_reservation import StockReservation
from app.models.tenant import TenantOwnedMixin

# Keep in step with migrations/versions/101_stock_reservation_changes.py. Maintained by the
# database so no code path can release, expire or move a reservation without leaving a mark.
TRIGGER_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION mark_stock_reservation_change() RETURNS trigger AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        INSERT INTO stock_reservation_changes (team_id, sku_id, changed_at)
        VALUES (OLD.team_id, OLD.sku_id, clock_timestamp())
        ON CONFLICT (team_id, sku_id) DO UPDATE SET changed_at = EXCLUDED.changed_at;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        INSERT INTO stock_reservation_changes (team_id, sku_id, changed_at)
        VALUES (NEW.team_id, NEW.sku_id, clock_timestamp())
        ON CONFLICT (team_id, sku_id) DO UPDATE SET changed_at = EXCLUDED.changed_at;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql
"""
TRIGGER_SQL = """
CREATE TRIGGER stock_reservations_mark_change
AFTER INSERT OR UPDATE OR DELETE ON stock_reservations
FOR EACH ROW EXECUTE FUNCTION mark_stock_reservation_change()
"""


class StockReservationChange(TenantOwnedMixin, Base):
    """When a SKU's reservations last changed; lets the ops feed version released stock."""

    __tablename__ = "stock_reservation_changes"

    sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    changed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (PrimaryKeyConstraint("team_id", "sku_id"),)


# create_all (tests) builds the trigger the migration installs in deployed databases.
event.listen(
    StockReservation.__table__,
    "after_create",
    DDL(TRIGGER_FUNCTION_SQL).execute_if(dialect="postgresql"),
)
event.listen(
    StockReservation.__table__, "after_create", DDL(TRIGGER_SQL).execute_if(dialect="postgresql")
)
