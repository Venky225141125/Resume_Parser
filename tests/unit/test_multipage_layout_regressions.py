"""Regression tests for a real-world resume that exposed several layout bugs:
title/date row-clustering merging title+company, a missing role-transition
when a second job's title has no date on the same line, a bullet dropped
because its text happened to contain a role keyword, a PROJECTS heading lost
because it sat at the very top of page 2, project "Tech Stack:" lines being
misread as new projects, and a word-wrapped bullet's second visual line
being shredded into a bogus new title/company pair. See
tests/helpers/sample_documents.py for the synthetic (non-PII) fixture that
reproduces the layout.
"""

from app.pipeline.orchestrator import ParsePipeline
from tests.helpers.sample_documents import multi_role_multi_project_pdf


def _parse():
    return ParsePipeline().parse_bytes(multi_role_multi_project_pdf(), "resume.pdf", "application/pdf")


def test_experience_keeps_title_and_company_separate_when_date_shares_the_title_row():
    response = _parse()
    first = response.data.experience[0]
    assert first.job_title == "Associate Software Engineer"
    assert first.company == "Acme Scientific Pvt. Ltd."
    assert first.start_date == "2026-02"
    assert first.is_current is True


def test_experience_starts_a_new_role_for_a_standalone_title_line():
    response = _parse()
    assert len(response.data.experience) == 2
    second = response.data.experience[1]
    assert second.job_title == "Java Trainer"
    assert second.start_date == "2025-05"
    assert second.end_date == "2026-01"


def test_experience_bullet_is_not_dropped_when_it_contains_a_role_keyword():
    response = _parse()
    second = response.data.experience[1]
    assert any("Delivered structured training on Core Java" in item for item in second.description)


def test_wrapped_bullet_stays_one_description_item_not_a_bogus_new_role():
    response = _parse()
    assert len(response.data.experience) == 2
    first = response.data.experience[0]
    # The bullet wraps across two visual PDF lines ("...Spring MVC, and" /
    # "Spring Boot, following..."); the wrap boundary text proves it survived
    # as one joined description item instead of being split into a second,
    # bogus experience entry.
    assert any("Spring MVC, and Spring Boot" in item for item in first.description)


def test_projects_section_survives_starting_on_page_two():
    response = _parse()
    names = [item.name for item in response.data.projects]
    assert "Grievance Management System" in names
    assert "Employee Data Management System" in names


def test_project_tech_stack_line_is_not_treated_as_a_new_project():
    response = _parse()
    assert len(response.data.projects) == 2
    projects = {item.name: item for item in response.data.projects}
    grievance = projects["Grievance Management System"]
    assert "React" in grievance.technologies
    assert any(
        "Built a full-stack civic-issue reporting platform enabling villagers" in d
        for d in grievance.description
    )


def test_certification_bullet_marker_is_stripped_from_name():
    response = _parse()
    names = [item.name for item in response.data.certifications]
    assert "Full Stack Development" in names
