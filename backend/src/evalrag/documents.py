"""Bounded parsers for the supported upload formats."""

from io import BytesIO
from pathlib import PurePath

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class DocumentError(ValueError):
    pass


MEDIA_TYPES = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown"}


def extract_pages(
    filename: str,
    data: bytes,
    *,
    max_bytes: int = 10_000_000,
    max_pages: int = 200,
    max_characters: int = 1_000_000,
) -> list[tuple[int, str]]:
    suffix = PurePath(filename).suffix.lower()
    if suffix not in MEDIA_TYPES:
        raise DocumentError("Supported formats are PDF, TXT and Markdown")
    if not data or len(data) > max_bytes:
        raise DocumentError("File size must be between 1 byte and the configured limit")
    if suffix == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise DocumentError("File does not contain a valid PDF header")
        try:
            reader = PdfReader(BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise DocumentError("Encrypted PDFs are not supported")
            if len(reader.pages) > max_pages:
                raise DocumentError("PDF exceeds the page limit")
            pages = []
            length = 0
            for number, page in enumerate(reader.pages, start=1):
                content_stream = page.get_contents()
                if content_stream and len(content_stream.get_data()) > 10_000_000:
                    raise DocumentError("PDF page exceeds the decompressed content limit")
                text = page.extract_text() or ""
                length += len(text)
                if length > max_characters:
                    raise DocumentError("Document exceeds the extracted text limit")
                pages.append((number, text))
        except (PdfReadError, ValueError, KeyError, RecursionError) as exc:
            if isinstance(exc, DocumentError):
                raise
            raise DocumentError("PDF could not be parsed") from exc
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentError("Text documents must use UTF-8 encoding") from exc
        if "\x00" in text or any(ord(char) < 32 and char not in "\r\n\t\f" for char in text):
            raise DocumentError("Binary content is not a text document")
        if len(text) > max_characters:
            raise DocumentError("Document exceeds the extracted text limit")
        pages = [(1, text)]
    if not any(text.strip() for _, text in pages):
        raise DocumentError("No extractable text; scanned PDFs require OCR before upload")
    return pages
