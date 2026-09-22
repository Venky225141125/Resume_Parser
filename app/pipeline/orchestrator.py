from __future__ import annotations

import time
import uuid

from app.confidence.scorer import SourceConfidenceScorer
from app.core.versions import PARSER_VERSION, SCHEMA_VERSION
from app.enrichment import get_skill_extractor
from app.enrichment.base import SkillExtractor
from app.extraction.service import ExtractionService
from app.normalization.candidate import CandidateNormalizer
from app.parsers.awards import AwardsParser, PublicationsParser
from app.parsers.certifications import CertificationParser
from app.parsers.contact import ContactParser
from app.parsers.education import EducationParser
from app.parsers.experience import ExperienceParser
from app.parsers.languages import LanguageParser
from app.parsers.projects import ProjectParser
from app.parsers.skills import SkillsParser
from app.parsers.summary import SummaryParser
from app.schemas.candidate import CandidateDocument, CandidateInfo, ParseResponse
from app.schemas.document import Document
from app.sections.detector import TaxonomySectionDetector
from app.validation.candidate import CandidateValidator


class ParsePipeline:
    """Deterministic-first resume parse pipeline."""

    def __init__(
        self,
        extraction: ExtractionService | None = None,
        skill_extractor: SkillExtractor | None = None,
    ) -> None:
        self._extraction = extraction or ExtractionService()
        self._normalizer = CandidateNormalizer()
        self._validator = CandidateValidator()
        self._scorer = SourceConfidenceScorer()
        # None unless skill NER is switched on in configuration, which keeps
        # the default install free of transformers/torch.
        self._skill_extractor = skill_extractor or get_skill_extractor()

    def extract_document(
        self,
        data: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> Document:
        return self._extraction.extract(data, filename, content_type)

    def parse_bytes(
        self,
        data: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> ParseResponse:
        started = time.perf_counter()
        document = self.extract_document(data, filename, content_type)
        sections = TaxonomySectionDetector().detect(document)

        name, contact, location, links = ContactParser().parse(document, sections)
        summary = SummaryParser().parse(document, sections)
        experience = ExperienceParser().parse(document, sections)
        education = EducationParser().parse(document, sections)
        skills = SkillsParser(self._skill_extractor).parse(document, sections)
        certifications = CertificationParser().parse(document, sections)
        projects = ProjectParser().parse(document, sections)
        languages = LanguageParser().parse(document, sections)
        awards = AwardsParser().parse(document, sections)
        publications = PublicationsParser().parse(document, sections)

        candidate = CandidateDocument(
            candidate=CandidateInfo(
                name=name,
                contact=contact,
                location=location,
                links=links,
            ),
            summary=summary,
            skills=skills,
            experience=experience,
            education=education,
            certifications=certifications,
            projects=projects,
            languages=languages,
            awards=awards,
            publications=publications,
        )

        candidate = self._normalizer.normalize(candidate)
        candidate = self._validator.validate(candidate)
        confidence, needs_review = self._scorer.score(candidate)
        elapsed_ms = max(0, int(round((time.perf_counter() - started) * 1000)))
        return ParseResponse(
            document_id=uuid.uuid4().hex,
            parser_version=PARSER_VERSION,
            schema_version=SCHEMA_VERSION,
            processing_time_ms=elapsed_ms,
            llm_used=False,
            confidence=confidence,
            needs_review=needs_review,
            data=candidate,
        )

    def empty_result(self, document_id: str) -> ParseResponse:
        return ParseResponse(
            document_id=document_id,
            parser_version=PARSER_VERSION,
            schema_version=SCHEMA_VERSION,
            processing_time_ms=0,
            llm_used=False,
            confidence=None,
            needs_review=True,
            data=CandidateDocument(),
        )
