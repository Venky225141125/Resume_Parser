from app.pipeline.orchestrator import ParsePipeline
from tests.helpers.sample_documents import ats_plus_technical_skills_resume


def _parse():
    return ParsePipeline().parse_bytes(
        ats_plus_technical_skills_resume(),
        "resume.txt",
        "text/plain",
    )


def test_technical_skill_languages_are_not_spoken_languages():
    response = _parse()
    spoken = [item.language.lower() for item in response.data.languages]
    assert spoken == []
    assert not any("java" in item.language.lower() for item in response.data.languages)
    assert not any("participating" in item.language.lower() for item in response.data.languages)


def test_skills_are_harvested_from_technical_skills_and_whole_resume():
    response = _parse()
    names = {(item.normalized or item.raw).lower() for item in response.data.skills}
    for expected in ("java", "spring", "hibernate", "oracle", "mysql", "tomcat", "junit", "git"):
        assert expected in names
    assert "web servers" not in names
    assert "languages" not in names


def test_both_jobs_are_parsed_with_dates_and_bullets():
    response = _parse()
    by_company = {(item.company or "").split(",")[0].strip().lower(): item for item in response.data.experience}
    assert "northwind" in by_company
    assert "contoso" in by_company
    northwind = by_company["northwind"]
    assert northwind.job_title and "developer" in northwind.job_title.lower()
    assert northwind.start_date == "2019-09"
    assert northwind.is_current is True
    assert any("system design" in item.lower() for item in northwind.description)
    contoso = by_company["contoso"]
    assert contoso.start_date == "2011-10"
    assert contoso.end_date == "2015-10"
    assert any("hibernate" in item.lower() for item in contoso.description)


def test_education_is_deduped_and_not_swallowed_by_summary():
    response = _parse()
    assert len(response.data.education) == 2
    degrees = {item.degree_normalized for item in response.data.education}
    assert "M.Tech" in degrees or "Master's" in degrees
    assert "B.Tech" in degrees or "Bachelor's" in degrees
    assert not any(
        item.institution and "master in master" in item.institution.lower()
        for item in response.data.education
    )
