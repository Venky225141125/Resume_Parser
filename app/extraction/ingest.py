"""Validate uploads before extraction."""

from app.core.config import Settings, get_settings
from app.core.exceptions import EmptyFileError, FileTooLargeError
from app.extraction.sniff import DetectedFile, assert_supported, sniff


def ingest(
    data: bytes,
    filename: str,
    content_type: str | None = None,
    settings: Settings | None = None,
) -> DetectedFile:
    cfg = settings or get_settings()
    if not data:
        raise EmptyFileError()
    if len(data) > cfg.max_upload_bytes:
        raise FileTooLargeError()
    detected = sniff(data, filename, content_type)
    assert_supported(detected)
    return detected
