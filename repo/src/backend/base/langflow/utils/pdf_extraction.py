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
import re
from pathlib import Path


def _fallback_extract(raw: bytes) -> tuple[str, int]:
    """Regex-based fallback extraction for malformed PDFs.

    Extracts text from PDF stream content operators and counts pages
    by looking for /Type /Page entries.

    Args:
        raw: The raw PDF bytes.

    Returns:
        A ``(text, page_count)`` tuple.
    """
    texts: list[str] = []

    # Find all stream...endstream blocks
    stream_pattern = re.compile(rb"stream\s*\n(.*?)\nendstream", re.DOTALL)
    for match in stream_pattern.finditer(raw):
        stream_data = match.group(1)
        # Find text show operators: (text) Tj
        text_pattern = re.compile(rb"\(([^)]*)\)\s*Tj")
        for text_match in text_pattern.finditer(stream_data):
            try:
                texts.append(text_match.group(1).decode("latin-1"))
            except Exception:  # noqa: BLE001
                pass
        # Also handle TJ array operator: [(text)] TJ
        tj_array_pattern = re.compile(rb"\[(.*?)\]\s*TJ", re.DOTALL)
        for tj_match in tj_array_pattern.finditer(stream_data):
            array_content = tj_match.group(1)
            inner_text_pattern = re.compile(rb"\(([^)]*)\)")
            for inner_match in inner_text_pattern.finditer(array_content):
                try:
                    texts.append(inner_match.group(1).decode("latin-1"))
                except Exception:  # noqa: BLE001
                    pass

    # Count pages: /Type /Page but not /Type /Pages
    page_count = len(re.findall(rb"/Type\s*/Page(?![s])", raw))
    if page_count == 0:
        page_count = 1  # At least 1 page if we found any text

    return "\n".join(texts), page_count


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

    # Read raw bytes for potential fallback extraction
    raw_bytes: bytes | None = None

    # Normalise *source* into something PdfReader accepts.
    if isinstance(source, (str, Path)):
        reader_input: str | io.IOBase = str(source)
        try:
            with open(str(source), "rb") as f:
                raw_bytes = f.read()
        except Exception:  # noqa: BLE001
            pass
    elif isinstance(source, (bytes, bytearray)):
        raw_bytes = bytes(source)
        reader_input = io.BytesIO(source)
    elif hasattr(source, "read"):
        # File-like object: read it to get raw bytes, then reset
        try:
            raw_bytes = source.read()  # type: ignore[union-attr]
            source.seek(0)  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass
        reader_input = source  # type: ignore[assignment]
    else:
        reader_input = source  # type: ignore[assignment]

    # Validate it looks like a PDF
    if raw_bytes is not None and not raw_bytes.strip().startswith(b"%PDF"):
        msg = "Not a valid PDF file (missing %PDF header)"
        raise ValueError(msg)

    # Try pypdf first with strict=False, then strict=True
    reader = None
    last_exc: Exception | None = None

    for strict in (False, True):
        try:
            if isinstance(reader_input, str):
                reader = PdfReader(reader_input, strict=strict)
            else:
                if hasattr(reader_input, "seek"):
                    reader_input.seek(0)  # type: ignore[union-attr]
                reader = PdfReader(reader_input, strict=strict)
            break
        except (PdfReadError, Exception) as exc:  # noqa: BLE001
            last_exc = exc
            if hasattr(reader_input, "seek"):
                reader_input.seek(0)  # type: ignore[union-attr]

    if reader is not None:
        try:
            page_count = len(reader.pages)
            parts: list[str] = []
            for page in reader.pages:
                try:
                    page_text = page.extract_text() or ""
                except Exception:  # noqa: BLE001
                    page_text = ""
                parts.append(page_text)
            text = "\n".join(parts)
            if text.strip():
                return text, page_count
        except Exception:  # noqa: BLE001
            pass

    # Fallback: regex-based extraction for malformed PDFs
    if raw_bytes is not None:
        try:
            text, page_count = _fallback_extract(raw_bytes)
            if text.strip():
                return text, page_count
        except Exception:  # noqa: BLE001
            pass

    # If we got here, nothing worked
    if last_exc is not None:
        msg = f"Failed to read PDF: {last_exc}"
        raise ValueError(msg) from last_exc

    msg = "Failed to extract text from PDF"
    raise ValueError(msg)
