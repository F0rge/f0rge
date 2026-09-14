from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.exceptions import CommsSmtpFailedError
from app.models.comms_message import CommsChannel, CommsDocumentType, CommsProvider
from app.models.team_settings import TeamSettings
from app.schemas.comms import CommsSendRequest, CommsSendResponse
from app.services.comms.outbox import CommsOutboxService
from app.services.comms.smtp import load_smtp_config, send_message
from app.services.invoices import InvoiceService
from f0rge_core.exceptions import ConflictError, NotFoundError, ValidationError


class CommsSendService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.outbox = CommsOutboxService(db)
        self.invoices = InvoiceService(db)
        self.settings_crud = TeamSettingsCRUD(db)
        self.team_crud = TeamCRUD(db)

    async def send_invoice(
        self,
        invoice_id: uuid.UUID,
        data: CommsSendRequest,
        actor_user_id: uuid.UUID,
    ) -> CommsSendResponse:
        if data.channel != "email":
            raise ValidationError("channel must be email")
        pdf_bytes, filename, invoice = await self.invoices.build_pdf_bytes(invoice_id)
        to_address = (invoice.customer.email or "").strip()
        if not to_address:
            raise ConflictError("Customer has no email")
        settings = await self._team_settings()
        shop = (settings.trading_name or settings.legal_name or "Vellano").strip()
        due = invoice.due_date.isoformat() if invoice.due_date else None
        subject = f"{shop} tax invoice {invoice.invoice_number}"
        lines = [
            f"{shop} tax invoice {invoice.invoice_number}.",
            f"Total inc VAT: {invoice.total_inc_vat:.2f}.",
        ]
        if due:
            lines.append(f"Due: {due}.")
        return await self._send_smtp(
            document_type=CommsDocumentType.INVOICE,
            document_id=invoice.id,
            to_address=to_address,
            actor_user_id=actor_user_id,
            settings=settings,
            subject=subject,
            body_text=" ".join(lines),
            pdf_bytes=pdf_bytes,
            pdf_filename=filename,
        )

    async def _send_smtp(
        self,
        *,
        document_type: CommsDocumentType,
        document_id: uuid.UUID,
        to_address: str,
        actor_user_id: uuid.UUID,
        settings: TeamSettings,
        subject: str,
        body_text: str,
        pdf_bytes: bytes,
        pdf_filename: str,
    ) -> CommsSendResponse:
        config = load_smtp_config(settings)
        from_identity = config.from_address
        row = await self.outbox.enqueue(
            channel=CommsChannel.EMAIL,
            provider=CommsProvider.SMTP,
            document_type=document_type,
            document_id=document_id,
            to_address=to_address,
            actor_user_id=actor_user_id,
            from_identity=from_identity,
            body_preview=subject,
        )
        try:
            provider_id = await send_message(
                config,
                to=to_address,
                subject=subject,
                body_text=body_text,
                pdf_bytes=pdf_bytes,
                pdf_filename=pdf_filename,
            )
        except CommsSmtpFailedError as exc:
            await self.outbox.mark_failed(row.id, exc.message)
            raise
        sent = await self.outbox.mark_sent(
            row.id,
            from_identity=from_identity,
            provider_message_id=provider_id,
        )
        return CommsSendResponse(
            id=sent.id,
            status=sent.status.value,
            channel=sent.channel.value,
            provider=sent.provider.value,
            mode="smtp",
        )

    async def _team_settings(self) -> TeamSettings:
        team = await self.team_crud.get_first()
        if team is None:
            raise NotFoundError("Team not found")
        return await self.settings_crud.get_or_create_for_team(team.id)
