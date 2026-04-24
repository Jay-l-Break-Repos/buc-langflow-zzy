"""PDF Loader component for Langflow — Step 1 scaffold.

Provides a node that accepts a PDF file upload and exposes a text output
for downstream nodes to consume.  Actual PDF text extraction will be
implemented in a subsequent step; for now the output method returns a
placeholder ``Message`` so the node can be wired up and tested end-to-end
in the UI.

The node appears in the node palette under the **Document Loaders** category
and accepts a single ``.pdf`` file upload via the standard ``FileInput``
provided by :class:`~langflow.base.data.base_file.BaseFileComponent`.
"""

from __future__ import annotations

from langflow.base.data.base_file import BaseFileComponent
from langflow.io import Output
from langflow.schema.data import Data
from langflow.schema.message import Message


class PDFLoaderComponent(BaseFileComponent):
    """Load a PDF file and expose its text content as a Message output.

    This is the **Step 1 scaffold**.  The node is fully wired into the
    Langflow palette under the *Document Loaders* category and accepts a
    ``.pdf`` file upload.  The output currently returns a placeholder
    ``Message``; real text extraction will be added in the next step.

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
    # BaseFileComponent interface                                          #
    # ------------------------------------------------------------------ #

    def process_files(
        self,
        file_list: list[BaseFileComponent.BaseFile],
    ) -> list[BaseFileComponent.BaseFile]:
        """Attach placeholder ``Data`` to each uploaded file.

        In this scaffold each file receives a ``Data`` object whose
        ``status`` field is ``"pending"`` and whose ``text`` field contains
        a placeholder string.  Real extraction logic will replace this body
        in the next implementation step.

        Args:
            file_list: Validated ``BaseFile`` objects representing the
                       uploaded PDF file(s).

        Returns:
            The same list with placeholder ``Data`` attached to every entry.
        """
        for base_file in file_list:
            file_name = base_file.path.name
            base_file.data = Data(
                data={
                    "file_path": str(base_file.path),
                    "status": "pending",
                    "text": f"[PDF text extraction not yet implemented for '{file_name}']",
                    "page_count": 0,
                }
            )
        return file_list

    # ------------------------------------------------------------------ #
    # Output method                                                        #
    # ------------------------------------------------------------------ #

    def load_pdf_content(self) -> Message:
        """Return the (placeholder) text content of the uploaded PDF.

        Delegates to :meth:`~langflow.base.data.base_file.BaseFileComponent.load_files_message`
        which calls :meth:`process_files` internally and serialises the
        resulting ``Data`` objects into a single ``Message``.

        Returns:
            ``Message``: Placeholder text ready for downstream nodes.
                         Real extracted text will be returned here once
                         PDF extraction is implemented.
        """
        self.status = "PDF Loader ready — extraction not yet implemented."
        return self.load_files_message()
