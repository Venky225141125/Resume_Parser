"""Skills are gathered from the whole resume, not just its Skills section.

Most resumes name far more of their skills in the work history than in a
Skills block, and many have no Skills block at all. The taxonomy sweep runs
over the entire document for that reason.

Matching correctness has two sharp edges worth pinning:

- \\b is the wrong boundary for skill names. "C++" and "C#" end on a
  non-word character, so \\b after them never matches and those skills could
  never be found at all.
- the canonical name is normally searchable too, but a few skills are named
  by a word that is far more often ordinary prose. "Go" and "R" are found
  only via unambiguous spellings, or every "go to" and middle initial in the
  corpus becomes a programming language.
"""

from app.normalization.skills import SkillNormalizer
from app.pipeline.orchestrator import ParsePipeline

_NO_SKILLS_SECTION = (
    "Wes Clement\n"
    "Milton, FL | wes.clement@example.com\n"
    "Experience\n"
    "Front Line Call Center Agent  2018 - Present\n"
    "Alorica - Pensacola, FL\n"
    "• Provided members with white glove technical support on their devices.\n"
    "• Took escalation calls from members with concerns outside the agent's scope.\n"
    "• Assisted team managers in overseeing the production floor.\n"
).encode("utf-8")


def _skills(payload: bytes) -> set[str]:
    response = ParsePipeline().parse_bytes(payload, "resume.txt", "text/plain")
    return {(item.normalized or item.raw).lower() for item in response.data.skills}


def test_skills_are_found_in_a_resume_with_no_skills_section():
    found = _skills(_NO_SKILLS_SECTION)

    assert "call center" in found
    assert "technical support" in found
    assert found, "a resume with no Skills block must still yield skills"


def test_skills_named_only_in_the_experience_section_are_reported():
    payload = (
        "Ada Byron\n"
        "Austin, TX | ada@example.com\n"
        "SKILLS\n"
        "Java\n"
        "EXPERIENCE\n"
        "Senior Engineer  Jan 2020 - Present\n"
        "Acme Corp - Austin, TX\n"
        "• Built services with Spring Boot and deployed them on Kubernetes.\n"
        "• Automated the pipeline with Jenkins and Terraform.\n"
    ).encode("utf-8")

    found = _skills(payload)

    assert {"java", "spring", "kubernetes", "jenkins", "terraform"} <= found


def test_skill_names_ending_in_punctuation_are_matchable():
    normalizer = SkillNormalizer()

    found = normalizer.find_aliases("Worked in C++, C# and .NET Core on CI/CD and PL/SQL.")

    assert {"c++", "c#", ".net core", "ci/cd", "pl/sql"} <= set(found)


def test_the_longest_skill_name_wins_at_a_given_position():
    normalizer = SkillNormalizer()

    found = normalizer.find_aliases("Migrated to SQL Server and Spring Boot last year.")

    assert "sql server" in found
    assert "spring boot" in found
    # The shorter names must not also be reported from the same words.
    assert "sql" not in found
    assert "spring" not in found


def test_ambiguous_one_letter_skill_names_do_not_match_bare_prose():
    normalizer = SkillNormalizer()

    found = set(normalizer.find_aliases("Asked to go to the R and D meeting with C level staff"))

    assert "go" not in found
    assert "r" not in found
    # They are still found when written unambiguously.
    assert "golang" in set(normalizer.find_aliases("Wrote services in Golang"))


def test_a_us_state_code_is_not_read_as_a_skill():
    # "Guntur, AP" made "AP" an alias hit and reported Accounts Payable.
    found = _skills(
        (
            "Priya Rao\n"
            "Guntur, AP | priya.rao@example.com\n"
            "SKILLS\n"
            "Java, MySQL\n"
        ).encode("utf-8")
    )

    assert "accounts payable" not in found
    assert "accounts receivable" not in found
