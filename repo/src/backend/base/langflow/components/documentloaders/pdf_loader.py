"""PDF Loader component for Langflow.

Provides a node that accepts a PDF file upload, extracts text from every
page using ``pypdf``, and exposes the result as a ``Message`` output for
downstream nodes to consume.

The node appears in the node palette under the **Document Loaders** category
and accepts ``.pdf`` files (directly or inside a ZIP/TAR bundle) via the
standard ``FileInput`` provided by
:class:`~langflow.base.data.base_file.BaseFileComponent`.

Error handling
--------------
* **Corrupted / unreadable PDFs** — a ``PdfReadError`` or ``PdfStreamError``
  is caught; the ``Data`` object for that file gets an ``error`` field and
  an empty ``text`` field so downstream nodes can detect the failure.
* **Password-protected PDFs** — a ``FileNotDecryptedError`` is caught and
  surfaced the same way.  The node does *not* attempt to decrypt files.
* **Silent errors** — when the ``silent_errors`` input is enabled the
  component logs the problem and continues; otherwise it re-raises.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError, PdfStreamError

from langflow.base.data.base_file import BaseFileComponent
from langflow.io import Output
from langflow.schema.data import Data
from langflow.schema.message import Message


class PDFLoaderComponent(BaseFileComponent):
    """Load a PDF file and expose its text content as a Message output.

    Uses ``pypdf.PdfReader`` to extract text from every page of the uploaded
    PDF.  The extracted text, page count, and file metadata are stored in a
    :class:`~langflow.schema.data.Data` object and returned as a
    :class:`~langflow.schema.message.Message` by :meth:`load_pdf_content`.

    Attributes:
        display_name: Human-readable label shown in the palette and on the node.
        description:  Short description shown in the palette tooltip.
        icon:         Lucide icon name rendered on the node card.
        name:         Internal component identifier used by the registry.
        VALID_EXTENSIONS: File extensions accepted by the file-upload input.
        outputs:      List of :class:`~langflow.io.Output` descriptors.
    """

    # ------------------------------------------------------------------ #
    # Palette / registry metadata                                          #
    # ------------------------------------------------------------------ #
    display_name: str = "PDF Loader"
    description: str = (
        "Upload a PDF file and extract its text content for use in your "
        "workflow. Appears under the Document Loaders category."
    )
    documentation: str = "https://docs.langflow.org/components-data"
    icon: str = "file-text"
    name: str = "PDFLoader"

    # ------------------------------------------------------------------ #
    # Accepted file types (drives the FileInput filter in the UI)         #
    # ------------------------------------------------------------------ #
    VALID_EXTENSIONS: list[str] = ["pdf"]

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

    def _extract_text_from_pdf(self, path: Path) -> tuple[str, int]:
        """Extract all text from a PDF file using ``pypdf``.

        Opens the file at *path*, iterates over every page, and joins the
        per-page text with ``"\\n\\n"``.  Empty pages contribute an empty
        string so the page count is always accurate.

        Args:
            path: Absolute path to the ``.pdf`` file on disk.

        Returns:
            A ``(text, page_count)`` tuple where *text* is the concatenated
            text of all pages and *page_count* is the total number of pages
            in the document.

        Raises:
            FileNotDecryptedError: If the PDF is password-protected and has
                not been decrypted.
            PdfReadError: If the file is corrupted or cannot be parsed.
            PdfStreamError: If an internal stream error occurs while reading.
        """
        with path.open("rb") as fh:
            raw = fh.read()

        reader = PdfReader(io.BytesIO(raw))

        # Raise immediately if the file is encrypted and we have no password.
        if reader.is_encrypted:
            # Attempt a no-password decrypt (handles PDFs with empty owner pwd)
            from pypdf import PasswordType  # local import to keep top-level clean

            result = reader.decrypt("")
            if result == PasswordType.NOT_DECRYPTED:
                msg = (
                    f"'{path.name}' is password-protected. "
                    "Provide the password or use an unencrypted copy."
                )
                raise FileNotDecryptedError(msg)

        page_count = len(reader.pages)
        page_texts: list[str] = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            page_texts.append(extracted)

        return "\n\n".join(page_texts), page_count

    # ------------------------------------------------------------------ #
    # BaseFileComponent interface                                          #
    # ------------------------------------------------------------------ #

    def process_files(
        self,
        file_list: list[BaseFileComponent.BaseFile],
    ) -> list[BaseFileComponent.BaseFile]:
        """Extract text from each uploaded PDF and attach it as ``Data``.

        For every :class:`~langflow.base.data.base_file.BaseFileComponent.BaseFile`
        in *file_list* the method:

        1. Opens the PDF with :meth:`_extract_text_from_pdf`.
        2. Stores the extracted text, page count, and file path in a
           :class:`~langflow.schema.data.Data` object.
        3. Attaches the ``Data`` to ``base_file.data``.

        If extraction fails the error is caught and an error ``Data`` object
        is attached instead.  When ``silent_errors`` is ``False`` the
        exception is re-raised after logging.

        Args:
            file_list: Validated ``BaseFile`` objects representing the
                       uploaded PDF file(s).

        Returns:
            The same list with populated ``Data`` attached to every entry.
        """
        for base_file in file_list:
            file_path = base_file.path
            file_name = file_path.name

            try:
                text, page_count = self._extract_text_from_pdf(file_path)
                base_file.data = Data(
                    data={
                        "file_path": str(file_path),
                        "file_name": file_name,
                        "page_count": page_count,
                        "text": text,
                    }
                )
                self.log(f"Extracted {page_count} page(s) from '{file_name}'.")

            except FileNotDecryptedError as exc:
                error_msg = (
                    f"'{file_name}' is password-protected and could not be "
                    f"decrypted: {exc}"
                )
                self.log(error_msg)
                base_file.data = Data(
                    data={
                        "file_path": str(file_path),
                        "file_name": file_name,
                        "page_count": 0,
                        "text": "",
                        "error": error_msg,
                    }
                )
                if not self.silent_errors:
                    raise

            except (PdfReadError, PdfStreamError) as exc:
                error_msg = f"Failed to read '{file_name}': {exc}"
                self.log(error_msg)
                base_file.data = Data(
                    data={
                        "file_path": str(file_path),
                        "file_name": file_name,
                        "page_count": 0,
                        "text": "",
                        "error": error_msg,
                    }
                )
                if not self.silent_errors:
                    raise

        return file_list

    # ------------------------------------------------------------------ #
    # Output method                                                        #
    # ------------------------------------------------------------------ #

    def load_pdf_content(self) -> Message:
        """Extract and return the text content of the uploaded PDF(s).

        Delegates to
        :meth:`~langflow.base.data.base_file.BaseFileComponent.load_files_message`
        which calls :meth:`process_files` internally and serialises the
        resulting :class:`~langflow.schema.data.Data` objects into a single
        :class:`~langflow.schema.message.Message`.

        The ``status`` attribute is updated with a human-readable summary
        (e.g. ``"Extracted text from 5 page(s) across 1 file(s)."``) so the
        Langflow UI can display progress information on the node card.

        Returns:
            :class:`~langflow.schema.message.Message` containing the
            extracted text from all uploaded PDF pages, ready for downstream
            nodes.
        """
        # Run the extraction pipeline and collect Data objects.
        data_list = self.load_files_base()

        # Build a human-readable status summary from the extracted Data.
        total_pages = 0
        error_files: list[str] = []
        for data in data_list:
            if isinstance(data, Data) and isinstance(data.data, dict):
                total_pages += data.data.get("page_count", 0)
                if "error" in data.data:
                    error_files.append(data.data.get("file_name", "unknown"))

        file_count = len(data_list)
        if error_files:
            self.status = (
                f"Completed with errors on {len(error_files)} file(s): "
                + ", ".join(error_files)
                + f". Extracted text from {total_pages} page(s) across "
                + f"{file_count - len(error_files)} successful file(s)."
            )
        else:
            self.status = (
                f"Extracted text from {total_pages} page(s) across "
                f"{file_count} file(s)."
            )

        # Serialise Data objects into a Message for downstream nodes.
        if not data_list:
            return Message(text="")

        sep: str = getattr(self, "separator", "\n\n") or "\n\n"
        parts: list[str] = []
        for data in data_list:
            if isinstance(data, Data) and isinstance(data.data, dict):
                parts.append(data.data.get("text", "") or "")
            else:
                parts.append(str(data))

        return Message(text=sep.join(parts))
