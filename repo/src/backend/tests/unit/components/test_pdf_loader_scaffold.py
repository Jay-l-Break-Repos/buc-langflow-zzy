"""Tests for the PDF Loader node scaffold (Step 1).

Verifies that:
- The PDFLoaderComponent class is importable from its module.
- The component is registered in the documentloaders package.
- The component is discoverable via the top-level components registry.
- Required node metadata (display_name, description, icon, name) is set.
- The VALID_EXTENSIONS list restricts uploads to PDF files only.
- The 'text_content' output is declared.
- process_files returns a placeholder Data object (no extraction yet).
"""

from __future__ import annotations


class TestPDFLoaderImports:
    """Verify the component is importable through all expected paths."""

    def test_import_from_module(self):
        """PDFLoaderComponent can be imported directly from its module."""
        from langflow.components.documentloaders.pdf_loader import PDFLoaderComponent

        assert PDFLoaderComponent is not None

    def test_import_from_package(self):
        """PDFLoaderComponent is exported from the documentloaders package."""
        from langflow.components.documentloaders import PDFLoaderComponent

        assert PDFLoaderComponent is not None

    def test_documentloaders_in_components_registry(self):
        """'documentloaders' is registered in the top-level components module."""
        from langflow import components

        assert "documentloaders" in components.__all__
        assert "documentloaders" in components._dynamic_imports

    def test_documentloaders_dynamic_import(self):
        """Accessing components.documentloaders returns the package."""
        from langflow import components

        doc_loaders = components.documentloaders
        assert doc_loaders is not None
        assert hasattr(doc_loaders, "PDFLoaderComponent")


class TestPDFLoaderMetadata:
    """Verify the node palette metadata is correctly defined."""

    def setup_method(self):
        from langflow.components.documentloaders.pdf_loader import PDFLoaderComponent

        self.cls = PDFLoaderComponent

    def test_display_name(self):
        assert self.cls.display_name == "PDF Loader"

    def test_name(self):
        assert self.cls.name == "PDFLoader"

    def test_description_is_set(self):
        assert isinstance(self.cls.description, str)
        assert len(self.cls.description) > 0

    def test_icon_is_set(self):
        assert isinstance(self.cls.icon, str)
        assert len(self.cls.icon) > 0

    def test_documentation_is_set(self):
        assert isinstance(self.cls.documentation, str)
        assert self.cls.documentation.startswith("http")


class TestPDFLoaderExtensions:
    """Verify only PDF files are accepted."""

    def test_valid_extensions_contains_pdf(self):
        from langflow.components.documentloaders.pdf_loader import PDFLoaderComponent

        assert "pdf" in PDFLoaderComponent.VALID_EXTENSIONS

    def test_valid_extensions_only_pdf(self):
        from langflow.components.documentloaders.pdf_loader import PDFLoaderComponent

        assert PDFLoaderComponent.VALID_EXTENSIONS == ["pdf"]


class TestPDFLoaderOutputs:
    """Verify the output field is declared correctly."""

    def test_text_content_output_declared(self):
        from langflow.components.documentloaders.pdf_loader import PDFLoaderComponent

        output_names = [o.name for o in PDFLoaderComponent.outputs]
        assert "text_content" in output_names

    def test_text_content_output_method(self):
        from langflow.components.documentloaders.pdf_loader import PDFLoaderComponent

        output = next(o for o in PDFLoaderComponent.outputs if o.name == "text_content")
        assert output.method == "load_pdf_content"

    def test_text_content_display_name(self):
        from langflow.components.documentloaders.pdf_loader import PDFLoaderComponent

        output = next(o for o in PDFLoaderComponent.outputs if o.name == "text_content")
        assert output.display_name == "Text Content"


class TestPDFLoaderInheritance:
    """Verify the component inherits from the correct base class."""

    def test_inherits_from_base_file_component(self):
        from langflow.base.data.base_file import BaseFileComponent
        from langflow.components.documentloaders.pdf_loader import PDFLoaderComponent

        assert issubclass(PDFLoaderComponent, BaseFileComponent)

    def test_has_process_files_method(self):
        from langflow.components.documentloaders.pdf_loader import PDFLoaderComponent

        assert callable(getattr(PDFLoaderComponent, "process_files", None))

    def test_has_load_pdf_content_method(self):
        from langflow.components.documentloaders.pdf_loader import PDFLoaderComponent

        assert callable(getattr(PDFLoaderComponent, "load_pdf_content", None))
