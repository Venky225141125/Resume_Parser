"""Regression tests from a batch check against ~40 real (anonymized-pattern)
resumes, run to find contact-extraction gaps the earlier combined-header fix
didn't cover. Each case below reproduces a distinct real layout bug found in
that batch, with placeholder identity — see git history for the session that
found them.
"""

from app.pipeline.orchestrator import ParsePipeline

LABEL_GLUED_HEADER = (
    "JANE DOE Location: Anavaram, Vizianagaram, Andhra Pradesh - INDIA\n"
    "Portfolio | LinkedIn | GitHub Email: jane.doe@example.com | Mobile: 8341947811\n"
    "EXPERIENCE\n"
    "Software Engineer - I Apr 2025 - present\n"
    "Example Corp\n"
    "Developed RESTful APIs using Java and Spring Boot.\n"
)

STREET_ADDRESS_THEN_CITY_STATE_ZIP = (
    "JORDAN B. SMITH\n"
    "123 Example Ln W, apt C 203\n"
    "Boca Raton, FL 33433\n"
    "508-309-5366 (Cell)\n"
    "WORK EXPERIENCE\n"
    "Example Co, Example City, NY - Manager 2010 - 2011\n"
    "Operated business development.\n"
)

EXPERIENCE_LOCATION_NOT_PERSONAL_LOCATION = (
    "TAYLOR MORGAN\n"
    "Tableau / BI Report Developer\n"
    "Phone - (405) 796-6683| email - taylor.morgan@example.com\n"
    "Legal Status: US Citizen\n"
    "PROFESSIONAL SUMMARY\n"
    "Experienced Project Manager with nine years of experience.\n"
    "WORK HISTORY\n"
    "Example Corp, Plano, TX Sept 2019-September 2021\n"
    "Led multiple teams aligned to scaled agile practices.\n"
)

CREDENTIALED_NAME_SUFFIX = (
    "Taylor Serrano, MS.,RMHCI, IMH20981\n"
    "Counselor, MS., RMHCI\n"
    "Example City, FL 32707\n"
    "taylor.serrano@example.com\n"
    "+1 407 473 1475\n"
    "Work Experience\n"
    "Clinical Therapist\n"
    "Example Recovery Ctr - Example City, FL\n"
    "August 2020 to Present\n"
    "Intake, assessment, biopsychosocial, family session.\n"
    "Education\n"
    "Master Degree in Psychology\n"
    "Example University - Example City, FL\n"
)

COMPOUND_AMPERSAND_HEADING = (
    "Taylor Reed 920-540-1259 - taylor.reed@example.com\n"
    "EDUCATION & HONORS\n"
    "Example University Example City, IL\n"
    "Masters in Health Informatics Anticipated December 2022\n"
    "EXPERIENCE\n"
    "Example Health, Example City, IL\n"
    "Patient Engagement Associate August 2021 - Present\n"
    "Manipulate, analyze and structure clinic metrics data.\n"
)


def _parse(text: str):
    return ParsePipeline().parse_bytes(text.encode("utf-8"), "resume.txt", "text/plain")


def test_name_and_location_survive_a_label_glued_two_column_header():
    response = _parse(LABEL_GLUED_HEADER)
    candidate = response.data.candidate
    assert candidate.name.full == "JANE DOE"
    assert candidate.contact.email == "jane.doe@example.com"
    assert candidate.location.city == "Anavaram"
    assert candidate.location.state == "Andhra Pradesh"
    assert candidate.location.country == "India"


def test_city_state_zip_line_is_preferred_over_a_bare_street_address():
    response = _parse(STREET_ADDRESS_THEN_CITY_STATE_ZIP)
    location = response.data.candidate.location
    assert location.city == "Boca Raton"
    assert location.state == "FL"
    assert location.postal_code == "33433"


def test_an_experience_entrys_location_is_not_mistaken_for_personal_location():
    response = _parse(EXPERIENCE_LOCATION_NOT_PERSONAL_LOCATION)
    location = response.data.candidate.location
    assert location.raw is None
    assert location.city is None


def test_name_with_post_nominal_credentials_is_still_extracted():
    response = _parse(CREDENTIALED_NAME_SUFFIX)
    candidate = response.data.candidate
    assert candidate.name.full == "Taylor Serrano"
    assert candidate.location.city == "Example City"
    assert candidate.location.state == "FL"
    assert candidate.location.postal_code == "32707"


def test_ampersand_compound_heading_is_recognized_as_a_section_boundary():
    response = _parse(COMPOUND_AMPERSAND_HEADING)
    assert response.data.education
    assert response.data.experience
    assert any(item.company == "Example Health" for item in response.data.experience)
    assert not any(
        "clinic metrics" in (item.field_of_study or "") for item in response.data.education
    )
