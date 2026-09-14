from __future__ import annotations

import uuid
from typing import Optional
from urllib.parse import quote

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.team_settings import TeamSettingsCRUD
from app.crud.user import TeamCRUD
from app.exceptions import CommsSmtpFailedError
from app.models.comms_message import CommsChannel, CommsDocumentType, CommsProvider
from app.models.layby import LaybyStatus
from app.models.team_settings import TeamSettings
from app.schemas.comms import CommsSendRequest, CommsSendResponse
from app.services.comms.outbox import CommsOutboxService
from app.services.comms.phone import to_whatsapp_e164
from app.services.comms.smtp import load_smtp_config, send_message
from app.services.comms.whatsapp import (
    load_whatsapp_cloud,
    send_cloud_document,
    wa_configured,
)
from app.services.credit_notes import CreditNoteService
from app.services.invoices import InvoiceService
from app.services.laybys import LaybysService
from f0rge_core.exceptions import (
    ConflictError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)


class CommsSendService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.outbox = CommsOutboxService(db)
        self.invoices = InvoiceService(db)
        self.credit_notes = CreditNoteService(db)
        self.laybys = LaybysService(db)
        self.settings_crud = TeamSettingsCRUD(db)
        self.team_crud = TeamCRUD(db)

    async def send_invoice(
        self,
        invoice_id: uuid.UUID,
        data: CommsSendRequest,
        actor_user_id: uuid.UUID,
    ) -> CommsSendResponse:
        pdf_bytes, filename, invoice = await self.invoices.build_pdf_bytes(invoice_id)
        settings = await self._team_settings()
        shop = (settings.trading_name or settings.legal_name or "Vellano").strip()
        if data.channel == "whatsapp":
            return await self._send_whatsapp(
                document_type=CommsDocumentType.INVOICE,
                document_id=invoice.id,
                phone=invoice.customer.phone if invoice.customer else None,
                actor_user_id=actor_user_id,
                text=f"{shop} tax invoice {invoice.invoice_number}",
                pdf_bytes=pdf_bytes,
                pdf_filename=filename,
                body_params=[invoice.invoice_number, f"{invoice.total_inc_vat:.2f}"],
                settings=settings,
            )
        if data.channel != "email":
            raise ValidationError("channel must be email or whatsapp")
        to_address = (invoice.customer.email or "").strip()
        if not to_address:
            raise ConflictError("Customer has no email")
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

    async def send_credit_note(
        self,
        credit_note_id: uuid.UUID,
        data: CommsSendRequest,
        actor_user_id: uuid.UUID,
    ) -> CommsSendResponse:
        pdf_bytes, filename, credit_note = await self.credit_notes.build_pdf_bytes(credit_note_id)
        customer = credit_note.invoice.customer
        settings = await self._team_settings()
        shop = (settings.trading_name or settings.legal_name or "Vellano").strip()
        if data.channel == "whatsapp":
            return await self._send_whatsapp(
                document_type=CommsDocumentType.CREDIT_NOTE,
                document_id=credit_note.id,
                phone=customer.phone if customer else None,
                actor_user_id=actor_user_id,
                text=f"{shop} credit note {credit_note.credit_note_number}",
                pdf_bytes=pdf_bytes,
                pdf_filename=filename,
                body_params=[
                    credit_note.credit_note_number,
                    f"{credit_note.total_inc_vat:.2f}",
                ],
                settings=settings,
            )
        if data.channel != "email":
            raise ValidationError("channel must be email or whatsapp")
        to_address = (customer.email or "").strip() if customer else ""
        if not to_address:
            raise ConflictError("Customer has no email")
        subject = f"{shop} credit note {credit_note.credit_note_number}"
        body = (
            f"{shop} credit note {credit_note.credit_note_number}. "
            f"Total inc VAT: {credit_note.total_inc_vat:.2f}."
        )
        return await self._send_smtp(
            document_type=CommsDocumentType.CREDIT_NOTE,
            document_id=credit_note.id,
            to_address=to_address,
            actor_user_id=actor_user_id,
            settings=settings,
            subject=subject,
            body_text=body,
            pdf_bytes=pdf_bytes,
            pdf_filename=filename,
        )

    async def send_layby(
        self,
        layby_id: uuid.UUID,
        data: CommsSendRequest,
        actor_user_id: uuid.UUID,
    ) -> CommsSendResponse:
        pdf_bytes, filename, layby = await self.laybys.build_pdf_bytes(layby_id)
        if layby.status == LaybyStatus.CANCELLED:
            raise ConflictError("Cannot send a cancelled layby")
        settings = await self._team_settings()
        shop = (settings.trading_name or settings.legal_name or "Vellano").strip()
        if data.channel == "whatsapp":
            balance = layby.total_inc_vat - layby.amount_paid
            return await self._send_whatsapp(
                document_type=CommsDocumentType.LAYBY,
                document_id=layby.id,
                phone=layby.customer.phone,
                actor_user_id=actor_user_id,
                text=f"{shop} layby {layby.layby_number}",
                pdf_bytes=pdf_bytes,
                pdf_filename=filename,
                body_params=[layby.layby_number, f"{balance:.2f}"],
                settings=settings,
            )
        if data.channel != "email":
            raise ValidationError("channel must be email or whatsapp")
        to_address = (layby.customer.email or "").strip()
        if not to_address:
            raise ConflictError("Customer has no email")
        subject = f"{shop} layby {layby.layby_number}"
        balance = layby.total_inc_vat - layby.amount_paid
        body = (
            f"{shop} layby {layby.layby_number}. "
            f"Paid {layby.amount_paid:.2f}. Balance {balance:.2f}. "
            f"Due {layby.due_date.isoformat()}."
        )
        return await self._send_smtp(
            document_type=CommsDocumentType.LAYBY,
            document_id=layby.id,
            to_address=to_address,
            actor_user_id=actor_user_id,
            settings=settings,
            subject=subject,
            body_text=body,
            pdf_bytes=pdf_bytes,
            pdf_filename=filename,
        )

    async def _send_whatsapp(
        self,
        *,
        document_type: CommsDocumentType,
        document_id: uuid.UUID,
        phone: Optional[str],
        actor_user_id: uuid.UUID,
        text: str,
        pdf_bytes: bytes,
        pdf_filename: str,
        body_params: list[str],
        settings: TeamSettings,
    ) -> CommsSendResponse:
        e164 = to_whatsapp_e164(phone)
        if not e164:
            raise ConflictError("Customer has no WhatsApp number")
        if wa_configured(settings):
            return await self._send_whatsapp_cloud(
                document_type=document_type,
                document_id=document_id,
                e164=e164,
                actor_user_id=actor_user_id,
                text=text,
                pdf_bytes=pdf_bytes,
                pdf_filename=pdf_filename,
                body_params=body_params,
                settings=settings,
            )
        return await self._send_whatsapp_click(
            document_type=document_type,
            document_id=document_id,
            e164=e164,
            actor_user_id=actor_user_id,
            text=text,
        )

    async def _send_whatsapp_click(
        self,
        *,
        document_type: CommsDocumentType,
        document_id: uuid.UUID,
        e164: str,
        actor_user_id: uuid.UUID,
        text: str,
    ) -> CommsSendResponse:
        digits = e164[1:]
        url = f"https://wa.me/{digits}?text={quote(text)}"
        row = await self.outbox.enqueue(
            channel=CommsChannel.WHATSAPP,
            provider=CommsProvider.WHATSAPP_CLICK,
            document_type=document_type,
            document_id=document_id,
            to_address=e164,
            actor_user_id=actor_user_id,
            from_identity="wa.me",
            body_preview=text,
        )
        opened = await self.outbox.mark_opened(row.id, from_identity="wa.me")
        return CommsSendResponse(
            id=opened.id,
            status=opened.status.value,
            channel=opened.channel.value,
            provider=opened.provider.value,
            mode="click",
            url=url,
        )

    async def _send_whatsapp_cloud(
        self,
        *,
        document_type: CommsDocumentType,
        document_id: uuid.UUID,
        e164: str,
        actor_user_id: uuid.UUID,
        text: str,
        pdf_bytes: bytes,
        pdf_filename: str,
        body_params: list[str],
        settings: TeamSettings,
    ) -> CommsSendResponse:
        config = load_whatsapp_cloud(settings)
        row = await self.outbox.enqueue(
            channel=CommsChannel.WHATSAPP,
            provider=CommsProvider.WHATSAPP_CLOUD,
            document_type=document_type,
            document_id=document_id,
            to_address=e164,
            actor_user_id=actor_user_id,
            from_identity=config.phone_number_id,
            body_preview=text,
        )
        try:
            provider_id = await send_cloud_document(
                config,
                to_e164=e164,
                body_params=body_params,
                pdf_bytes=pdf_bytes,
                pdf_filename=pdf_filename,
                caption=text,
            )
        except (ConflictError, ExternalServiceError) as exc:
            await self.outbox.mark_failed(row.id, exc.detail)
            raise
        sent = await self.outbox.mark_sent(
            row.id,
            from_identity=config.phone_number_id,
            provider_message_id=provider_id or None,
        )
        return CommsSendResponse(
            id=sent.id,
            status=sent.status.value,
            channel=sent.channel.value,
            provider=sent.provider.value,
            mode="cloud",
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
