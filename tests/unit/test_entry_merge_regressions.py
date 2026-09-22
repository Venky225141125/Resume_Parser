"""Two entries must never be reported as one.

Two independent causes produced the same symptom — consecutive jobs, and
consecutive projects, collapsing into a single entry:

1. The wrap-rejoining pass treated "the bullet above did not end in a full
   stop" as proof that the next line continued it. Plenty of resumes simply
   omit the trailing period, so the *next entry's header* was appended to
   the bullet and its entry vanished.
2. Splitting a block at a section heading rebuilt it as one synthetic line
   holding the block's outer bbox. With every per-line box gone,
   `_block_lines` could no longer group rows, and the whole remainder of the
   section came back as a single string.
"""

from app.parsers.support import _merge_wrapped_lines, section_lines
from app.pipeline.orchestrator import ParsePipeline
from app.schemas.document import BBox, Block, Line
from app.sections.detector import TaxonomySectionDetector

_TWO_OF_EACH = (
    "Dana Cole\n"
    "Austin, TX | dana.cole@example.com\n"
    "WORK EXPERIENCE\n"
    "Senior Engineer Jan 2021 - Present\n"
    "Acme Corp - Austin, TX\n"
    "• Built the billing service and shipped it to production\n"
    "Junior Engineer Jun 2019 - Dec 2020\n"
    "Globex Inc - Dallas, TX\n"
    "• Maintained the reporting pipeline\n"
    "PROJECTS\n"
    "Inventory Tracker\n"
    "Tech Stack: Java, MySQL\n"
    "• Built a stock tracking tool for warehouse staff\n"
    "Weather Dashboard\n"
    "Tech Stack: Python, Flask\n"
    "• Charted forecast data from a public API\n"
).encode("utf-8")


def _parse(payload: bytes):
    return ParsePipeline().parse_bytes(payload, "resume.txt", "text/plain").data


def test_two_jobs_after_a_bullet_without_a_full_stop_stay_two_jobs():
    experience = _parse(_TWO_OF_EACH).experience

    assert [item.job_title for item in experience] == ["Senior Engineer", "Junior Engineer"]
    assert experience[0].company == "Acme Corp"
    assert experience[1].company == "Globex Inc"
    assert experience[1].start_date == "2019-06"


def test_two_projects_after_a_bullet_without_a_full_stop_stay_two_projects():
    projects = _parse(_TWO_OF_EACH).projects

    assert [item.name for item in projects] == ["Inventory Tracker", "Weather Dashboard"]
    assert projects[0].technologies == ["Java", "MySQL"]
    assert projects[1].technologies == ["Python", "Flask"]


def test_an_entry_header_is_never_absorbed_into_the_bullet_above_it():
    lines = [
        "• Built the billing service and shipped it to production",
        "Junior Engineer Jun 2019 - Dec 2020",
    ]

    assert _merge_wrapped_lines(lines) == lines


def test_a_genuine_wrap_tail_is_still_rejoined():
    # Long bullet that runs out of room, continued by a line that closes the
    # sentence it left open. Neither half stands alone.
    lines = [
        "• Designed, developed and implemented a POM based automation "
        "testing framework utilizing Java, and Selenium",
        "WebDriver.",
    ]

    merged = _merge_wrapped_lines(lines)

    assert len(merged) == 1
    assert merged[0].endswith("Java, and Selenium WebDriver.")


def test_a_short_bullet_does_not_absorb_the_line_below_it():
    # Text only wraps when it ran out of room, so a short bullet cannot have
    # wrapped - even if the line below closes a sentence.
    lines = ["• Ran the daily standup", "Acme Corp."]

    assert _merge_wrapped_lines(lines) == lines


def _heading_block() -> Block:
    """A block whose heading shares it with the items beneath — the shape
    that forced the detector to split and rebuild the block."""
    texts = [
        "Academic Projects",
        "Inventory Tracker",
        "• Built a stock tracking tool",
        "Weather Dashboard",
        "• Charted forecast data",
    ]
    lines = [
        Line(
            text=text,
            page=1,
            bbox=BBox(x0=72.0, y0=100.0 + index * 15, x1=300.0, y1=112.0 + index * 15),
            confidence=1.0,
        )
        for index, text in enumerate(texts)
    ]
    return Block(
        text="\n".join(texts),
        page=1,
        bbox=BBox(x0=72.0, y0=100.0, x1=300.0, y1=172.0),
        block_type="paragraph",
        confidence=1.0,
        lines=lines,
    )


def test_splitting_a_block_at_a_heading_keeps_the_individual_line_boxes():
    from app.schemas.document import Document

    document = Document(blocks=[_heading_block()], pages=[], metadata={})
    sections = TaxonomySectionDetector().detect(document)

    lines = section_lines(sections, "projects")

    # One line per item: with the boxes collapsed this came back as a single
    # string and both projects merged into one.
    assert "Inventory Tracker" in lines
    assert "Weather Dashboard" in lines
    assert not any("\n" in line for line in lines)
    # The heading itself is consumed, not re-introduced as an item.
    assert "Academic Projects" not in lines
