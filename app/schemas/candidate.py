"""Versioned candidate output schema. Missing values are null or []."""

from pydantic import BaseModel, Field

from app.core.versions import PARSER_VERSION, SCHEMA_VERSION


class NameInfo(BaseModel):
    full: str | None = None
    first: str | None = None
    middle: str | None = None
    last: str | None = None
    confidence: float | None = None


class ContactInfo(BaseModel):
    email: str | None = None
    phone: str | None = None
    alternate_phone: str | None = None


class LocationInfo(BaseModel):
    raw: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    address: str | None = None


class LinkInfo(BaseModel):
    type: str
    url: str
    confidence: float | None = None


class CandidateInfo(BaseModel):
    name: NameInfo = Field(default_factory=NameInfo)
    contact: ContactInfo = Field(default_factory=ContactInfo)
    location: LocationInfo = Field(default_factory=LocationInfo)
    links: list[LinkInfo] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    company: str | None = None
    job_title: str | None = None
    employment_type: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False
    description: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    confidence: float | None = None


class EducationItem(BaseModel):
    institution: str | None = None
    degree: str | None = None
    degree_normalized: str | None = None
    field_of_study: str | None = None
    specialization: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    graduation_date: str | None = None
    grade: str | None = None
    gpa: str | None = None
    location: str | None = None
    confidence: float | None = None


class SkillItem(BaseModel):
    raw: str
    normalized: str | None = None
    category: str | None = None
    confidence: float | None = None
    source: str | None = None


class CertificationItem(BaseModel):
    name: str | None = None
    issuing_organization: str | None = None
    issue_date: str | None = None
    expiration_date: str | None = None
    credential_id: str | None = None
    credential_url: str | None = None
    confidence: float | None = None


class ProjectItem(BaseModel):
    name: str | None = None
    description: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    role: str | None = None
    url: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    confidence: float | None = None


class LanguageItem(BaseModel):
    language: str
    proficiency: str | None = None
    confidence: float | None = None


class AwardItem(BaseModel):
    name: str | None = None
    issuer: str | None = None
    date: str | None = None


class PublicationItem(BaseModel):
    title: str | None = None
    publisher: str | None = None
    date: str | None = None
    url: str | None = None


class CandidateDocument(BaseModel):
    schema_version: str = SCHEMA_VERSION
    candidate: CandidateInfo = Field(default_factory=CandidateInfo)
    summary: str | None = None
    skills: list[SkillItem] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    certifications: list[CertificationItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    awards: list[AwardItem] = Field(default_factory=list)
    publications: list[PublicationItem] = Field(default_factory=list)


class ParseResponse(BaseModel):
    status: str = "success"
    document_id: str
    parser_version: str = PARSER_VERSION
    schema_version: str = SCHEMA_VERSION
    processing_time_ms: int
    llm_used: bool = False
    confidence: float | None = None
    needs_review: bool = False
    data: CandidateDocument
