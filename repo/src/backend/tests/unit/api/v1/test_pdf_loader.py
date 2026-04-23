"""Tests for the PDF Loader API endpoint.

Covers:
- POST /api/v1/flows/pdf-loader with a valid PDF → 200 + {text, page_count, status}
- Corrupted PDF → 400
- Non-PDF file  → 400 or 415
"""

from __future__ import annotations

import asyncio
import io
import tempfile
from contextlib import suppress
from pathlib import Path

import anyio
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from langflow.main import create_app


# ---------------------------------------------------------------------------
# Minimal valid PDF builder (no external library needed)
# ---------------------------------------------------------------------------

def _build_minimal_pdf(text: str = "Hello PDF World") -> bytes:
    """Return the bytes of a minimal but spec-compliant single-page PDF."""
    stream = f"BT\n/F1 12 Tf\n72 720 Td\n({text}) Tj\nET"
    stream_bytes = stream.encode("latin-1")
    stream_len = len(stream_bytes)

    objects: list[bytes] = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        ),
        (
            f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode("latin-1")
            + stream_bytes
            + b"\nendstream\nendobj\n"
        ),
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]

    header = b"%PDF-1.4\n"
    body = header
    offsets: list[int] = []
    for obj in objects:
        offsets.append(len(body))
        body += obj

    xref_offset = len(body)
    xref = f"xref\n0 {len(objects) + 1}\n"
    xref += "0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n"

    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    )

    return body + xref.encode("latin-1") + trailer.encode("latin-1")


# ---------------------------------------------------------------------------
# Unit tests for the extraction utility (no HTTP stack needed)
# ---------------------------------------------------------------------------

def test_extract_pdf_text_valid():
    """extract_pdf_text returns (text, page_count) for a valid PDF."""
    from langflow.utils.pdf_extraction import extract_pdf_text

    pdf_bytes = _build_minimal_pdf("Hello PDF World")
    text, page_count = extract_pdf_text(io.BytesIO(pdf_bytes))

    assert isinstance(text, str)
    assert isinstance(page_count, int)
    assert page_count == 1
    assert "Hello PDF World" in text


def test_extract_pdf_text_corrupted():
    """extract_pdf_text raises ValueError for a corrupted PDF."""
    from langflow.utils.pdf_extraction import extract_pdf_text

    corrupted = b"%PDF-1.4\nThis is not a valid PDF - corrupted!!!"
    with pytest.raises(ValueError, match="(?i)pdf"):
        extract_pdf_text(io.BytesIO(corrupted))


# ---------------------------------------------------------------------------
# Integration fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="pdf_client")
async def pdf_client_fixture(monkeypatch):
    """Spin up a full Langflow app with a temp SQLite database."""

    def _init():
        db_dir = tempfile.mkdtemp()
        db_path = Path(db_dir) / "test_pdf.db"
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")
        from langflow.services.manager import service_manager

        service_manager.factories.clear()
        service_manager.services.clear()
        app = create_app()
        return app, db_path

    app, db_path = await asyncio.to_thread(_init)

    async with (
        LifespanManager(app, startup_timeout=None, shutdown_timeout=None) as manager,
        AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://testserver/",
        ) as client,
    ):
        yield client

    monkeypatch.undo()
    with suppress(FileNotFoundError):
        await anyio.Path(db_path).unlink()


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

PDF_ENDPOINT = "api/v1/flows/pdf-loader"


async def test_pdf_loader_valid_pdf(pdf_client):
    """A valid PDF should return 200 with text, page_count, and status."""
    pdf_bytes = _build_minimal_pdf("Hello PDF World")

    response = await pdf_client.post(
        PDF_ENDPOINT,
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert "text" in body
    assert "page_count" in body
    assert "status" in body

    assert isinstance(body["text"], str)
    assert isinstance(body["page_count"], int)
    assert body["status"] == "success"
    assert body["page_count"] >= 1
    assert "Hello PDF World" in body["text"]


async def test_pdf_loader_page_count(pdf_client):
    """Single-page PDF should report page_count == 1."""
    pdf_bytes = _build_minimal_pdf("Page one")

    response = await pdf_client.post(
        PDF_ENDPOINT,
        files={"file": ("single.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["page_count"] == 1
    assert body["status"] == "success"


async def test_pdf_loader_corrupted_pdf(pdf_client):
    """A corrupted PDF (valid magic, garbage body) should return 400."""
    corrupted = b"%PDF-1.4\nThis is not a valid PDF - corrupted!!!"

    response = await pdf_client.post(
        PDF_ENDPOINT,
        files={"file": ("corrupted.pdf", corrupted, "application/pdf")},
    )

    assert response.status_code == 400, response.text
    body = response.json()
    assert "detail" in body
    assert len(body["detail"]) > 0


async def test_pdf_loader_non_pdf_file(pdf_client):
    """A plain text file should return 400 or 415."""
    text_content = b"This is a plain text file, not a PDF."

    response = await pdf_client.post(
        PDF_ENDPOINT,
        files={"file": ("document.txt", text_content, "text/plain")},
    )

    assert response.status_code in (400, 415), response.text
    body = response.json()
    assert "detail" in body


async def test_pdf_loader_jpeg_file(pdf_client):
    """A JPEG file should return 400 or 415."""
    jpeg_bytes = bytes([0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46])

    response = await pdf_client.post(
        PDF_ENDPOINT,
        files={"file": ("image.jpg", jpeg_bytes, "image/jpeg")},
    )

    assert response.status_code in (400, 415), response.text
    body = response.json()
    assert "detail" in body


async def test_pdf_loader_status_field(pdf_client):
    """The status field must be 'success' for a valid PDF."""
    pdf_bytes = _build_minimal_pdf("Status check")

    response = await pdf_client.post(
        PDF_ENDPOINT,
        files={"file": ("status.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "success"
