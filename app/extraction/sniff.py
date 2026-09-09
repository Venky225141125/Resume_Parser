"""File type detection from magic bytes. Do not trust extensions alone."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from pathlib import Path

from app.core.exceptions import CorruptFileError, UnsupportedMediaError

_PDF_MAGIC = b"%PDF"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_GIF_MAGIC = b"GIF8"
_ZIP_MAGIC = b"PK\x03\x04"
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_RTF_MAGIC = b"{\\rtf"


class FileKind(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    DOC = "doc"
    IMAGE = "image"
    UNKNOWN = "unknown"


_CONTENT_TYPES: dict[FileKind, str] = {
    FileKind.PDF: "application/pdf",
    FileKind.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    FileKind.TXT: "text/plain",
    FileKind.DOC: "application/msword",
    FileKind.IMAGE: "application/octet-stream",
    FileKind.UNKNOWN: "application/octet-stream",
}

_EXTENSION_KIND: dict[str, FileKind] = {
    ".pdf": FileKind.PDF,
    ".docx": FileKind.DOCX,
    ".txt": FileKind.TXT,
    ".text": FileKind.TXT,
    ".doc": FileKind.DOC,
    ".png": FileKind.IMAGE,
    ".jpg": FileKind.IMAGE,
    ".jpeg": FileKind.IMAGE,
    ".tif": FileKind.IMAGE,
    ".tiff": FileKind.IMAGE,
    ".webp": FileKind.IMAGE,
    ".gif": FileKind.IMAGE,
}


@dataclass(frozen=True, slots=True)
class DetectedFile:
    file_type: FileKind
    content_type: str
    extension: str
    extension_mismatch: bool


def sniff(data: bytes, filename: str, declared_content_type: str | None = None) -> DetectedFile:
    """Detect type from payload; compare with extension and declared MIME."""
    extension = Path(filename or "").suffix.lower()
    kind = _sniff_bytes(data)
    if kind is FileKind.UNKNOWN and _declared_or_extension_text(declared_content_type, extension):
        if _looks_like_text(data):
            kind = FileKind.TXT
    if kind is FileKind.UNKNOWN and _looks_like_text(data):
        kind = FileKind.TXT

    declared_kind = _kind_from_mime(declared_content_type)
    extension_kind = _EXTENSION_KIND.get(extension)
    mismatch = False
    if extension_kind is not None and extension_kind is not kind:
        mismatch = True
    if declared_kind is not None and declared_kind is not FileKind.UNKNOWN and declared_kind is not kind:
        mismatch = True

    return DetectedFile(
        file_type=kind,
        content_type=_CONTENT_TYPES[kind],
        extension=extension,
        extension_mismatch=mismatch,
    )


def assert_supported(detected: DetectedFile) -> None:
    if detected.file_type is FileKind.PDF:
        return
    if detected.file_type is FileKind.DOCX:
        return
    if detected.file_type is FileKind.TXT:
        return
    if detected.file_type is FileKind.DOC:
        raise UnsupportedMediaError(
            "Legacy .doc files are not supported in this version. Convert to DOCX or PDF."
        )
    if detected.file_type is FileKind.IMAGE:
        raise UnsupportedMediaError(
            "Image-only resumes are not supported until OCR is enabled. Use a digital PDF or DOCX."
        )
    raise UnsupportedMediaError("Unsupported or unrecognized file type.")


def _sniff_bytes(data: bytes) -> FileKind:
    head = data[:16]
    if head.startswith(_PDF_MAGIC):
        return FileKind.PDF
    if head.startswith(_PNG_MAGIC) or head.startswith(_JPEG_MAGIC) or head.startswith(_GIF_MAGIC):
        return FileKind.IMAGE
    if head.startswith(_OLE_MAGIC):
        return FileKind.DOC
    if head.startswith(_RTF_MAGIC):
        return FileKind.UNKNOWN
    if head.startswith(_ZIP_MAGIC) or head.startswith(b"PK\x05\x06") or head.startswith(b"PK\x07\x08"):
        return _sniff_zip(data)
    return FileKind.UNKNOWN


def _sniff_zip(data: bytes) -> FileKind:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise CorruptFileError("ZIP-based document is corrupt or unreadable.") from exc
    if "word/document.xml" in names:
        return FileKind.DOCX
    if any(name.startswith("xl/") for name in names) or "xl/workbook.xml" in names:
        return FileKind.UNKNOWN
    return FileKind.UNKNOWN


def _looks_like_text(data: bytes) -> bool:
    if not data:
        return False
    if b"\x00" in data[:4096]:
        if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
            return True
        return False
    sample = data[:8192]
    try:
        sample.decode("utf-8")
        return True
    except UnicodeDecodeError:
        printable = sum(32 <= byte < 127 or byte in (9, 10, 13) for byte in sample)
        return (printable / max(len(sample), 1)) > 0.85


def _kind_from_mime(content_type: str | None) -> FileKind | None:
    if not content_type:
        return None
    mime = content_type.split(";")[0].strip().lower()
    mapping = {
        "application/pdf": FileKind.PDF,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileKind.DOCX,
        "application/msword": FileKind.DOC,
        "text/plain": FileKind.TXT,
        "image/png": FileKind.IMAGE,
        "image/jpeg": FileKind.IMAGE,
        "image/tiff": FileKind.IMAGE,
        "image/webp": FileKind.IMAGE,
        "image/gif": FileKind.IMAGE,
    }
    return mapping.get(mime)


def _declared_or_extension_text(declared: str | None, extension: str) -> bool:
    if extension in {".txt", ".text", ".md"}:
        return True
    if declared and declared.split(";")[0].strip().lower() == "text/plain":
        return True
    return False
