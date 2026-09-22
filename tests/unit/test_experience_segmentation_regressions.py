"""Regression tests for experience-entry segmentation.

The parser used to decide entry boundaries from the *shape* of a line —
short, capitalized, contains a dash or comma. Real resumes put the company
and location on their own line directly beneath the role header, and that
line has exactly that shape, so every job in a two-line-header resume split
into two entries: one holding the title and dates, a phantom one holding the
company. On the local corpus this inflated 313 real entries to 457.

Boundaries now come from date ranges instead, which is the structure a
person reads first: scan the dates, and each range is one job. Everything
else is absorbed into the job it sits under.
"""

from app.pipeline.orchestrator import ParsePipeline

_TWO_LINE_HEADERS = (
    "Jane Q Doe\n"
    "Austin, TX | jane.doe@example.com\n"
    "EXPERIENCE\n"
    "IT Service Desk Manager Dec 2020 - Dec 2021\n"
    "U.S. Army, Captain - Fort Hood, TX\n"
    "• Provided IT support across multiple locations and set service standards.\n"
    "• Managed rollout of new cloud environments without interrupting operations.\n"
    "Founder Nov 2018 - Present\n"
    "Mind Marquee - Alexandria, VA\n"
    "• Created an educational e-commerce brand for home and office wall art.\n"
    "Digital Content Specialist Sep 2015 - Sep 2017\n"
    "In Pursuit Of, LLC - Arlington, VA\n"
    "• Drove content creation at a full-service communications agency.\n"
).encode("utf-8")


def _parse(payload: bytes):
    return ParsePipeline().parse_bytes(payload, "resume.txt", "text/plain")


def test_company_line_under_a_role_header_does_not_start_a_second_entry():
    experience = _parse(_TWO_LINE_HEADERS).data.experience

    assert len(experience) == 3
    first = experience[0]
    assert first.job_title == "IT Service Desk Manager"
    assert first.company == "U.S. Army"
    assert first.location == "Fort Hood, TX"
    assert first.start_date == "2020-12"
    assert first.end_date == "2021-12"
    assert len(first.description) == 2


def test_a_role_whose_title_is_not_a_known_role_noun_still_opens_an_entry():
    # "Founder" matches no role-noun vocabulary and parses as neither a
    # "Title, Company" pair nor a location, so its dates used to be absorbed
    # by the entry above it and the job disappeared entirely.
    experience = _parse(_TWO_LINE_HEADERS).data.experience

    founder = [item for item in experience if item.job_title == "Founder"]
    assert len(founder) == 1
    assert founder[0].company == "Mind Marquee"
    assert founder[0].start_date == "2018-11"
    assert founder[0].is_current is True


def test_corporate_suffix_stays_with_the_company_name():
    experience = _parse(_TWO_LINE_HEADERS).data.experience

    last = experience[-1]
    assert last.company == "In Pursuit Of, LLC"
    assert last.location == "Arlington, VA"


_COLUMNAR = (
    "Pat Rivera\n"
    "Chicago, IL | pat.rivera@example.com\n"
    "WORK EXPERIENCE\n"
    "Computer Aid, Inc.\t\tChicago, IL\t\t10/26/2015 - 02/18/2016\n"
    "Business Analyst\n"
    "• Gathered requirements from underwriting stakeholders.\n"
    "Abbott Laboratories\t\tAbbott Park, IL\t\t04/12/1993 - 06/30/1997\n"
    "Data Modeler\n"
    "• Designed the reporting schema for clinical trial submissions.\n"
).encode("utf-8")


def test_tab_separated_columns_split_company_from_city():
    # Whitespace is collapsed before parsing, so the only boundary left in
    # "Computer Aid, Inc.  Chicago, IL" is a comma, and the city was landing
    # in the company field. The column gap has to be read off the raw line.
    experience = _parse(_COLUMNAR).data.experience

    assert len(experience) == 2
    assert experience[0].company == "Computer Aid, Inc."
    assert experience[0].location == "Chicago, IL"
    assert experience[1].company == "Abbott Laboratories"
    assert experience[1].location == "Abbott Park, IL"


def test_numeric_slash_date_ranges_are_parsed():
    experience = _parse(_COLUMNAR).data.experience

    assert experience[0].start_date == "2015-10"
    assert experience[0].end_date == "2016-02"
    assert experience[1].start_date == "1993-04"
    assert experience[1].end_date == "1997-06"


_PROMOTION_HISTORY = (
    "Alex Stone\n"
    "Oaks, PA | alex.stone@example.com\n"
    "PROFESSIONAL EXPERIENCE\n"
    "SEI - Oaks, Pennsylvania 1998 - 2013\n"
    "Open Architecture Product Manager 2006 - 2009\n"
    "• Launched the open architecture managed account platform.\n"
    "Fund Accounting Analyst 1998 - 2001\n"
    "• Reconciled daily fund positions across custodial feeds.\n"
    "Fiduciary Tax Accountant - Mellon Bank 1996 - 1997\n"
    "• Prepared fiduciary returns for personal trust accounts.\n"
).encode("utf-8")


def test_sub_roles_inherit_the_employer_whose_span_encloses_them():
    # A long tenure is written as one employer header followed by the roles
    # held there, each with dates but no company repeated.
    experience = _parse(_PROMOTION_HISTORY).data.experience

    by_title = {item.job_title: item for item in experience if item.job_title}
    assert by_title["Open Architecture Product Manager"].company == "SEI"
    assert by_title["Fund Accounting Analyst"].company == "SEI"
    # Outside the 1998-2013 span, so it keeps its own employer.
    assert by_title["Fiduciary Tax Accountant"].company == "Mellon Bank"


_PROSE_AFTER_HEADER = (
    "Sam Bell\n"
    "Seattle, WA | sam.bell@example.com\n"
    "EXPERIENCE\n"
    "Senior Software Engineer Jul 2014 - Dec 2016\n"
    "Description: The platform includes functionality associated with on-boarding "
    "sites, routing payment transactions, managing card tables, and collecting "
    "transactional report data for the enterprise environment.\n"
    "• Built the payment routing service.\n"
).encode("utf-8")


def test_a_paragraph_of_prose_is_not_taken_as_the_company_name():
    # Company detection matched substrings with no length limit, so
    # "includes" supplied the "inc" and whole paragraphs became company
    # names. It now needs a real word match on a header-shaped line.
    experience = _parse(_PROSE_AFTER_HEADER).data.experience

    assert len(experience) == 1
    company = experience[0].company or ""
    assert "on-boarding" not in company
    assert len(company) < 60
