"""Regression tests for word-wrapped bullets and projects nested inside a
role.

`_block_lines` rejoins wrapped lines within one layout block, but PDF
extraction often emits every visual line as its own block, and then nothing
rejoined them: each bullet arrived split at its wrap point. The orphaned tail
is short and header-shaped, so it did not merely look untidy - downstream
parsers read fragments like "supply issues, garbage collection, and
streetlight failures" as project names in their own right.

The second fixture covers a "Key Project:" block written inside a job. It
names a role and a stack but never an employer, so it opens an entry that
inherits the one whose role contains it.
"""

from app.parsers.support import embedded_project_name, split_label_prefix
from app.pipeline.orchestrator import ParsePipeline

_WRAPPED = (
    "Dana Cole\n"
    "Guntur, AP | dana.cole@example.com\n"
    "WORK EXPERIENCE\n"
    "Associate Software Engineer Feb 2024 - Present\n"
    "Prominent Scientific Pvt. Ltd. | Hyderabad, Telangana\n"
    "● Build and maintain scalable, production-grade web applications using core Java, Spring MVC,\n"
    "following OOP principles and clean coding standards.\n"
    "● Design and implement RESTful services and Java Servlet modules that integrate with MySQL,\n"
    "writing optimized SQL queries for data retrieval and reporting.\n"
    "PROJECTS\n"
    "Smart Village Grievance Management System\n"
    "Tech Stack: Spring Boot, React.js, MySQL\n"
    "● Designed complaint workflows with real-time status tracking (Submitted → Assigned →\n"
    "Resolved) and full complaint history.\n"
    "● Built a civic-issue reporting platform enabling villagers to report problems such as road\n"
    "damage, water supply issues, and streetlight failures.\n"
).encode("utf-8")


def _parse(payload: bytes):
    return ParsePipeline().parse_bytes(payload, "resume.txt", "text/plain")


def test_wrapped_bullet_halves_are_rejoined_into_one_description_item():
    experience = _parse(_WRAPPED).data.experience

    assert len(experience) == 1
    description = experience[0].description
    assert len(description) == 2
    assert description[0].endswith("clean coding standards")
    assert "Spring MVC, following OOP" in description[0]
    # No item may start mid-sentence: that is the signature of an orphan tail.
    assert not any(item[:1].islower() for item in description)


def test_a_wrap_tail_is_not_promoted_to_a_project_of_its_own():
    projects = _parse(_WRAPPED).data.projects

    assert [project.name for project in projects] == [
        "Smart Village Grievance Management System"
    ]
    assert len(projects[0].description) == 2


def test_a_wrap_before_a_capitalized_word_is_still_rejoined():
    # "(Submitted -> Assigned ->" / "Resolved) and full complaint history."
    # starts with a capital, so the lowercase rule alone misses it; the line
    # above ends mid-sentence on an arrow.
    projects = _parse(_WRAPPED).data.projects

    tracking = [item for item in projects[0].description if "status tracking" in item]
    assert len(tracking) == 1
    assert tracking[0].endswith("Resolved) and full complaint history")


_KEY_PROJECT = (
    "Dana Cole\n"
    "Guntur, AP | dana.cole@example.com\n"
    "WORK EXPERIENCE\n"
    "Associate Software Engineer Feb 2024 - Present\n"
    "Prominent Scientific Pvt. Ltd. | Hyderabad, Telangana\n"
    "● Build and maintain scalable web applications using core Java and Spring Boot.\n"
    "Key Project: HRMS (Human Resource Management System)\n"
    "Role: Full Stack Developer (Front End + Back End) | Stack: Spring Boot, React.js, MySQL\n"
    "● Built backend services with Spring Boot and MySQL to manage leave requests and payroll.\n"
    "● Built responsive React.js interfaces for employees and HR staff.\n"
    "Java Trainer May 2023 - Jan 2024\n"
    "Freelance / Institute-based Training\n"
    "● Delivered structured training on Core Java and Spring Boot to 40+ students.\n"
).encode("utf-8")


def test_every_entry_is_named_by_its_own_heading():
    experience = _parse(_KEY_PROJECT).data.experience

    assert [item.job_title for item in experience] == [
        "Associate Software Engineer",
        "HRMS (Human Resource Management System)",
        "Java Trainer",
    ]
    # The project's bullets belong to it, not to the job above it.
    assert len(experience[0].description) == 1


def test_a_key_project_entry_does_not_borrow_the_neighbouring_employer():
    # The block states a role and a stack but no employer. Inheriting one
    # from the role above put the previous entry's company on this one.
    hrms = _parse(_KEY_PROJECT).data.experience[1]

    assert hrms.company is None
    assert hrms.location is None
    # No dates are claimed for it either, so none are reported.
    assert hrms.start_date is None
    assert hrms.end_date is None


def test_the_role_and_stack_line_is_kept_as_sub_text_and_mined_for_the_stack():
    hrms = _parse(_KEY_PROJECT).data.experience[1]

    assert hrms.technologies == ["Spring Boot", "React.js", "MySQL"]
    # Kept verbatim as the block's sub-text, the counterpart of the
    # "Company | Location" line under an ordinary role header.
    assert hrms.description[0].startswith("Role: Full Stack Developer")
    assert len(hrms.description) == 3


def test_a_bare_project_label_does_not_open_an_entry():
    # Many resumes structure the whole experience section as one "Project:"
    # block per client engagement; treating those as nested projects would
    # rewrite the work history.
    assert embedded_project_name("Project: Payments Platform") is None
    assert embedded_project_name("Key Project: Payments Platform") == "Payments Platform"


def test_label_prefix_does_not_keep_the_colon():
    assert split_label_prefix("Role: Full Stack Developer") == (
        "Role",
        "Full Stack Developer",
    )
