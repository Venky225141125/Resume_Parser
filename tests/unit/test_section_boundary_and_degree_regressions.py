"""Regression tests for a real-world resume that broke section detection and
the education parser together: creatively-worded headings ("VCU Practical
Experience:", "Personal Accomplishments", "Continuous Education, Licenses
and Certificates", "References:") were invisible to exact-alias-only
heading matching, so everything after "Education" — including unrelated
experience bullets, awards, and references — got absorbed into one giant
education section, and the M.E./B.E. degree regex (missing word
boundaries) then matched the bare substring "me" inside ordinary words
across all of that swept-in prose, producing dozens of bogus "M.E."
education entries. See tests/helpers/sample_documents.py for the synthetic
(non-PII) fixture that reproduces the layout.
"""

from app.pipeline.orchestrator import ParsePipeline
from tests.helpers.sample_documents import creative_headings_pdf


def _parse():
    return ParsePipeline().parse_bytes(creative_headings_pdf(), "resume.pdf", "application/pdf")


def test_creatively_worded_headings_are_recognized_as_section_boundaries():
    response = _parse()
    assert len(response.data.education) == 1
    assert response.data.education[0].degree == "Bachelor of Arts"


def test_experience_after_education_is_not_absorbed_into_education():
    response = _parse()
    assert len(response.data.experience) == 1
    role = response.data.experience[0]
    assert role.job_title == "AR/VR/XR Project Manager"
    assert role.company == "Acme Experiences"
    assert any("Guided new customers" in item for item in role.description)


def test_awards_after_experience_are_not_absorbed_into_education():
    response = _parse()
    assert len(response.data.awards) == 1
    assert "Pioneered a VR experience" in response.data.awards[0].name


def test_ordinary_prose_containing_bare_me_does_not_produce_bogus_me_degree():
    response = _parse()
    degrees = [item.degree_normalized for item in response.data.education]
    assert "M.E." not in degrees
    assert len(response.data.education) == 1
