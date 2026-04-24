"""Tests for the PDF Loader component — Step 2: text extraction.

Covers:
- process_files() extracts text from a valid PDF
- process_files() populates page_count and file_path metadata
- process_files() handles corrupted/invalid PDF files gracefully
- process_files() handles password-protected PDFs gracefully
- process_files() handles empty (zero-page) PDFs gracefully
- process_files() handles image-only (no text) PDFs without raising
- load_pdf_content() returns a Message with the extracted text
- load_pdf_content() returns a Message on error (no exception raised)
"""

from __future__ import annotations

import io
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_base_file(path: Path, *, silent_errors: bool = False):
    """Create a BaseFileComponent.BaseFile pointing at *path*."""
    from langflow.base.data.base_file import BaseFileComponent
    from langflow.schema.data import Data

    return BaseFileComponent.BaseFile(
        data=Data(data={"file_path": str(path)}),
        path=path,
        silent_errors=silent_errors,
    )


def _make_component():
    """Instantiate PDFLoaderComponent with minimal mocked inputs."""
    from langflow.components.documentloaders.pdf_loader import PDFLoaderComponent

    comp = PDFLoaderComponent.__new__(PDFLoaderComponent)
    # Provide the attributes that BaseFileComponent / load_files_message use
    comp.silent_errors = False
    comp.separator = "\n\n"
    comp.path = []
    comp.file_path = None
    comp.delete_server_file_after_processing = False
    comp.ignore_unsupported_extensions = True
    comp.ignore_unspecified_files = False
    # Stub out log() so tests don't need a running server
    comp.log = lambda msg, *a, **kw: None  # noqa: ARG005
    return comp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_pdf(tmp_path):
    """Return a minimal but valid single-page PDF file."""
    # Minimal PDF 1.4 with one page containing the text "Hello PDF"
    pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj
4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
5 0 obj<</Length 44>>
stream
BT /F1 12 Tf 100 700 Td (Hello PDF) Tj ET
endstream
endobj
xref
0 6
0000000000 65535 f\r
0000000009 00000 n\r
0000000058 00000 n\r
0000000115 00000 n\r
0000000266 00000 n\r
0000000340 00000 n\r
trailer<</Size 6/Root 1 0 R>>
startxref
436
%%EOF"""
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture()
def corrupted_pdf(tmp_path):
    """Return a file with a .pdf extension but invalid/corrupted content."""
    bad_path = tmp_path / "corrupted.pdf"
    bad_path.write_bytes(b"THIS IS NOT A PDF FILE AT ALL \x00\x01\x02")
    return bad_path


@pytest.fixture()
def empty_file_pdf(tmp_path):
    """Return a completely empty file with a .pdf extension."""
    empty_path = tmp_path / "empty.pdf"
    empty_path.write_bytes(b"")
    return empty_path


# ---------------------------------------------------------------------------
# Tests: _extract_text_from_pdf internals (unit-level, mocked pypdf)
# ---------------------------------------------------------------------------

class TestExtractTextSuccess:
    """_extract_text_from_pdf returns success Data for a readable PDF."""

    def test_status_is_success(self, tmp_pdf):
        comp = _make_component()
        result = comp._extract_text_from_pdf(tmp_pdf)
        assert result.data["status"] == "success"

    def test_file_path_in_data(self, tmp_pdf):
        comp = _make_component()
        result = comp._extract_text_from_pdf(tmp_pdf)
        assert result.data["file_path"] == str(tmp_pdf)

    def test_page_count_is_integer(self, tmp_pdf):
        comp = _make_component()
        result = comp._extract_text_from_pdf(tmp_pdf)
        assert isinstance(result.data["page_count"], int)
        assert result.data["page_count"] >= 1

    def test_text_is_string(self, tmp_pdf):
        comp = _make_component()
        result = comp._extract_text_from_pdf(tmp_pdf)
        assert isinstance(result.data["text"], str)

    def test_no_error_key_on_success(self, tmp_pdf):
        comp = _make_component()
        result = comp._extract_text_from_pdf(tmp_pdf)
        assert "error" not in result.data


class TestExtractTextPasswordProtected:
    """_extract_text_from_pdf returns error Data for encrypted PDFs."""

    def test_status_is_error(self):
        comp = _make_component()
        mock_reader = MagicMock()
        mock_reader.is_encrypted = True

        with patch("pypdf.PdfReader", return_value=mock_reader):
            result = comp._extract_text_from_pdf(Path("/fake/protected.pdf"))

        assert result.data["status"] == "error"

    def test_error_mentions_password(self):
        comp = _make_component()
        mock_reader = MagicMock()
        mock_reader.is_encrypted = True

        with patch("pypdf.PdfReader", return_value=mock_reader):
            result = comp._extract_text_from_pdf(Path("/fake/protected.pdf"))

        assert "password" in result.data["error"].lower() or "encrypt" in result.data["error"].lower()

    def test_page_count_is_zero(self):
        comp = _make_component()
        mock_reader = MagicMock()
        mock_reader.is_encrypted = True

        with patch("pypdf.PdfReader", return_value=mock_reader):
            result = comp._extract_text_from_pdf(Path("/fake/protected.pdf"))

        assert result.data["page_count"] == 0

    def test_text_is_empty_string(self):
        comp = _make_component()
        mock_reader = MagicMock()
        mock_reader.is_encrypted = True

        with patch("pypdf.PdfReader", return_value=mock_reader):
            result = comp._extract_text_from_pdf(Path("/fake/protected.pdf"))

        assert result.data["text"] == ""


class TestExtractTextCorrupted:
    """_extract_text_from_pdf returns error Data for corrupted PDFs."""

    def test_status_is_error(self):
        comp = _make_component()
        from pypdf.errors import PdfReadError

        with patch("pypdf.PdfReader", side_effect=PdfReadError("bad pdf")):
            result = comp._extract_text_from_pdf(Path("/fake/bad.pdf"))

        assert result.data["status"] == "error"

    def test_error_key_present(self):
        comp = _make_component()
        from pypdf.errors import PdfReadError

        with patch("pypdf.PdfReader", side_effect=PdfReadError("bad pdf")):
            result = comp._extract_text_from_pdf(Path("/fake/bad.pdf"))

        assert "error" in result.data
        assert len(result.data["error"]) > 0

    def test_page_count_is_zero(self):
        comp = _make_component()
        from pypdf.errors import PdfReadError

        with patch("pypdf.PdfReader", side_effect=PdfReadError("bad pdf")):
            result = comp._extract_text_from_pdf(Path("/fake/bad.pdf"))

        assert result.data["page_count"] == 0


class TestExtractTextEmptyPDF:
    """_extract_text_from_pdf returns error Data for zero-page PDFs."""

    def test_status_is_error(self):
        comp = _make_component()
        mock_reader = MagicMock()
        mock_reader.is_encrypted = False
        mock_reader.pages = []

        with patch("pypdf.PdfReader", return_value=mock_reader):
            result = comp._extract_text_from_pdf(Path("/fake/empty.pdf"))

        assert result.data["status"] == "error"

    def test_error_mentions_no_pages(self):
        comp = _make_component()
        mock_reader = MagicMock()
        mock_reader.is_encrypted = False
        mock_reader.pages = []

        with patch("pypdf.PdfReader", return_value=mock_reader):
            result = comp._extract_text_from_pdf(Path("/fake/empty.pdf"))

        assert "page" in result.data["error"].lower()


class TestExtractTextFileNotFound:
    """_extract_text_from_pdf returns error Data when the file is missing."""

    def test_status_is_error(self, tmp_path):
        comp = _make_component()
        missing = tmp_path / "does_not_exist.pdf"
        result = comp._extract_text_from_pdf(missing)
        assert result.data["status"] == "error"

    def test_error_key_present(self, tmp_path):
        comp = _make_component()
        missing = tmp_path / "does_not_exist.pdf"
        result = comp._extract_text_from_pdf(missing)
        assert "error" in result.data


class TestExtractTextImageOnlyPDF:
    """_extract_text_from_pdf does NOT raise for image-only PDFs (no text)."""

    def test_returns_success_with_empty_text(self):
        comp = _make_component()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_reader = MagicMock()
        mock_reader.is_encrypted = False
        mock_reader.pages = [mock_page]

        with patch("pypdf.PdfReader", return_value=mock_reader):
            result = comp._extract_text_from_pdf(Path("/fake/image_only.pdf"))

        # Should succeed (not raise), text is empty string
        assert result.data["status"] == "success"
        assert result.data["text"] == ""
        assert result.data["page_count"] == 1


# ---------------------------------------------------------------------------
# Tests: process_files integration
# ---------------------------------------------------------------------------

class TestProcessFiles:
    """process_files() correctly populates BaseFile.data for each file."""

    def test_process_files_attaches_data(self, tmp_pdf):
        comp = _make_component()
        base_file = _make_base_file(tmp_pdf)
        result = comp.process_files([base_file])
        assert len(result) == 1
        assert result[0].data  # non-empty list

    def test_process_files_data_has_status(self, tmp_pdf):
        comp = _make_component()
        base_file = _make_base_file(tmp_pdf)
        result = comp.process_files([base_file])
        data_obj = result[0].data[0]
        assert "status" in data_obj.data

    def test_process_files_data_has_text(self, tmp_pdf):
        comp = _make_component()
        base_file = _make_base_file(tmp_pdf)
        result = comp.process_files([base_file])
        data_obj = result[0].data[0]
        assert "text" in data_obj.data

    def test_process_files_data_has_page_count(self, tmp_pdf):
        comp = _make_component()
        base_file = _make_base_file(tmp_pdf)
        result = comp.process_files([base_file])
        data_obj = result[0].data[0]
        assert "page_count" in data_obj.data

    def test_process_files_data_has_file_path(self, tmp_pdf):
        comp = _make_component()
        base_file = _make_base_file(tmp_pdf)
        result = comp.process_files([base_file])
        data_obj = result[0].data[0]
        assert data_obj.data["file_path"] == str(tmp_pdf)

    def test_process_files_corrupted_does_not_raise(self, corrupted_pdf):
        comp = _make_component()
        base_file = _make_base_file(corrupted_pdf)
        # Should not raise — error is captured in Data
        result = comp.process_files([base_file])
        assert len(result) == 1

    def test_process_files_corrupted_status_is_error(self, corrupted_pdf):
        comp = _make_component()
        base_file = _make_base_file(corrupted_pdf)
        result = comp.process_files([base_file])
        data_obj = result[0].data[0]
        assert data_obj.data["status"] == "error"

    def test_process_files_multiple_files(self, tmp_pdf, tmp_path):
        """process_files handles a list with more than one file."""
        comp = _make_component()
        # Copy the valid PDF to create a second file
        second_pdf = tmp_path / "second.pdf"
        second_pdf.write_bytes(tmp_pdf.read_bytes())

        files = [_make_base_file(tmp_pdf), _make_base_file(second_pdf)]
        result = comp.process_files(files)
        assert len(result) == 2
        for f in result:
            assert f.data[0].data["status"] == "success"


# ---------------------------------------------------------------------------
# Tests: load_pdf_content output method
# ---------------------------------------------------------------------------

class TestLoadPdfContent:
    """load_pdf_content() returns a Message (never raises)."""

    def test_returns_message_type(self, tmp_pdf):
        from langflow.schema.message import Message

        comp = _make_component()
        # Wire up path so load_files_base can find the file
        comp.path = [str(tmp_pdf)]

        result = comp.load_pdf_content()
        assert isinstance(result, Message)

    def test_message_text_is_string(self, tmp_pdf):
        comp = _make_component()
        comp.path = [str(tmp_pdf)]

        result = comp.load_pdf_content()
        assert isinstance(result.text, str)

    def test_error_pdf_returns_message_not_exception(self, tmp_path):
        """Even for a corrupted PDF, load_pdf_content returns a Message."""
        from langflow.schema.message import Message

        bad_pdf = tmp_path / "bad.pdf"
        bad_pdf.write_bytes(b"not a pdf")

        comp = _make_component()
        comp.path = [str(bad_pdf)]

        result = comp.load_pdf_content()
        assert isinstance(result, Message)
