from __future__ import annotations

from io import BytesIO, StringIO

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.models.schemas import CSVUploadResponse, PDFGenerateRequest
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
    Upload CSV file and return parsed data with available price columns
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        # Read CSV file
        contents = await file.read()
        df = pd.read_csv(StringIO(contents.decode("utf-8")))

        # Get price columns (numeric only — a text column would 500 the PDF step)
        price_columns = numeric_price_columns(df)

        # Get unique product codes
        product_codes = df["ProductCode"].unique().tolist() if "ProductCode" in df.columns else []

        # Convert dataframe to list of dicts
        data = df.to_dict("records")

        return CSVUploadResponse(
            data=data, price_columns=price_columns, product_codes=product_codes
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing CSV: {str(e)}")


@router.post("/generate-pdf")
async def generate_pdf(request: PDFGenerateRequest):
    """
    Generate PDF with price tags based on configuration and selected products
    """
    try:
        # Convert data to DataFrame
        df = pd.DataFrame(request.csv_data)

        # Filter by selected products
        if request.selected_products:
            df = df[df["ProductCode"].isin(request.selected_products)]

        if df.empty:
            raise HTTPException(status_code=400, detail="No products selected or found")

        # Validate the chosen price column is present and numeric, else the
        # markup multiply in generate_tags would raise and surface as a 500.
        if request.price_column not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Price column '{request.price_column}' not found",
            )
        prices = pd.to_numeric(df[request.price_column], errors="coerce")
        if prices.isna().all():
            raise HTTPException(
                status_code=400,
                detail=f"Price column '{request.price_column}' isn't numeric",
            )
        df[request.price_column] = prices

        # Reset index
        df = df.reset_index(drop=True)

        # Generate PDF
        generator = PDFGenerator(request.config)
        pdf_bytes = generator.generate_tags(df, request.price_column)

        # Return PDF as streaming response
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=PriceTags.pdf"},
        )
    except HTTPException:
        raise  # don't let the 400s above get swallowed into a 500
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")
