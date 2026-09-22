"""The optional layer-3 skill enricher.

The transformer itself is not exercised here — `transformers` and `torch` are
not base dependencies, so there is no model to run. What *is* tested is
everything around the model, which is where the behaviour that matters lives:
the enricher only ever adds, it never overrides a deterministic result, its
output is canonicalized through the same taxonomy as every other source, and
a missing or broken model degrades to the deterministic parse rather than
failing the request.

`_to_spans` is tested directly against the shapes a Hugging Face
token-classification pipeline returns, so the one piece that cannot be run
here is still pinned to a contract.
"""

from app.enrichment.base import ExtractedSpan
from app.enrichment.ner_skills import TransformerSkillExtractor, _to_spans
from app.parsers.skills import SkillsParser
from app.pipeline.orchestrator import ParsePipeline
from app.sections.detector import TaxonomySectionDetector
from app.extraction.service import ExtractionService

_RESUME = (
    "Dana Reed\n"
    "Orlando, FL | dana.reed@example.com\n"
    "SKILLS\n"
    "Java, MySQL\n"
    "EXPERIENCE\n"
    "Support Lead  Jan 2020 - Present\n"
    "Acme Corp - Orlando, FL\n"
    "• Took escalation calls and handled biopsychosocial assessment intake.\n"
).encode("utf-8")


class _StubExtractor:
    """Stands in for the transformer, returning fixed spans."""

    def __init__(self, spans: list[ExtractedSpan]) -> None:
        self._spans = spans
        self.calls = 0

    @property
    def name(self) -> str:
        return "ner"

    def available(self) -> bool:
        return True

    def extract(self, text: str) -> list[ExtractedSpan]:
        self.calls += 1
        return list(self._spans)


def _parse(extractor=None):
    document = ExtractionService().extract(_RESUME, "resume.txt", "text/plain")
    sections = TaxonomySectionDetector().detect(document)
    return SkillsParser(extractor).parse(document, sections)


def _names(items) -> list[str]:
    return [(item.normalized or item.raw).lower() for item in items]


def test_without_an_extractor_the_parse_is_unchanged():
    assert _parse(None) == _parse(None)
    assert "java" in _names(_parse(None))


def test_the_enricher_adds_phrases_no_gazetteer_could_hold():
    baseline = set(_names(_parse(None)))
    extractor = _StubExtractor(
        [
            ExtractedSpan(text="white glove support", score=0.91),
            ExtractedSpan(text="shift handover", score=0.84),
        ]
    )

    enriched = _parse(extractor)

    assert extractor.calls == 1
    added = set(_names(enriched)) - baseline
    assert "white glove support" in added
    # Everything found deterministically survives.
    assert baseline <= set(_names(enriched))


def test_an_added_span_is_labelled_with_its_source_and_model_score():
    extractor = _StubExtractor([ExtractedSpan(text="white glove support", score=0.91)])

    item = next(i for i in _parse(extractor) if i.raw == "white glove support")

    assert item.source == "ner"
    assert item.confidence == 0.91


def test_a_span_that_is_a_known_skill_is_canonicalized_not_duplicated():
    # The model returning "Spring Boot" must not create a second entry
    # alongside the taxonomy's "Spring".
    extractor = _StubExtractor(
        [ExtractedSpan(text="Spring Boot", score=0.95), ExtractedSpan(text="java", score=0.99)]
    )

    items = _parse(extractor)
    names = _names(items)

    assert names.count("java") == 1
    spring = [i for i in items if (i.normalized or "").lower() == "spring"]
    assert len(spring) == 1
    assert spring[0].source == "taxonomy"


def test_a_whole_clause_returned_by_the_model_is_rejected():
    extractor = _StubExtractor(
        [ExtractedSpan(text="took escalation calls from members with concerns", score=0.99)]
    )

    assert "took escalation calls from members with concerns" not in _names(_parse(extractor))


def test_a_missing_model_degrades_to_the_deterministic_parse():
    # transformers is not a base dependency, so this is the real default.
    extractor = TransformerSkillExtractor("jjzha/jobbert_skill_extraction")

    assert extractor.available() is False
    assert extractor.extract("Built services with Spring Boot") == []
    assert _names(_parse(extractor)) == _names(_parse(None))


def test_enrichment_is_off_unless_configured():
    # The shipped default must not reach for a model at all.
    assert ParsePipeline()._skill_extractor is None


def test_pipeline_output_is_identical_with_enrichment_off():
    response = ParsePipeline().parse_bytes(_RESUME, "resume.txt", "text/plain")

    assert [s.source for s in response.data.skills]
    assert all(s.source in {"taxonomy", "rule"} for s in response.data.skills)


def test_pipeline_surfaces_enriched_skills_when_an_extractor_is_injected():
    extractor = _StubExtractor([ExtractedSpan(text="white glove support", score=0.88)])

    response = ParsePipeline(skill_extractor=extractor).parse_bytes(
        _RESUME, "resume.txt", "text/plain"
    )

    assert "white glove support" in {(s.normalized or s.raw).lower() for s in response.data.skills}


def test_pipeline_output_shapes_are_mapped_to_spans():
    # aggregation_strategy="simple" yields entity_group/word/score.
    raw = [
        {"entity_group": "SKILL", "word": "white glove support", "score": 0.91},
        {"entity_group": "KNOWLEDGE", "word": "Spring Boot", "score": 0.88},
        {"entity_group": "LABEL_0", "word": "the", "score": 0.99},
        {"entity_group": "SKILL", "word": "low confidence", "score": 0.2},
        {"entity_group": "SKILL", "word": "white glove support", "score": 0.7},
    ]

    spans = _to_spans(raw, min_score=0.6)

    assert [s.text for s in spans] == ["white glove support", "Spring Boot"]


def test_span_mapping_tolerates_missing_and_malformed_entries():
    raw = [None, {}, {"word": "  ", "score": 0.9}, {"word": "Kubernetes", "score": 0.95}]

    spans = _to_spans(raw, min_score=0.6)

    assert [s.text for s in spans] == ["Kubernetes"]
    assert _to_spans(None, min_score=0.6) == []
