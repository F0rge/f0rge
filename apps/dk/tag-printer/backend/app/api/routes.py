from __future__ import annotations

from io import BytesIO, StringIO

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.models.schemas import CSVUploadResponse, PDFGenerateRequest
from app.services.csv_sessions import MAX_UPLOAD_BYTES, create_session, get_session
from app.services.pdf_generator import PDFGenerator

router = APIRouter()


def numeric_price_columns(df: pd.DataFrame) -> list[str]:
    """Price-named columns whose values are actually numeric.

    Keeps the UI from offering text columns like "Default Price Tier" or
    "Price Regime" (values "Standard"/"Premium") that would crash PDF
    generation when multiplied by the markup.
    """
    return [
        col
        for col in df.filter(regex="Price").columns
        if pd.to_numeric(df[col], errors="coerce").notna().mean() >= 0.5
    ]


@router.post("/upload-csv", response_model=CSVUploadResponse)
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload CSV file and return parsed data with available price columns.
    Max upload size: 5 MB.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="CSV exceeds 5 MB upload limit")

        df = pd.read_csv(StringIO(contents.decode("utf-8")))

        price_columns = numeric_price_columns(df)
        product_codes = df["ProductCode"].unique().tolist() if "ProductCode" in df.columns else []
        data = df.to_dict("records")
        session_id = create_session(data, price_columns, product_codes)

        return CSVUploadResponse(
            session_id=session_id,
            data=data,
            price_columns=price_columns,
            product_codes=product_codes,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV: {str(e)}")


@router.post("/generate-pdf")
async def generate_pdf(request: PDFGenerateRequest):
    """
    Generate PDF with price tags based on configuration and selected products.
    Prefer session_id from upload to avoid re-posting the full CSV payload.
    """
    try:
        if request.session_id:
            session = get_session(request.session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="CSV session not found or expired")
            records = session.data
        elif request.csv_data:
            records = request.csv_data
        else:
            raise HTTPException(status_code=400, detail="session_id or csv_data is required")

        df = pd.DataFrame(records)

        missing = [c for c in ("ProductCode", "Name") if c not in df.columns]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing)}",
            )

        if request.selected_products:
            df = df[df["ProductCode"].isin(request.selected_products)]

        if df.empty:
            raise HTTPException(status_code=400, detail="No products selected or found")

        if request.price_column not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Price column '{request.price_column}' not found",
            )
        prices = pd.to_numeric(df[request.price_column], errors="coerce")
        if prices.isna().any():
            raise HTTPException(
                status_code=400,
                detail=f"Price column '{request.price_column}' contains non-numeric values",
            )
        df[request.price_column] = prices

        df = df.reset_index(drop=True)

        generator = PDFGenerator(request.config)
        pdf_bytes = generator.generate_tags(df, request.price_column)

        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=PriceTags.pdf"},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")
