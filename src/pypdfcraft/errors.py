"""Exceptions raised by pdfcraft."""


class PdfCraftError(Exception):
    """Base class of every pdfcraft error."""


class NativeLibraryError(PdfCraftError):
    """libpdfcraft_android.so could not be loaded (wrong CPU/OS, or file not found)."""


class OpenError(PdfCraftError):
    """The file could not be opened as a PDF."""


class PasswordRequired(OpenError):
    """The document needs a password."""


class WrongPassword(OpenError):
    """The password given does not open the document."""


class RenderError(PdfCraftError):
    """A page could not be drawn."""


class NoDocumentError(PdfCraftError):
    """The document id is not open in this session."""


class ToolError(PdfCraftError):
    """A tool failed or was refused (bad arguments, not allowed by the document, ...)."""


class UnknownToolError(PdfCraftError, AttributeError):
    """No tool with that name exists in this engine build."""
