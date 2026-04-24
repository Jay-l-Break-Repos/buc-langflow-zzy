"""PDF Loader component for Langflow.

Provides a node that accepts a PDF file upload and exposes the raw file
path as a text output.  Actual text extraction will be added in a
subsequent step — this module establishes the foundational node structure
so the component is visible in the UI under the **Document Loaders**
category.
"""

from __future__ import annotations

from langflow.base.data.base_file import BaseFileComponent
from langflow.io import Output
from langflow.schema.data import Data
from langflow.schema.message import Message


class PDFLoaderComponent(BaseFileComponent):
    """Load a PDF file and expose its path as a text output.

    The node appears in the node palette under the **Document Loaders**
    category and accepts a single ``.pdf`` file upload.  Text extraction
    logic will be wired up in the next implementation step.
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
    # Processing (stub — extraction logic added in next step)             #
    # ------------------------------------------------------------------ #

    def process_files(
        self,
        file_list: list[BaseFileComponent.BaseFile],
    ) -> list[BaseFileComponent.BaseFile]:
        """Populate each BaseFile with a placeholder Data object.

        Full PDF text extraction will be implemented in the next step.
        For now each file is annotated with its path so downstream nodes
        can already reference the uploaded file.

        Args:
            file_list: List of validated BaseFile objects representing the
                       uploaded PDF file(s).

        Returns:
            The file list with placeholder Data objects attached.
        """
        for base_file in file_list:
            base_file.data = Data(
                data={
                    "file_path": str(base_file.path),
                    "status": "pending_extraction",
                }
            )
        return file_list

    # ------------------------------------------------------------------ #
    # Output method                                                        #
    # ------------------------------------------------------------------ #

    def load_pdf_content(self) -> Message:
        """Return the PDF file information as a Message.

        Returns:
            Message: A Message object containing file path information.
                     Text extraction will be added in the next step.
        """
        return self.load_files_message()
