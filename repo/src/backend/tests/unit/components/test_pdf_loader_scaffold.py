"""Unit tests for the PDF Loader node scaffold (Step 1).

These tests verify that:
- ``PDFLoaderComponent`` can be imported and instantiated.
- The node has the correct palette metadata (display_name, icon, name).
- ``VALID_EXTENSIONS`` is set to ``["pdf"]``.
- The ``text_content`` output is declared.
- ``process_files`` attaches placeholder ``Data`` to each ``BaseFile``.
- ``load_pdf_content`` returns a ``Message`` instance.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from langflow.components.documentloaders.pdf_loader import PDFLoaderComponent
from langflow.schema.data import Data
from langflow.schema.message import Message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_base_file(tmp_path: Path, filename: str = "sample.pdf") -> MagicMock:
    """Return a mock BaseFile whose ``path`` points to a real temp file."""
    pdf_file = tmp_path / filename
    pdf_file.write_bytes(b"%PDF-1.4 placeholder")

    base_file = MagicMock()
    base_file.path = pdf_file
    base_file.data = Data()  # initial empty Data
    return base_file


# ---------------------------------------------------------------------------
# Palette / registry metadata
# ---------------------------------------------------------------------------


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

    def test_valid_extensions(self):
        assert PDFLoaderComponent.VALID_EXTENSIONS == ["pdf"]


# ---------------------------------------------------------------------------
# Output declaration
# ---------------------------------------------------------------------------


class TestPDFLoaderOutputs:
    """Verify the output descriptor is present and correctly configured."""

    def test_text_content_output_exists(self):
        output_names = [o.name for o in PDFLoaderComponent.outputs]
        assert "text_content" in output_names

    def test_text_content_output_method(self):
        output = next(o for o in PDFLoaderComponent.outputs if o.name == "text_content")
        assert output.method == "load_pdf_content"

    def test_text_content_display_name(self):
        output = next(o for o in PDFLoaderComponent.outputs if o.name == "text_content")
        assert output.display_name == "Text Content"


# ---------------------------------------------------------------------------
# process_files — placeholder behaviour
# ---------------------------------------------------------------------------


class TestProcessFiles:
    """Verify process_files attaches placeholder Data to each BaseFile."""

    def test_single_file_gets_data(self, tmp_path):
        comp = PDFLoaderComponent()
        base_file = _make_base_file(tmp_path)

        result = comp.process_files([base_file])

        assert len(result) == 1
        # data setter wraps a single Data in a list
        data_list = result[0].data
        assert isinstance(data_list, list)
        assert len(data_list) == 1
        data = data_list[0]
        assert isinstance(data, Data)

    def test_placeholder_status_is_pending(self, tmp_path):
        comp = PDFLoaderComponent()
        base_file = _make_base_file(tmp_path)

        result = comp.process_files([base_file])
        data = result[0].data[0]

        assert data.data["status"] == "pending"

    def test_placeholder_text_contains_filename(self, tmp_path):
        comp = PDFLoaderComponent()
        base_file = _make_base_file(tmp_path, "my_document.pdf")

        result = comp.process_files([base_file])
        data = result[0].data[0]

        assert "my_document.pdf" in data.data["text"]

    def test_placeholder_file_path_is_set(self, tmp_path):
        comp = PDFLoaderComponent()
        base_file = _make_base_file(tmp_path)

        result = comp.process_files([base_file])
        data = result[0].data[0]

        assert data.data["file_path"] == str(base_file.path)

    def test_multiple_files_all_get_data(self, tmp_path):
        comp = PDFLoaderComponent()
        files = [
            _make_base_file(tmp_path, "a.pdf"),
            _make_base_file(tmp_path, "b.pdf"),
            _make_base_file(tmp_path, "c.pdf"),
        ]

        result = comp.process_files(files)

        assert len(result) == 3
        for bf in result:
            assert bf.data  # non-empty list
            assert bf.data[0].data["status"] == "pending"

    def test_empty_file_list_returns_empty(self):
        comp = PDFLoaderComponent()
        result = comp.process_files([])
        assert result == []


# ---------------------------------------------------------------------------
# load_pdf_content — output method
# ---------------------------------------------------------------------------


class TestLoadPdfContent:
    """Verify load_pdf_content returns a Message."""

    def test_returns_message(self, tmp_path):
        comp = PDFLoaderComponent()

        # Patch load_files_message so we don't need a real Langflow runtime
        with patch.object(comp, "load_files_message", return_value=Message(text="placeholder")):
            result = comp.load_pdf_content()

        assert isinstance(result, Message)

    def test_sets_status(self, tmp_path):
        comp = PDFLoaderComponent()

        with patch.object(comp, "load_files_message", return_value=Message(text="")):
            comp.load_pdf_content()

        assert comp.status  # non-empty status string
        assert isinstance(comp.status, str)
