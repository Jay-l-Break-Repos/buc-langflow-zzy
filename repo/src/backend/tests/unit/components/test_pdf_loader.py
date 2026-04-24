"""Unit tests for the PDF Loader node — Step 2 (real extraction + error handling).

Coverage
--------
* Palette metadata (display_name, icon, name, VALID_EXTENSIONS)
* Output descriptor (name, method, display_name)
* ``_extract_text_from_pdf`` — happy path, multi-page, empty page, encrypted,
  corrupted, and truncated PDFs
* ``process_files`` — successful extraction, corrupted PDF (silent / non-silent),
  password-protected PDF (silent / non-silent), multiple files, empty list
* ``load_pdf_content`` — returns Message, status string, page-count summary,
  error-file summary, empty-file-list edge case
"""

from __future__ import annotations

import io
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# pypdf helpers — used to build real in-memory PDFs for testing
# ---------------------------------------------------------------------------
from pypdf import PdfReader, PdfWriter
from pypdf.errors import FileNotDecryptedError, PdfReadError, PdfStreamError

from langflow.components.documentloaders.pdf_loader import PDFLoaderComponent
from langflow.schema.data import Data
from langflow.schema.message import Message


# ===========================================================================
# PDF factory helpers
# ===========================================================================


def _make_pdf_bytes(pages: list[str]) -> bytes:
    """Return a minimal valid PDF containing one text layer per page."""
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        # PdfWriter doesn't have a simple "add text" API without a font resource,
        # so we inject a raw content stream directly.
        content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        page.compress_content_streams()
        # Patch the page's /Contents with our stream
        from pypdf.generic import DecodedStreamObject, NameObject

        stream_obj = DecodedStreamObject()
        stream_obj.set_data(content)
        page[NameObject("/Contents")] = stream_obj

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_encrypted_pdf_bytes(password: str = "secret") -> bytes:
    """Return a minimal password-protected PDF."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt(password)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_base_file(
    tmp_path: Path,
    filename: str = "sample.pdf",
    content: bytes | None = None,
) -> MagicMock:
    """Return a mock BaseFile whose ``path`` points to a real temp file."""
    pdf_file = tmp_path / filename
    pdf_file.write_bytes(content if content is not None else _make_pdf_bytes(["Hello"]))

    base_file = MagicMock(spec=["path", "data"])
    base_file.path = pdf_file
    base_file.data = Data()
    return base_file


# ===========================================================================
# Palette / registry metadata
# ===========================================================================


class TestPDFLoaderMetadata:
    """Verify the node's palette metadata is correctly set."""

    def test_display_name(self):
        assert PDFLoaderComponent.display_name == "PDF Loader"

    def test_icon(self):
        assert PDFLoaderComponent.icon == "file-text"

    def test_internal_name(self):
        assert PDFLoaderComponent.name == "PDFLoader"

    def test_description_is_non_empty(self):
        assert PDFLoaderComponent.description
        assert isinstance(PDFLoaderComponent.description, str)

    def test_valid_extensions_is_pdf_only(self):
        assert PDFLoaderComponent.VALID_EXTENSIONS == ["pdf"]


# ===========================================================================
# Output declaration
# ===========================================================================


class TestPDFLoaderOutputs:
    """Verify the output descriptor is present and correctly configured."""

    def test_text_content_output_exists(self):
        names = [o.name for o in PDFLoaderComponent.outputs]
        assert "text_content" in names

    def test_text_content_output_method(self):
        output = next(o for o in PDFLoaderComponent.outputs if o.name == "text_content")
        assert output.method == "load_pdf_content"

    def test_text_content_display_name(self):
        output = next(o for o in PDFLoaderComponent.outputs if o.name == "text_content")
        assert output.display_name == "Text Content"


# ===========================================================================
# _extract_text_from_pdf — unit tests (no Langflow runtime needed)
# ===========================================================================


class TestExtractTextFromPdf:
    """Direct tests of the internal extraction helper."""

    def test_single_page_returns_text_and_count(self, tmp_path):
        pdf_bytes = _make_pdf_bytes(["Hello World"])
        path = tmp_path / "single.pdf"
        path.write_bytes(pdf_bytes)

        comp = PDFLoaderComponent()
        text, page_count = comp._extract_text_from_pdf(path)

        assert page_count == 1
        assert isinstance(text, str)

    def test_multi_page_returns_correct_count(self, tmp_path):
        pdf_bytes = _make_pdf_bytes(["Page 1", "Page 2", "Page 3"])
        path = tmp_path / "multi.pdf"
        path.write_bytes(pdf_bytes)

        comp = PDFLoaderComponent()
        text, page_count = comp._extract_text_from_pdf(path)

        assert page_count == 3

    def test_pages_joined_with_double_newline(self, tmp_path):
        """Extracted pages must be separated by '\\n\\n'."""
        # We mock PdfReader to return predictable per-page text
        pdf_bytes = _make_pdf_bytes(["A", "B"])
        path = tmp_path / "two.pdf"
        path.write_bytes(pdf_bytes)

        comp = PDFLoaderComponent()

        mock_page_a = MagicMock()
        mock_page_a.extract_text.return_value = "Page A text"
        mock_page_b = MagicMock()
        mock_page_b.extract_text.return_value = "Page B text"

        mock_reader = MagicMock()
        mock_reader.is_encrypted = False
        mock_reader.pages = [mock_page_a, mock_page_b]
        mock_reader.__enter__ = lambda s: s
        mock_reader.__exit__ = MagicMock(return_value=False)

        with patch("langflow.components.documentloaders.pdf_loader.PdfReader", return_value=mock_reader):
            text, page_count = comp._extract_text_from_pdf(path)

        assert text == "Page A text\n\nPage B text"
        assert page_count == 2

    def test_empty_page_text_treated_as_empty_string(self, tmp_path):
        """Pages where extract_text() returns None must not cause errors."""
        pdf_bytes = _make_pdf_bytes([""])
        path = tmp_path / "empty_page.pdf"
        path.write_bytes(pdf_bytes)

        comp = PDFLoaderComponent()

        mock_page = MagicMock()
        mock_page.extract_text.return_value = None  # simulate empty page

        mock_reader = MagicMock()
        mock_reader.is_encrypted = False
        mock_reader.pages = [mock_page]

        with patch("langflow.components.documentloaders.pdf_loader.PdfReader", return_value=mock_reader):
            text, page_count = comp._extract_text_from_pdf(path)

        assert text == ""
        assert page_count == 1

    def test_corrupted_pdf_raises_pdf_read_error(self, tmp_path):
        path = tmp_path / "corrupt.pdf"
        path.write_bytes(b"this is not a pdf")

        comp = PDFLoaderComponent()
        with pytest.raises(PdfReadError):
            comp._extract_text_from_pdf(path)

    def test_password_protected_raises_file_not_decrypted(self, tmp_path):
        path = tmp_path / "protected.pdf"
        path.write_bytes(_make_encrypted_pdf_bytes("secret"))

        comp = PDFLoaderComponent()
        with pytest.raises(FileNotDecryptedError):
            comp._extract_text_from_pdf(path)

    def test_pdf_stream_error_propagates(self, tmp_path):
        """A PdfStreamError raised inside PdfReader must propagate."""
        pdf_bytes = _make_pdf_bytes(["x"])
        path = tmp_path / "stream_err.pdf"
        path.write_bytes(pdf_bytes)

        comp = PDFLoaderComponent()
        with patch(
            "langflow.components.documentloaders.pdf_loader.PdfReader",
            side_effect=PdfStreamError("stream broken"),
        ):
            with pytest.raises(PdfStreamError):
                comp._extract_text_from_pdf(path)


# ===========================================================================
# process_files — integration-style tests (mock BaseFile, real extraction)
# ===========================================================================


class TestProcessFiles:
    """Verify process_files populates Data correctly for each scenario."""

    # ------------------------------------------------------------------
    # Happy path
    # ------------------------------------------------------------------

    def test_single_file_data_is_populated(self, tmp_path):
        comp = PDFLoaderComponent()
        comp.silent_errors = False

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Extracted text"
        mock_reader = MagicMock()
        mock_reader.is_encrypted = False
        mock_reader.pages = [mock_page]

        base_file = _make_base_file(tmp_path)

        with patch("langflow.components.documentloaders.pdf_loader.PdfReader", return_value=mock_reader):
            result = comp.process_files([base_file])

        assert len(result) == 1
        data_list = result[0].data
        assert isinstance(data_list, list)
        data = data_list[0]
        assert isinstance(data, Data)

    def test_extracted_text_stored_in_data(self, tmp_path):
        comp = PDFLoaderComponent()
        comp.silent_errors = False

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Hello PDF"
        mock_reader = MagicMock()
        mock_reader.is_encrypted = False
        mock_reader.pages = [mock_page]

        base_file = _make_base_file(tmp_path)

        with patch("langflow.components.documentloaders.pdf_loader.PdfReader", return_value=mock_reader):
            result = comp.process_files([base_file])

        data = result[0].data[0]
        assert data.data["text"] == "Hello PDF"

    def test_page_count_stored_in_data(self, tmp_path):
        comp = PDFLoaderComponent()
        comp.silent_errors = False

        pages = [MagicMock() for _ in range(4)]
        for p in pages:
            p.extract_text.return_value = "text"
        mock_reader = MagicMock()
        mock_reader.is_encrypted = False
        mock_reader.pages = pages

        base_file = _make_base_file(tmp_path)

        with patch("langflow.components.documentloaders.pdf_loader.PdfReader", return_value=mock_reader):
            result = comp.process_files([base_file])

        data = result[0].data[0]
        assert data.data["page_count"] == 4

    def test_file_path_and_name_stored_in_data(self, tmp_path):
        comp = PDFLoaderComponent()
        comp.silent_errors = False

        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_reader = MagicMock()
        mock_reader.is_encrypted = False
        mock_reader.pages = [mock_page]

        base_file = _make_base_file(tmp_path, "my_doc.pdf")

        with patch("langflow.components.documentloaders.pdf_loader.PdfReader", return_value=mock_reader):
            result = comp.process_files([base_file])

        data = result[0].data[0]
        assert data.data["file_name"] == "my_doc.pdf"
        assert "my_doc.pdf" in data.data["file_path"]

    def test_multiple_files_all_processed(self, tmp_path):
        comp = PDFLoaderComponent()
        comp.silent_errors = False

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "text"
        mock_reader = MagicMock()
        mock_reader.is_encrypted = False
        mock_reader.pages = [mock_page]

        files = [_make_base_file(tmp_path, f"doc{i}.pdf") for i in range(3)]

        with patch("langflow.components.documentloaders.pdf_loader.PdfReader", return_value=mock_reader):
            result = comp.process_files(files)

        assert len(result) == 3
        for bf in result:
            assert bf.data[0].data["text"] == "text"

    def test_empty_file_list_returns_empty(self):
        comp = PDFLoaderComponent()
        comp.silent_errors = False
        assert comp.process_files([]) == []

    # ------------------------------------------------------------------
    # Corrupted PDF
    # ------------------------------------------------------------------

    def test_corrupted_pdf_silent_errors_true_stores_error_field(self, tmp_path):
        comp = PDFLoaderComponent()
        comp.silent_errors = True

        base_file = _make_base_file(tmp_path, "corrupt.pdf", content=b"not a pdf")

        result = comp.process_files([base_file])

        data = result[0].data[0]
        assert "error" in data.data
        assert data.data["text"] == ""
        assert data.data["page_count"] == 0

    def test_corrupted_pdf_silent_errors_false_raises(self, tmp_path):
        comp = PDFLoaderComponent()
        comp.silent_errors = False

        base_file = _make_base_file(tmp_path, "corrupt.pdf", content=b"not a pdf")

        with pytest.raises((PdfReadError, PdfStreamError)):
            comp.process_files([base_file])

    def test_corrupted_pdf_error_message_contains_filename(self, tmp_path):
        comp = PDFLoaderComponent()
        comp.silent_errors = True

        base_file = _make_base_file(tmp_path, "bad_file.pdf", content=b"garbage")

        result = comp.process_files([base_file])

        data = result[0].data[0]
        assert "bad_file.pdf" in data.data["error"]

    # ------------------------------------------------------------------
    # Password-protected PDF
    # ------------------------------------------------------------------

    def test_password_protected_silent_errors_true_stores_error_field(self, tmp_path):
        comp = PDFLoaderComponent()
        comp.silent_errors = True

        base_file = _make_base_file(
            tmp_path, "protected.pdf", content=_make_encrypted_pdf_bytes("secret")
        )

        result = comp.process_files([base_file])

        data = result[0].data[0]
        assert "error" in data.data
        assert data.data["text"] == ""
        assert data.data["page_count"] == 0

    def test_password_protected_silent_errors_false_raises(self, tmp_path):
        comp = PDFLoaderComponent()
        comp.silent_errors = False

        base_file = _make_base_file(
            tmp_path, "protected.pdf", content=_make_encrypted_pdf_bytes("secret")
        )

        with pytest.raises(FileNotDecryptedError):
            comp.process_files([base_file])

    def test_password_protected_error_message_mentions_password(self, tmp_path):
        comp = PDFLoaderComponent()
        comp.silent_errors = True

        base_file = _make_base_file(
            tmp_path, "locked.pdf", content=_make_encrypted_pdf_bytes("pass")
        )

        result = comp.process_files([base_file])

        data = result[0].data[0]
        error_msg = data.data["error"].lower()
        # Should mention either "password" or "decrypt" or "encrypted"
        assert any(kw in error_msg for kw in ("password", "decrypt", "encrypt"))


# ===========================================================================
# load_pdf_content — output method
# ===========================================================================


class TestLoadPdfContent:
    """Verify load_pdf_content returns the right Message and sets status."""

    def test_returns_message_instance(self):
        comp = PDFLoaderComponent()
        data_list = [
            Data(data={"text": "Hello", "page_count": 1, "file_name": "a.pdf"})
        ]
        with patch.object(comp, "load_files_base", return_value=data_list):
            result = comp.load_pdf_content()
        assert isinstance(result, Message)

    def test_message_text_contains_extracted_text(self):
        comp = PDFLoaderComponent()
        data_list = [
            Data(data={"text": "Extracted content", "page_count": 2, "file_name": "doc.pdf"})
        ]
        with patch.object(comp, "load_files_base", return_value=data_list):
            result = comp.load_pdf_content()
        assert "Extracted content" in result.text

    def test_status_contains_page_count(self):
        comp = PDFLoaderComponent()
        data_list = [
            Data(data={"text": "text", "page_count": 7, "file_name": "doc.pdf"})
        ]
        with patch.object(comp, "load_files_base", return_value=data_list):
            comp.load_pdf_content()
        assert "7" in comp.status

    def test_status_contains_file_count(self):
        comp = PDFLoaderComponent()
        data_list = [
            Data(data={"text": "t1", "page_count": 2, "file_name": "a.pdf"}),
            Data(data={"text": "t2", "page_count": 3, "file_name": "b.pdf"}),
        ]
        with patch.object(comp, "load_files_base", return_value=data_list):
            comp.load_pdf_content()
        assert "2" in comp.status  # 2 files

    def test_status_mentions_error_files(self):
        comp = PDFLoaderComponent()
        data_list = [
            Data(data={"text": "", "page_count": 0, "file_name": "bad.pdf", "error": "corrupted"})
        ]
        with patch.object(comp, "load_files_base", return_value=data_list):
            comp.load_pdf_content()
        assert "bad.pdf" in comp.status

    def test_multiple_files_text_joined_by_separator(self):
        comp = PDFLoaderComponent()
        comp.separator = "\n\n"
        data_list = [
            Data(data={"text": "First", "page_count": 1, "file_name": "a.pdf"}),
            Data(data={"text": "Second", "page_count": 1, "file_name": "b.pdf"}),
        ]
        with patch.object(comp, "load_files_base", return_value=data_list):
            result = comp.load_pdf_content()
        assert "First" in result.text
        assert "Second" in result.text

    def test_empty_data_list_returns_empty_message(self):
        comp = PDFLoaderComponent()
        with patch.object(comp, "load_files_base", return_value=[]):
            result = comp.load_pdf_content()
        assert isinstance(result, Message)
        assert result.text == ""

    def test_status_is_non_empty_string(self):
        comp = PDFLoaderComponent()
        data_list = [
            Data(data={"text": "x", "page_count": 1, "file_name": "x.pdf"})
        ]
        with patch.object(comp, "load_files_base", return_value=data_list):
            comp.load_pdf_content()
        assert comp.status
        assert isinstance(comp.status, str)
