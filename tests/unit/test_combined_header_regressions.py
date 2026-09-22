"""Regression tests for a real-world bug: many resumes put the name and/or
location on the same physical line as the email/phone (a pipe-separated
"contact bar" is extremely common in ATS-style templates, both US and
Indian). The original _extract_name/_extract_location unconditionally
skipped any line containing an email/phone/URL, so if the name or location
shared that line, both came back null even though the resume clearly had
them. See app/parsers/contact.py's _header_segments/_strip_contact_noise.
"""

from app.pipeline.orchestrator import ParsePipeline

US_STYLE_PIPE_HEADER = (
    "Jane Doe | San Francisco, CA 94105 | jane.doe@example.com | +1 415 555 0100\n"
    "Experience\n"
    "Software Engineer at Acme Corp, Jan 2021 - Present\n"
    "- Built REST APIs using Python.\n"
    "Education\n"
    "B.Sc Computer Science, State University, 2019\n"
)

INDIAN_STYLE_GLUED_LOCATION = (
    "Venkatesh Edubilli\n"
    "Hyderabad, Telangana, India 500032 venkatesh.edubilli@example.com +91 8341947811\n"
    "Experience\n"
    "Software Engineer at Example Corp, Jun 2022 - Present\n"
    "- Built REST APIs using Java.\n"
)

INDIAN_STYLE_BULLET_HEADER = (
    "Venkatesh Edubilli • Hyderabad, Telangana • venkatesh.edubilli@example.com • +91 8341947811\n"
    "Experience\n"
    "Software Engineer at Example Corp, Jun 2022 - Present\n"
)


def _parse(text: str):
    return ParsePipeline().parse_bytes(text.encode("utf-8"), "resume.txt", "text/plain")


def test_us_style_pipe_header_extracts_name_and_location_alongside_contact():
    response = _parse(US_STYLE_PIPE_HEADER)
    candidate = response.data.candidate
    assert candidate.name.full == "Jane Doe"
    assert candidate.contact.email == "jane.doe@example.com"
    assert candidate.contact.phone == "+14155550100"
    assert candidate.location.city == "San Francisco"


def test_indian_resume_with_glued_location_and_pin_is_not_dropped():
    response = _parse(INDIAN_STYLE_GLUED_LOCATION)
    candidate = response.data.candidate
    assert candidate.name.full == "Venkatesh Edubilli"
    assert candidate.contact.email == "venkatesh.edubilli@example.com"
    assert candidate.location.city == "Hyderabad"
    assert candidate.location.state == "Telangana"
    assert candidate.location.country == "India"
    assert candidate.location.postal_code == "500032"


def test_bullet_separated_header_extracts_name_and_location():
    response = _parse(INDIAN_STYLE_BULLET_HEADER)
    candidate = response.data.candidate
    assert candidate.name.full == "Venkatesh Edubilli"
    assert candidate.location.city == "Hyderabad"
    assert candidate.location.state == "Telangana"
