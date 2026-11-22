from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.models.team_settings import (
    DEFAULT_ADDRESS,
    DEFAULT_LEGAL_NAME,
    DEFAULT_VAT_NUMBER,
    TeamSettings,
)

SELLER_NAME = DEFAULT_LEGAL_NAME
SELLER_ADDRESS = DEFAULT_ADDRESS
SELLER_VAT_NUMBER = DEFAULT_VAT_NUMBER


@dataclass(frozen=True)
class SellerDetails:
    name: str
    address: str
    vat_number: str
    bank_name: Optional[str] = None
    bank_account: Optional[str] = None
    bank_branch_code: Optional[str] = None
    logo_bytes: Optional[bytes] = None
    trading_name: Optional[str] = None


def seller_details_from_settings(
    settings: TeamSettings,
    *,
    logo_bytes: Optional[bytes] = None,
) -> SellerDetails:
    return SellerDetails(
        name=settings.legal_name,
        address=settings.address,
        vat_number=settings.vat_number,
        bank_name=settings.bank_name,
        bank_account=settings.bank_account,
        bank_branch_code=settings.bank_branch_code,
        logo_bytes=logo_bytes,
        trading_name=settings.trading_name,
    )


def draw_seller_logo(
    pdf: canvas.Canvas,
    seller_details: SellerDetails,
    *,
    page_width: float,
    anchor_y: float,
) -> None:
    if not seller_details.logo_bytes:
        return
    try:
        from io import BytesIO

        from reportlab.lib.utils import ImageReader

        image = ImageReader(BytesIO(seller_details.logo_bytes))
        img_w, img_h = image.getSize()
        max_w = 35 * mm
        max_h = 20 * mm
        scale = min(max_w / img_w, max_h / img_h)
        draw_w = img_w * scale
        draw_h = img_h * scale
        x = page_width - 25 * mm - draw_w
        y = anchor_y - draw_h + 2 * mm
        pdf.drawImage(image, x, y, width=draw_w, height=draw_h, mask="auto")
    except Exception:
        return
