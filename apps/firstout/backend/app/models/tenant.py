"""Explicit tenant ownership and per-tenant natural-key uniqueness for domain rows."""

from __future__ import annotations

import uuid

from f0rge_db.organisation import current_tenant_id
from sqlalchemy import ForeignKey, Index, Table, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class TenantOwnedMixin:
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("teams.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        default=current_tenant_id,
        server_default=text("NULLIF(current_setting('app.tenant_id', true), '')::uuid"),
    )

    @classmethod
    def __table_cls__(cls, *args, **kwargs):
        """Scope every natural key; UUID primary keys remain globally unique.

        Keeping the rule here also covers future tenant models. Existing index
        names/options (including partial predicates) are retained.
        """
        table = Table(*args, **kwargs)
        for constraint in list(table.constraints):
            if isinstance(constraint, UniqueConstraint) and "team_id" not in constraint.columns:
                columns = [column.name for column in constraint.columns]
                table.constraints.remove(constraint)
                table.append_constraint(UniqueConstraint("team_id", *columns, name=constraint.name))
        for index in list(table.indexes):
            if index.unique and "team_id" not in index.columns:
                table.indexes.remove(index)
                Index(index.name, table.c.team_id, *index.expressions, unique=True, **index.kwargs)
        return table
