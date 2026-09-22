"""Regression tests for resumes that put the date range on its own line,
either above or below the role header.

Date-anchored segmentation assumes each job header carries its own range. Two
real layouts break that assumption in opposite directions:

- the range sits on a line *above* the header ("AUGUST 2018 - PRESENT" then
  "QA AUTOMATION ENGINEER, Alliance Tek Solutions"). Without the range, the
  header cannot open a job, so every bullet in the section piled onto the
  previous entry.
- the title sits on a line *above* its company/date line ("Clinical
  Therapist" then "Orlando Recovery Ctr - Orlando, FL  August 2020 to
  Present"). Treating both as headers produced two entries per job.

One real file also has its years truncated by the PDF text layer
("AUGUST 201 - PRESENT", "20- JUNE 2016"). The missing year cannot be
recovered and is never guessed, but the legible half is still reported.
"""

from app.parsers.experience import _partial_date_line
from app.pipeline.orchestrator import ParsePipeline

_DATE_ABOVE_HEADER = (
    "Erin Acar\n"
    "Tampa, FL | erin.acar@example.com\n"
    "WORK EXPERIENCE\n"
    "AUGUST 2018 - PRESENT\n"
    "QA AUTOMATION ENGINEER, Alliance Tek Solutions\n"
    "● Developed test scripts in Java using Selenium WebDriver and Cucumber.\n"
    "● Implemented automated execution of tests using Maven and Jenkins.\n"
    "Environment: Selenium, Java, Cucumber, Maven\n"
    "JANUARY 2014 - JUNE 2016\n"
    "MANUAL TESTER, Ziraat Bank\n"
    "● Executed and verified test cases and test results.\n"
    "Environment: HP ALM, SQL\n"
).encode("utf-8")


def _parse(payload: bytes):
    return ParsePipeline().parse_bytes(payload, "resume.txt", "text/plain")


def test_a_date_line_above_a_header_opens_that_job_not_the_one_before_it():
    experience = _parse(_DATE_ABOVE_HEADER).data.experience

    assert len(experience) == 2
    first, second = experience
    assert first.job_title == "QA AUTOMATION ENGINEER"
    assert first.company == "Alliance Tek Solutions"
    assert first.start_date == "2018-08"
    assert first.is_current is True
    assert second.job_title == "MANUAL TESTER"
    assert second.company == "Ziraat Bank"
    assert second.start_date == "2014-01"
    assert second.end_date == "2016-06"


def test_bullets_attach_to_the_job_whose_header_precedes_them():
    experience = _parse(_DATE_ABOVE_HEADER).data.experience

    assert len(experience[0].description) == 2
    assert len(experience[1].description) == 1
    assert "Selenium" in experience[0].technologies
    assert "HP ALM" in experience[1].technologies


_TITLE_ABOVE_COMPANY = (
    "Dana Reed\n"
    "Orlando, FL | dana.reed@example.com\n"
    "WORK EXPERIENCE\n"
    "Clinical Therapist\n"
    "Orlando Recovery Ctr - Orlando, FL August 2020 to Present\n"
    "Intake, assessment, family session, individual counseling, referrals.\n"
    "Clinical Program Director\n"
    "Steps Recovery - Apopka, FL April 2019 to August 2020\n"
    "Hiring, referrals, counseling, staffing, training, oversees programs.\n"
).encode("utf-8")


def test_a_title_above_its_company_and_date_line_is_one_job_not_two():
    experience = _parse(_TITLE_ABOVE_COMPANY).data.experience

    assert len(experience) == 2
    first, second = experience
    assert first.job_title == "Clinical Therapist"
    assert first.company == "Orlando Recovery Ctr"
    assert first.location == "Orlando, FL"
    assert first.start_date == "2020-08"
    assert first.is_current is True
    assert second.job_title == "Clinical Program Director"
    assert second.company == "Steps Recovery"
    assert second.start_date == "2019-04"
    assert second.end_date == "2020-08"


def test_a_truncated_year_reports_the_legible_half_and_guesses_nothing():
    # Real PDF text: the start year lost a digit, the end is intact.
    span = _partial_date_line("20- JUNE 2016")
    assert span is not None
    assert span.start is None
    assert span.end == "2016-06"
    assert span.is_current is False

    # Here the start is unreadable but the job is plainly ongoing.
    span = _partial_date_line("AUGUST 201 - PRESENT")
    assert span is not None
    assert span.start is None
    assert span.end is None
    assert span.is_current is True


def test_prose_is_not_mistaken_for_a_truncated_date_line():
    assert _partial_date_line("Designed and delivered the 2019 migration plan") is None
    assert _partial_date_line("Senior Engineer - Acme Corp") is None
