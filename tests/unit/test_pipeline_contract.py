from app.core.exceptions import NotImplementedStageError
from app.pipeline.orchestrator import ParsePipeline
from app.schemas.candidate import CandidateDocument
from app.schemas.document import Block, Document
from tests.helpers.sample_documents import simple_txt


def test_parse_pipeline_extracts_candidate_data_for_simple_resume() -> None:
    pipeline = ParsePipeline()
    response = pipeline.parse_bytes(simple_txt(), "resume.txt", "text/plain")

    assert response.status == "success"
    assert response.document_id
    assert response.llm_used is False
    assert response.data.candidate.contact.email == "jane.doe@example.com"
    assert response.data.candidate.name.full == "Jane Doe"
    assert response.data.experience[0].company == "Acme Corp"
    assert response.data.experience[0].job_title == "Software Engineer"
    assert response.data.skills
    assert response.data.skills[0].normalized in {"Python", "Django", "AWS", "PostgreSQL"}


def test_parse_handles_real_resume_name_and_bullets() -> None:
    text = (
        "GUTTIKONDA PURNA CHANDRA REDDY\n"
        "Java Full Stack Developer\n"
        "Guntur, AP | purnachandrareddy75@gmail.com | +91 9640989450\n"
        "WORK EXPERIENCE\n"
        "Associate Software Engineer\n"
        "Feb 2026 – Present\n"
        "Prominent Scientific Pvt. Ltd. | Hyderabad, Telangana\n"
        "● Build and maintain scalable web applications.\n"
        "● Design and implement REST APIs.\n"
    )
    response = ParsePipeline().parse_bytes(text.encode("utf-8"), "resume.txt", "text/plain")
    assert response.data.candidate.name.full == "GUTTIKONDA PURNA CHANDRA REDDY"
    assert response.data.candidate.name.full != "Java Full Stack Developer"
    assert all("●" not in item for item in response.data.experience[0].description)
    assert any("Build and maintain scalable web applications" in item for item in response.data.experience[0].description)


def test_empty_candidate_uses_nulls_and_empty_lists() -> None:
    doc = CandidateDocument()
    dumped = doc.model_dump()
    assert dumped["summary"] is None
    assert dumped["skills"] == []
    assert dumped["experience"] == []
    assert dumped["candidate"]["contact"]["email"] is None


def test_document_plain_text_from_blocks() -> None:
    document = Document(
        blocks=[
            Block(text="Jane Doe", page=1, block_type="paragraph"),
            Block(text="python@example.com", page=1, block_type="paragraph"),
        ]
    )
    assert "Jane Doe" in document.plain_text()
