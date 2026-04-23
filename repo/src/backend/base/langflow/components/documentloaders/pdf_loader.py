"""PDF Loader component for Langflow.

Provides a node that accepts a PDF file upload and exposes the raw text
content as a Message output for use in downstream flow nodes.

Note: Actual text extraction logic will be wired up in a follow-up step.
      This skeleton establishes the node structure, palette registration,
      and file-upload input so the node appears under "Document Loaders".
"""

from __future__ import annotations

from langflow.base.data.base_file import BaseFileComponent
from langflow.io import Output
from langflow.schema.data import Data
from langflow.schema.message import Message


class PDFLoaderComponent(BaseFileComponent):
    """Load a PDF file and expose its text content as a Message.

    The node appears in the node palette under the **Document Loaders**
    category and accepts a single ``.pdf`` file upload.  Text extraction
    will be implemented in a follow-up step; for now the output returns
    an empty placeholder so the node can be wired into a flow.
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
        """Process uploaded PDF files.

        Currently returns the file list unchanged (skeleton implementation).
        Text extraction logic will be added in a follow-up step.

        Args:
            file_list: List of validated BaseFile objects representing the
                       uploaded PDF file(s).

        Returns:
            The same file list, unmodified, until extraction is wired up.
        """
        # Placeholder: extraction logic will be implemented in the next step.
        # Each BaseFile already carries a Data stub from _validate_and_resolve_paths;
        # we simply return the list as-is so the pipeline does not error out.
        return file_list

    # ------------------------------------------------------------------ #
    # Output method                                                        #
    # ------------------------------------------------------------------ #

    def load_pdf_content(self) -> Message:
        """Return extracted PDF text as a Message.

        Currently returns a placeholder message.  Full extraction will be
        implemented in the follow-up step.

        Returns:
            Message: A Message object containing the (future) extracted text.
        """
        # Skeleton output – real extraction replaces this in the next step.
        return Message(text="")
