"""Regression test for a real-world layout bug found while debugging a
user-supplied resume: a large-font name sharing a header row with a
small-font "Location: ..." field, immediately followed by a second
small-font row (link bar + "Email: ... Mobile: ..."). The old row-grouping
compared each new PDF line against the whole row's accumulated min/max
y-envelope; the tall name line stretched that envelope down far enough to
falsely swallow the *next* visual row too, merging all 4 header lines into
one garbled string (name became "JANE DOE Portfolio | LinkedIn | GitHub...",
location became "5551234567 Location: ..."). See
tests/helpers/sample_documents.py:large_font_name_two_column_header_pdf and
app/parsers/support.py's _row_groups/_block_lines.
"""

from app.pipeline.orchestrator import ParsePipeline
from tests.helpers.sample_documents import large_font_name_two_column_header_pdf


def _parse():
    return ParsePipeline().parse_bytes(
        large_font_name_two_column_header_pdf(), "resume.pdf", "application/pdf"
    )


def test_large_font_name_is_not_merged_with_the_next_header_row():
    response = _parse()
    candidate = response.data.candidate
    assert candidate.name.full == "JANE DOE"


def test_phone_and_email_are_not_swallowed_into_the_location_field():
    response = _parse()
    candidate = response.data.candidate
    assert candidate.contact.email == "jane.doe@example.com"
    assert candidate.contact.phone is not None
    assert candidate.location.raw is not None
    assert "5551234567" not in candidate.location.raw
    assert candidate.location.city == "Example City"
