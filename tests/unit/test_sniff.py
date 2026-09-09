from app.core.exceptions import CorruptFileError, UnsupportedMediaError
from app.extraction.sniff import FileKind, sniff
from tests.helpers.sample_documents import ole_doc_bytes, png_bytes, simple_docx, simple_pdf, simple_txt


def test_sniff_pdf_ignores_txt_extension() -> None:
    detected = sniff(simple_pdf(), "resume.txt", "text/plain")
    assert detected.file_type is FileKind.PDF
    assert detected.extension_mismatch is True


def test_sniff_docx() -> None:
    detected = sniff(simple_docx(), "cv.docx", None)
    assert detected.file_type is FileKind.DOCX
    assert detected.extension_mismatch is False


def test_sniff_txt() -> None:
    detected = sniff(simple_txt(), "resume.txt", "text/plain")
    assert detected.file_type is FileKind.TXT


def test_sniff_png_is_image() -> None:
    detected = sniff(png_bytes(), "scan.png", "image/png")
    assert detected.file_type is FileKind.IMAGE


def test_sniff_ole_is_doc() -> None:
    detected = sniff(ole_doc_bytes(), "old.doc", "application/msword")
    assert detected.file_type is FileKind.DOC


def test_sniff_bad_zip_is_corrupt() -> None:
    try:
        sniff(b"PK\x03\x04not-a-zip", "file.docx", None)
        raise AssertionError("expected CorruptFileError")
    except CorruptFileError:
        pass


def test_image_and_doc_are_unsupported_by_assert() -> None:
    from app.extraction.sniff import assert_supported

    png = sniff(png_bytes(), "scan.png", None)
    try:
        assert_supported(png)
        raise AssertionError("expected UnsupportedMediaError")
    except UnsupportedMediaError:
        pass
