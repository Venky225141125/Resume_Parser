from app.extraction.service import ExtractionService
from tests.helpers.sample_documents import simple_docx


def test_docx_preserves_headings_paragraphs_and_tables() -> None:
    document = ExtractionService().extract(simple_docx(), "resume.docx", None)
    assert document.metadata.file_type == "docx"
    assert document.metadata.extractor == "python-docx"
    types = {block.block_type for block in document.blocks}
    assert "heading" in types
    assert "paragraph" in types
    assert "table_cell" in types
    assert document.tables
    assert document.tables[0].rows[1][0] == "Python"
    text = document.plain_text()
    assert "Jane Doe" in text
    assert "Software Engineer at Acme Corp" in text
    headings = [block.text for block in document.blocks if block.block_type == "heading"]
    assert "Experience" in headings
