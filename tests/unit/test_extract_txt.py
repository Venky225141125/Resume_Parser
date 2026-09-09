from pathlib import Path

from app.extraction.service import ExtractionService
from tests.helpers.sample_documents import simple_txt


def test_txt_extracts_lines_and_words() -> None:
    service = ExtractionService()
    document = service.extract(simple_txt(), "resume.txt", "text/plain")
    text = document.plain_text()
    assert "Jane Doe" in text
    assert "jane.doe@example.com" in text
    assert document.metadata.file_type == "txt"
    assert document.metadata.extractor == "txt"
    assert document.metadata.page_count == 1
    assert any(block.text == "Experience" for block in document.blocks)
    assert any(word.text == "Python," or word.text == "Python" for word in document.words)


def test_txt_fixture_file() -> None:
    path = Path("tests/fixtures/resumes/simple.txt")
    data = path.read_bytes()
    document = ExtractionService().extract(data, path.name, "text/plain")
    assert "Jane Doe" in document.plain_text()
