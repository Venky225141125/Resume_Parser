from app.core.exceptions import EmptyFileError, FileTooLargeError, UnsupportedMediaError
from app.core.config import Settings
from app.extraction.service import ExtractionService
from tests.helpers.sample_documents import ole_doc_bytes, png_bytes, simple_txt


def test_empty_file_rejected() -> None:
    try:
        ExtractionService().extract(b"", "resume.txt", "text/plain")
        raise AssertionError("expected EmptyFileError")
    except EmptyFileError as exc:
        assert exc.code == "empty_file"


def test_file_too_large_rejected() -> None:
    settings = Settings(max_upload_bytes=4)
    try:
        ExtractionService(settings=settings).extract(simple_txt(), "resume.txt", "text/plain")
        raise AssertionError("expected FileTooLargeError")
    except FileTooLargeError as exc:
        assert exc.code == "file_too_large"


def test_png_rejected_until_ocr() -> None:
    try:
        ExtractionService().extract(png_bytes(), "scan.png", "image/png")
        raise AssertionError("expected UnsupportedMediaError")
    except UnsupportedMediaError as exc:
        assert exc.code == "unsupported_media"


def test_legacy_doc_rejected() -> None:
    try:
        ExtractionService().extract(ole_doc_bytes(), "old.doc", "application/msword")
        raise AssertionError("expected UnsupportedMediaError")
    except UnsupportedMediaError as exc:
        assert "doc" in exc.message.lower()
