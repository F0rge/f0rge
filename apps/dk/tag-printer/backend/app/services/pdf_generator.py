from __future__ import annotations

import pandas as pd
from fpdf import FPDF

from app.models.schemas import TagConfig


class PDFGenerator:
    def __init__(self, config: TagConfig):
        self.config = config

    def generate_tags(self, df: pd.DataFrame, price_column: str) -> bytes:
        """Generate PDF with price tags on an explicit grid."""

        # Apply max characters limit to product names
        df["Name"] = df["Name"].str[: self.config.max_characters]

        tag_height = self.config.tag_height
        tag_width = self.config.tag_width
        font_size = self.config.font_size
        orientation = self.config.portrait_landscape
        left_margin = self.config.left_margin
        top_margin = self.config.top_margin
        # Clamp padding so inner width stays positive
        inner_padding = max(0.0, min(self.config.inner_padding, (tag_width - 0.1) / 2))

        # Create PDF
        pdf = FPDF(unit="mm", format="A4", orientation=orientation)
        pdf.set_auto_page_break(False)
        pdf.add_page(orientation)
        pdf.set_font("Arial", "B", font_size)

        page_w = pdf.w
        page_h = pdf.h
        right = left_margin
        bottom = top_margin

        x = left_margin
        y = top_margin

        for i in df.index:
            # Wrap to next row when the tag would overrun the usable width
            if x + tag_width > page_w - right + 0.5:
                x = left_margin
                y += tag_height
            # Spill to a new page when the row would overrun the usable height
            if y + tag_height > page_h - bottom + 0.5:
                pdf.add_page(orientation)
                y = top_margin

            self._draw_tag(pdf, df, i, price_column, x, y, tag_width, tag_height, inner_padding)
            x += tag_width

        # Return PDF as bytes
        return pdf.output(dest="S").encode("latin-1")

    def _draw_tag(self, pdf, df, i, price_column, x, y, tag_width, tag_height, inner_padding):
        """Draw one tag: three left-aligned text rows plus a border."""
        inner_x = x + inner_padding
        inner_w = tag_width - 2 * inner_padding
        row = tag_height / 3

        pdf.set_xy(inner_x, y)
        pdf.cell(w=inner_w, h=row, txt=str(df.iloc[i, 0]), border=0)
        pdf.set_xy(inner_x, y + row)
        pdf.cell(w=inner_w, h=row, txt=str(df.iloc[i, 1]), border=0)
        pdf.set_xy(inner_x, y + 2 * row)
        pdf.cell(w=inner_w, h=row, txt="R" + f"{df.at[i, price_column] * 1.15:0.2f}", border=0)

        pdf.rect(inner_x, y, inner_w, tag_height)


if __name__ == "__main__":
    df = pd.DataFrame(
        {
            "ProductCode": [f"P{n:03d}" for n in range(5)],
            "Name": [f"Widget {n}" for n in range(5)],
            "Price": [9.99, 19.5, 4.0, 120.0, 3.25],
        }
    )
    config = TagConfig(
        portrait_landscape="P",
        tag_height=39.5,
        tag_width=65,
        font_size=10,
        max_characters=20,
        auto_max_characters=False,
    )
    out = PDFGenerator(config).generate_tags(df, "Price")
    assert isinstance(out, bytes) and out.startswith(b"%PDF"), "PDF output invalid"
    print(f"OK: {len(out)} bytes, starts with {out[:4]!r}")
