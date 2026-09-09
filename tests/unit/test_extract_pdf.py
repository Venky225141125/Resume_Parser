from app.core.exceptions import CorruptFileError, EncryptedDocumentError, ExtractionError
from app.extraction.service import ExtractionService
from tests.helpers.sample_documents import empty_text_pdf, encrypted_pdf, simple_pdf, simple_txt


def test_pdf_extracts_text_pages_and_bboxes() -> None:
    document = ExtractionService().extract(simple_pdf(), "resume.pdf", "application/pdf")
    assert document.metadata.file_type == "pdf"
    assert document.metadata.extractor == "pymupdf"
    assert document.metadata.page_count == 1
    assert document.metadata.needs_ocr is False
    assert "Jane Doe" in document.plain_text()
    assert "jane.doe@example.com" in document.plain_text()
    assert any(block.bbox is not None for block in document.blocks)
    assert any(word.bbox is not None for word in document.words)
    assert all(page.number >= 1 for page in document.pages)


def test_pdf_two_column_assigns_columns() -> None:
    document = ExtractionService().extract(simple_pdf(two_column=True), "cols.pdf", None)
    assert document.metadata.column_count == 2
    left = [block.text for block in document.blocks if block.column == 0]
    right = [block.text for block in document.blocks if block.column == 1]
    assert any("Python" in text for text in left)
    assert any("Acme" in text for text in right)


def test_pdf_repeating_header_marked() -> None:
    document = ExtractionService().extract(
        simple_pdf(pages=2, header="Confidential Resume"),
        "header.pdf",
        None,
    )
    headers = [block.text for block in document.blocks if block.block_type == "header"]
    assert any("Confidential" in text for text in headers)


def test_sparse_pdf_flags_needs_ocr() -> None:
    document = ExtractionService().extract(empty_text_pdf(), "scan.pdf", None)
    assert document.metadata.needs_ocr is True
    assert document.metadata.ocr_used is False
    assert document.metadata.char_count < 40


def test_encrypted_pdf_raises() -> None:
    try:
        ExtractionService().extract(encrypted_pdf(), "secret.pdf", None)
        raise AssertionError("expected EncryptedDocumentError")
    except EncryptedDocumentError as exc:
        assert exc.code == "encrypted_pdf"


def test_corrupt_pdf_raises() -> None:
    try:
        ExtractionService().extract(b"%PDF-1.4\n%not-a-real-pdf", "bad.pdf", None)
        raise AssertionError("expected corrupt or extraction error")
    except (CorruptFileError, ExtractionError):
        pass


def test_txt_payload_with_pdf_name_is_detected_as_text() -> None:
    document = ExtractionService().extract(simple_txt(), "resume.pdf", "application/pdf")
    assert document.metadata.file_type == "txt"
    assert document.metadata.extension_mismatch is True
