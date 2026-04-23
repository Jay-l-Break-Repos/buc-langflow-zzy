"""PDF Loader component for Langflow.

Provides a node that accepts a PDF file upload and extracts the text
content for use in downstream flow nodes.

The node appears in the node palette under "Document Loaders" and
accepts a single ``.pdf`` file upload.
"""

from __future__ import annotations

from langflow.base.data.base_file import BaseFileComponent
from langflow.io import Output
from langflow.schema.data import Data
from langflow.schema.message import Message
from langflow.utils.pdf_extraction import extract_pdf_text


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
                text, page_count = extract_pdf_text(base_file.path)
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
