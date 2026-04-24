"""PDF Loader component for Langflow.

Provides a node that accepts a PDF file upload, extracts text from all pages
using ``pypdf``, and exposes the content as a ``Message`` output for downstream
nodes to consume.

After processing, ``self.status`` is set so the node's info panel in the UI
shows extraction status (success/error), page count, and any error message.

Error handling covers:
- Corrupted / invalid PDF files (``pypdf.errors.PdfReadError``)
- Password-protected PDFs (``reader.is_encrypted`` guard)
- Empty PDFs (zero pages or all-blank extraction)
- Unexpected I/O or parsing failures (generic ``Exception`` fallback)
"""

from __future__ import annotations

from pathlib import Path

from langflow.base.data.base_file import BaseFileComponent
from langflow.io import Output
from langflow.schema.data import Data
from langflow.schema.message import Message


class PDFLoaderComponent(BaseFileComponent):
    """Load a PDF file and extract its text content.

    The node appears in the node palette under the **Document Loaders**
    category and accepts a single ``.pdf`` file upload.  Text is extracted
    page-by-page using ``pypdf.PdfReader`` and returned as a ``Message``
    for downstream nodes.

    After each run the node's info panel (``self.status``) is updated with:
    - Extraction status (✅ success / ❌ error)
    - Number of pages processed
    - Error message when extraction fails

    Error conditions (corrupted file, password-protected PDF, empty PDF)
    are captured and surfaced as structured ``Data`` objects so that the
    pipeline can continue or report the problem gracefully.
    """

    # ------------------------------------------------------------------ #
    # Palette metadata                                                     #
    # ------------------------------------------------------------------ #
    display_name = "PDF Loader"
    description = (
        "Upload a PDF file and extract its text content for use in your "
        "workflow. Appears under the Document Loaders category."
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
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _build_status(
        self,
        *,
        success: bool,
        file_name: str,
        page_count: int,
        error: str | None = None,
    ) -> str:
        """Build a human-readable status string for the node's info panel.

        The string is set on ``self.status`` so Langflow's UI can display
        extraction feedback directly on the node after a run.

        Args:
            success:    ``True`` when extraction completed without errors.
            file_name:  Base name of the processed PDF file.
            page_count: Number of pages found in the PDF (0 on error).
            error:      Error description when ``success`` is ``False``.

        Returns:
            A formatted status string.
        """
        if success:
            return (
                f"✅ Extracted successfully\n"
                f"File: {file_name}\n"
                f"Pages: {page_count}"
            )
        return (
            f"❌ Extraction failed\n"
            f"File: {file_name}\n"
            f"Pages: {page_count}\n"
            f"Error: {error or 'Unknown error'}"
        )

    def _extract_text_from_pdf(self, file_path: Path) -> Data:
        """Open *file_path* with ``pypdf`` and return a populated ``Data`` object.

        The returned ``Data`` always contains:

        ``file_path``
            Absolute path to the source PDF (``str``).
        ``status``
            ``"success"`` on a clean extraction, ``"error"`` otherwise.
        ``text``
            Extracted text joined with ``"\\n\\n"`` between pages, or an
            empty string when no text could be retrieved.
        ``page_count``
            Number of pages in the PDF (``int``), or ``0`` on error.
        ``error``  *(only present on failure)*
            Human-readable description of what went wrong.

        Args:
            file_path: Resolved ``Path`` to the PDF file.

        Returns:
            A ``Data`` object with the fields described above.
        """
        # Lazy import — pypdf is an optional dependency at the module level
        # but is declared in pyproject.toml so it will always be present.
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError, PdfStreamError

        str_path = str(file_path)
        file_name = file_path.name
        base_meta: dict = {"file_path": str_path}

        try:
            with file_path.open("rb") as fh:
                try:
                    reader = PdfReader(fh, strict=False)
                except (PdfReadError, PdfStreamError) as exc:
                    msg = f"Corrupted or invalid PDF file: {exc}"
                    self.log(msg)
                    self.status = self._build_status(
                        success=False,
                        file_name=file_name,
                        page_count=0,
                        error=msg,
                    )
                    return Data(
                        data={
                            **base_meta,
                            "status": "error",
                            "error": msg,
                            "page_count": 0,
                            "text": "",
                        }
                    )

                # Guard: password-protected PDFs cannot be read without a key
                if reader.is_encrypted:
                    msg = (
                        "PDF is password-protected. "
                        "Please provide an unencrypted file."
                    )
                    self.log(msg)
                    self.status = self._build_status(
                        success=False,
                        file_name=file_name,
                        page_count=0,
                        error=msg,
                    )
                    return Data(
                        data={
                            **base_meta,
                            "status": "error",
                            "error": msg,
                            "page_count": 0,
                            "text": "",
                        }
                    )

                page_count = len(reader.pages)

                if page_count == 0:
                    msg = "PDF contains no pages."
                    self.log(msg)
                    self.status = self._build_status(
                        success=False,
                        file_name=file_name,
                        page_count=0,
                        error=msg,
                    )
                    return Data(
                        data={
                            **base_meta,
                            "status": "error",
                            "error": msg,
                            "page_count": 0,
                            "text": "",
                        }
                    )

                # Extract text from every page; replace None with empty string
                page_texts: list[str] = []
                for page_num, page in enumerate(reader.pages, start=1):
                    try:
                        raw = page.extract_text() or ""
                        page_texts.append(raw)
                    except Exception as page_exc:  # noqa: BLE001
                        self.log(
                            f"Could not extract text from page {page_num} "
                            f"of '{file_name}': {page_exc}"
                        )
                        page_texts.append("")

                full_text = "\n\n".join(page_texts)

                # Warn (but don't fail) when the PDF appears to be image-only
                if not full_text.strip():
                    self.log(
                        f"No text extracted from '{file_name}'. "
                        "The file may be a scanned/image-only PDF."
                    )

                self.status = self._build_status(
                    success=True,
                    file_name=file_name,
                    page_count=page_count,
                )
                return Data(
                    data={
                        **base_meta,
                        "status": "success",
                        "text": full_text,
                        "page_count": page_count,
                    }
                )

        except FileNotFoundError:
            msg = f"File not found: {file_path}"
            self.log(msg)
            self.status = self._build_status(
                success=False,
                file_name=file_name,
                page_count=0,
                error=msg,
            )
            return Data(
                data={
                    **base_meta,
                    "status": "error",
                    "error": msg,
                    "page_count": 0,
                    "text": "",
                }
            )
        except OSError as exc:
            msg = f"I/O error reading '{file_name}': {exc}"
            self.log(msg)
            self.status = self._build_status(
                success=False,
                file_name=file_name,
                page_count=0,
                error=msg,
            )
            return Data(
                data={
                    **base_meta,
                    "status": "error",
                    "error": msg,
                    "page_count": 0,
                    "text": "",
                }
            )
        except Exception as exc:  # noqa: BLE001
            msg = f"Unexpected error processing '{file_name}': {exc}"
            self.log(msg)
            self.status = self._build_status(
                success=False,
                file_name=file_name,
                page_count=0,
                error=msg,
            )
            return Data(
                data={
                    **base_meta,
                    "status": "error",
                    "error": msg,
                    "page_count": 0,
                    "text": "",
                }
            )

    # ------------------------------------------------------------------ #
    # BaseFileComponent interface                                          #
    # ------------------------------------------------------------------ #

    def process_files(
        self,
        file_list: list[BaseFileComponent.BaseFile],
    ) -> list[BaseFileComponent.BaseFile]:
        """Extract text from each uploaded PDF and attach the result as ``Data``.

        For every ``BaseFile`` in *file_list* the method calls
        :meth:`_extract_text_from_pdf` and stores the returned ``Data``
        object on ``base_file.data``.  Errors are captured inside the
        ``Data`` object (``status="error"``) rather than raising, so the
        pipeline can continue processing remaining files.

        After all files are processed ``self.status`` reflects the aggregate
        result (last file's status for single-file use; summary for multi-file).

        Args:
            file_list: List of validated ``BaseFile`` objects representing
                       the uploaded PDF file(s).

        Returns:
            The same file list with ``Data`` objects attached to each entry.
        """
        for base_file in file_list:
            extracted_data = self._extract_text_from_pdf(base_file.path)
            base_file.data = extracted_data

        # For multi-file runs, set an aggregate status summary
        if len(file_list) > 1:
            success_count = sum(
                1
                for f in file_list
                if f.data and f.data[0].data.get("status") == "success"
            )
            total = len(file_list)
            self.status = (
                f"Processed {total} file(s): "
                f"{success_count} succeeded, {total - success_count} failed."
            )

        return file_list

    # ------------------------------------------------------------------ #
    # Output method                                                        #
    # ------------------------------------------------------------------ #

    def load_pdf_content(self) -> Message:
        """Extract text from the uploaded PDF and return it as a ``Message``.

        Delegates to :meth:`load_files_message` which calls
        :meth:`process_files` internally and serialises the resulting
        ``Data`` objects into a single ``Message`` separated by the
        configured *separator* (default ``"\\n\\n"``).

        Returns:
            ``Message``: The extracted text content ready for downstream
            nodes.  On error the message will contain the error description
            from the ``Data`` object.
        """
        return self.load_files_message()
