"""PDF Loader component for Langflow.

Provides a node that accepts a PDF file upload and extracts the text
content for use in downstream flow nodes.

The node appears in the node palette under "Document Loaders" and
accepts a single ``.pdf`` file upload.
"""

from __future__ import annotations

import io
from pathlib import Path

from langflow.base.data.base_file import BaseFileComponent
from langflow.io import Output
from langflow.schema.data import Data
from langflow.schema.message import Message


class PDFLoaderComponent(BaseFileComponent):
    """Load a PDF file and expose its text content as a Message.

    The node appears in the node palette under the **Document Loaders**
    category and accepts a single ``.pdf`` file upload.
    """

    # ------------------------------------------------------------------ #
    # Palette metadata                                                     #
    # ------------------------------------------------------------------ #
    display_name = "PDF Loader"
    description = (
        "Upload a PDF file and extract its text content for use in your workflow. "
        "Appears under the Document Loaders category."
    )
    documentation = "https://docs.langflow.org/components-data"
    icon = "file-text"
    name = "PDFLoader"

    # ------------------------------------------------------------------ #
    # Accepted file types                                                  #
    # ------------------------------------------------------------------ #
    VALID_EXTENSIONS = ["pdf"]

    # ------------------------------------------------------------------ #
    # Outputs                                                              #
    # ------------------------------------------------------------------ #
    outputs = [
        Output(
            display_name="Text Content",
            name="text_content",
            method="load_pdf_content",
        ),
    ]

    # ------------------------------------------------------------------ #
    # Processing                                                           #
    # ------------------------------------------------------------------ #

    def process_files(
        self,
        file_list: list[BaseFileComponent.BaseFile],
    ) -> list[BaseFileComponent.BaseFile]:
        """Extract text from uploaded PDF files using pypdf.

        Args:
            file_list: List of validated BaseFile objects representing the
                       uploaded PDF file(s).

        Returns:
            The file list with Data objects populated with extracted text
            and page count metadata.
        """
        for base_file in file_list:
            try:
                text, page_count = _extract_pdf_text(base_file.path)
                base_file.data = Data(
                    text=text,
                    data={
                        "file_path": str(base_file.path),
                        "text": text,
                        "page_count": page_count,
                        "status": "success",
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self.log(f"Error extracting text from {base_file.path}: {exc}")
                base_file.data = Data(
                    data={
                        "file_path": str(base_file.path),
                        "error": str(exc),
                        "status": "error",
                    }
                )
        return file_list

    # ------------------------------------------------------------------ #
    # Output method                                                        #
    # ------------------------------------------------------------------ #

    def load_pdf_content(self) -> Message:
        """Return extracted PDF text as a Message.

        Returns:
            Message: A Message object containing the extracted text.
        """
        return self.load_files_message()


# ---------------------------------------------------------------------------
# Pure-function helper (also used by the API endpoint)
# ---------------------------------------------------------------------------

def _extract_pdf_text(path: Path | str | bytes | io.IOBase) -> tuple[str, int]:
    """Extract all text from a PDF and return ``(text, page_count)``.

    Args:
        path: A filesystem path (``Path`` or ``str``), raw PDF bytes, or a
              file-like object.

    Returns:
        A ``(text, page_count)`` tuple where *text* is the concatenated text
        from every page and *page_count* is the total number of pages.

    Raises:
        ValueError: If the file is not a valid PDF or cannot be parsed.
        ImportError: If ``pypdf`` is not installed.
    """
    try:
        from pypdf import PdfReader  # type: ignore[import]
        from pypdf.errors import PdfReadError  # type: ignore[import]
    except ImportError as exc:
        msg = (
            "pypdf is required for PDF text extraction. "
            "Install it with: pip install pypdf"
        )
        raise ImportError(msg) from exc

    # Normalise the input into something PdfReader can consume
    if isinstance(path, (str, Path)):
        source: str | io.IOBase = str(path)
    else:
        source = path  # bytes or file-like

    try:
        reader = PdfReader(source)
    except PdfReadError as exc:
        msg = f"Failed to read PDF: {exc}"
        raise ValueError(msg) from exc
    except Exception as exc:  # noqa: BLE001
        msg = f"Unexpected error reading PDF: {exc}"
        raise ValueError(msg) from exc

    page_count = len(reader.pages)
    parts: list[str] = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            page_text = ""
        parts.append(page_text)

    text = "\n".join(parts)
    return text, page_count
