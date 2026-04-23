"""PDF text extraction utility.

This module provides a single pure function, :func:`extract_pdf_text`, that
extracts all text from a PDF source and returns the text together with the
page count.  It is intentionally kept free of any Langflow-specific imports
so it can be used safely from both the component layer and the API layer
without risk of circular imports.

Requires ``pypdf`` (already a project dependency at ``~5.1.0``).
"""

from __future__ import annotations

import io
from pathlib import Path


def extract_pdf_text(
    source: str | Path | bytes | io.IOBase,
) -> tuple[str, int]:
    """Extract all text from a PDF and return ``(text, page_count)``.

    Args:
        source: One of:
            - A filesystem path as a :class:`str` or :class:`~pathlib.Path`.
            - Raw PDF bytes (``bytes`` or ``bytearray``).
            - Any file-like object that supports ``.read()`` (e.g.
              :class:`io.BytesIO`).

    Returns:
        A ``(text, page_count)`` tuple where *text* is the concatenated
        text extracted from every page (pages joined with ``"\\n"``) and
        *page_count* is the total number of pages in the document.

    Raises:
        ImportError: If ``pypdf`` is not installed.
        ValueError: If *source* is not a valid / readable PDF.
    """
    try:
        from pypdf import PdfReader  # type: ignore[import]
        from pypdf.errors import PdfReadError  # type: ignore[import]
    except ImportError as exc:
        msg = (
            "pypdf is required for PDF text extraction. "
            "Install it with: pip install 'pypdf~=5.1.0'"
        )
        raise ImportError(msg) from exc

    # Normalise *source* into something PdfReader accepts.
    # PdfReader accepts: str path, Path, or a file-like object.
    if isinstance(source, (str, Path)):
        reader_input: str | io.IOBase = str(source)
    elif isinstance(source, (bytes, bytearray)):
        reader_input = io.BytesIO(source)
    else:
        # Assume it is already a file-like object.
        reader_input = source  # type: ignore[assignment]

    try:
        reader = PdfReader(reader_input)
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

    return "\n".join(parts), page_count
