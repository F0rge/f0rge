from __future__ import annotations

import re
import uuid
from typing import Optional

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.document_sequence import DOCUMENT_TYPE_DEFAULTS, DocumentSequenceCRUD
from app.crud.user import TeamCRUD
from app.models.document_sequence import DocumentSequence
from f0rge_core.exceptions import NotFoundError, ValidationError

_PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9]{1,8}$")


class DocumentNumberingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.crud = DocumentSequenceCRUD(db)
        self.team_crud = TeamCRUD(db)

    async def resolve_team_id(self, team_id: Optional[uuid.UUID] = None) -> uuid.UUID:
        if team_id is not None:
            return team_id
        team = await self.team_crud.get_first()
        if team is None:
            raise NotFoundError("Team not found")
        return team.id

    async def ensure_all_for_team(self, team_id: uuid.UUID) -> None:
        for doc_type, (prefix, padding) in DOCUMENT_TYPE_DEFAULTS.items():
            stmt = (
                insert(DocumentSequence)
                .values(
                    team_id=team_id,
                    doc_type=doc_type,
                    prefix=prefix,
                    padding=padding,
                    next_value=1,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        DocumentSequence.team_id,
                        DocumentSequence.doc_type,
                    ]
                )
            )
            await self.db.execute(stmt)

    async def allocate(
        self,
        doc_type: str,
        *,
        team_id: Optional[uuid.UUID] = None,
    ) -> str:
        if doc_type not in DOCUMENT_TYPE_DEFAULTS:
            raise ValidationError(f"Unknown document type: {doc_type}")

        resolved_team_id = await self.resolve_team_id(team_id)
        await self.ensure_all_for_team(resolved_team_id)

        result = await self.db.execute(
            text(
                """
                UPDATE document_sequences
                SET next_value = next_value + 1,
                    updated_at = NOW()
                WHERE team_id = :team_id AND doc_type = :doc_type
                RETURNING next_value - 1 AS seq, prefix, padding
                """
            ),
            {"team_id": resolved_team_id, "doc_type": doc_type},
        )
        row = result.one()
        return f"{row.prefix}-{int(row.seq):0{int(row.padding)}d}"

    @staticmethod
    def normalize_prefix(prefix: str) -> str:
        cleaned = prefix.strip()
        if not _PREFIX_PATTERN.fullmatch(cleaned):
            raise ValidationError("prefix must be 1-8 alphanumeric characters")
        return cleaned.upper()
