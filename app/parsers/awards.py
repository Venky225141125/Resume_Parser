from app.parsers.base import FieldParser
from app.parsers.support import section_lines
from app.schemas.candidate import AwardItem, PublicationItem
from app.schemas.document import Document
from app.sections.base import DetectedSection


class AwardsParser(FieldParser):
    def parse(self, document: Document, sections: list[DetectedSection]) -> list[AwardItem]:
        return [
            AwardItem(name=line)
            for line in section_lines(sections, "awards")
            if line
        ]


class PublicationsParser(FieldParser):
    def parse(self, document: Document, sections: list[DetectedSection]) -> list[PublicationItem]:
        return [
            PublicationItem(title=line)
            for line in section_lines(sections, "publications")
            if line
        ]
