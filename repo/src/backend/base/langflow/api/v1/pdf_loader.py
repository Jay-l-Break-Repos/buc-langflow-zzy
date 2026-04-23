"""PDF Loader API endpoint.

Exposes ``POST /api/v1/flows/pdf-loader`` which accepts a multipart PDF
upload and returns the extracted text, page count, and status.

This router is mounted onto the existing ``/flows`` prefix so the full
path becomes ``/api/v1/flows/pdf-loader``.
"""

from __future__ import annotations

import io
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from langflow.utils.pdf_extraction import extract_pdf_text

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PDF_MAGIC = b"%PDF"


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class PDFLoaderResponse(BaseModel):
    """Successful PDF extraction response."""

    text: str
    page_count: int
    status: str = "success"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/pdf-loader", response_model=PDFLoaderResponse, status_code=200)
async def pdf_loader(
    file: Annotated[UploadFile, File(description="PDF file to extract text from")],
) -> PDFLoaderResponse:
    """Extract text from an uploaded PDF file.

    Accepts a ``multipart/form-data`` upload with a single ``file`` field.

    Returns:
        JSON with ``text`` (extracted content), ``page_count``, and
        ``status`` (``"success"``).

    Raises:
        400: If the file is corrupted or cannot be parsed as a PDF.
        415: If the uploaded file is not a PDF (wrong extension and no PDF
             magic bytes).
    """
    # ---- Read the raw bytes ------------------------------------------------
    try:
        raw = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read uploaded file: {exc}",
        ) from exc

    # ---- Validate file type ------------------------------------------------
    filename = (file.filename or "").lower()
    is_pdf_by_name = filename.endswith(".pdf")
    is_pdf_by_magic = raw[:4] == _PDF_MAGIC

    # Reject files that are neither named *.pdf nor start with %PDF magic.
    if not is_pdf_by_name and not is_pdf_by_magic:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported file type. Only PDF files are accepted. "
                f"Received filename='{file.filename}', "
                f"content_type='{file.content_type}'."
            ),
        )

    # ---- Extract text ------------------------------------------------------
    try:
        text, page_count = extract_pdf_text(io.BytesIO(raw))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process PDF: {exc}",
        ) from exc

    return PDFLoaderResponse(text=text, page_count=page_count, status="success")
