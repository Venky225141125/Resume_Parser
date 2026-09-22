"""Regression tests for a real-world resume where one Experience entry was
being split into several bogus ones. Root causes, found by inspecting the
actual PDF's extracted geometry and section boundaries:

1. `_block_lines`' wrap-vs-new-line gap threshold was tuned against one PDF's
   spacing (~0.4pt); a different PDF's ordinary word-wrap gap measured
   ~1.8pt, so the wrapped continuation of a bullet ("feature development,
   and coding best practices.") was read as a bogus new experience entry.
   Fixed by also treating a lowercase, non-bulleted line as a continuation
   regardless of the exact gap. This test uses the exact bbox values
   measured on the real PDF (see app/parsers/support.py's _block_lines).
2. A bullet ending in "...improved overall system stability and user
   experience." made the section detector's trailing-heading matcher
   misfire on the (lowercase, mid-sentence) word "experience", incorrectly
   closing and reopening the Experience section — and since Projects sat
   between the two "experience"-labeled sections, its content got spliced
   into the middle of Experience as fake job entries.
3. "Software Engineer - I" (a seniority-level suffix, not a company) was
   split into job_title="Software Engineer", company="I".
"""

from app.parsers.support import _block_lines
from app.pipeline.orchestrator import ParsePipeline
from app.schemas.document import BBox, Block, Line

# bbox values measured on the real PDF that exposed this bug
_BULLET_LINE_BBOX = BBox(x0=61.53, y0=285.98, x1=544.35, y1=297.17)
_WRAP_LINE_BBOX = BBox(x0=70.80, y0=298.999, x1=270.51, y1=308.96)


def test_wide_gap_wrap_continuation_merges_when_it_starts_lowercase():
    bullet_text = (
        "• Collaborated with product managers and developers in an Agile "
        "Scrum environment, contributing to code reviews,"
    )
    wrap_text = "feature development, and coding best practices."
    block = Block(
        text=f"{bullet_text}\n{wrap_text}",
        page=1,
        bbox=BBox(x0=61.53, y0=285.98, x1=544.35, y1=308.96),
        block_type="list_item",
        confidence=1.0,
        lines=[
            Line(text=bullet_text, page=1, bbox=_BULLET_LINE_BBOX, confidence=1.0),
            Line(text=wrap_text, page=1, bbox=_WRAP_LINE_BBOX, confidence=1.0),
        ],
    )
    # The 1.83pt gap between these two real lines exceeds the tuned
    # threshold — confirms this fixture reproduces the actual bug geometry.
    assert _WRAP_LINE_BBOX.y0 - _BULLET_LINE_BBOX.y1 > 1.0
    lines = _block_lines(block)
    assert lines == [f"{bullet_text} {wrap_text}"]


SECTION_SPLIT_RESUME = (
    "JANE DOE\n"
    "EXPERIENCE\n"
    "Software Engineer - I Apr 2025 - Present\n"
    "Example Corp\n"
    "- Debugged and resolved issues, optimized performance, and improved overall system stability and user experience.\n"
    "- Shipped three major releases on schedule.\n"
    "PROJECTS\n"
    "Widget Dashboard React, Node.js\n"
    "- Built an internal analytics dashboard used by 40+ engineers.\n"
    "CERTIFICATIONS\n"
    "- Example Certification - Example Body (2022)\n"
)


def _parse(text: str):
    return ParsePipeline().parse_bytes(text.encode("utf-8"), "resume.txt", "text/plain")


def test_prose_ending_in_a_taxonomy_word_does_not_reopen_a_section():
    response = _parse(SECTION_SPLIT_RESUME)
    assert len(response.data.experience) == 1
    assert response.data.experience[0].company == "Example Corp"
    assert not any("Widget Dashboard" in (item.company or "") for item in response.data.experience)


def test_projects_are_not_spliced_into_experience():
    response = _parse(SECTION_SPLIT_RESUME)
    names = [item.name or "" for item in response.data.projects]
    assert any("Widget Dashboard" in name for name in names)


def test_seniority_level_suffix_stays_part_of_the_job_title():
    response = _parse(SECTION_SPLIT_RESUME)
    role = response.data.experience[0]
    assert role.job_title == "Software Engineer - I"
    assert role.company == "Example Corp"
