from __future__ import annotations

import re

from app.parsers.base import FieldParser
from app.parsers.dates import parse_date_range, parse_date_token
from app.parsers.support import section_lines
from app.schemas.candidate import CertificationItem
from app.schemas.document import Document
from app.sections.base import DetectedSection

_ORG = re.compile(r"\s+(?:[-–—]|by|from)\s+", re.I)


class CertificationParser(FieldParser):
    def parse(self, document: Document, sections: list[DetectedSection]) -> list[CertificationItem]:
        items: list[CertificationItem] = []
        for line in section_lines(sections, "certifications"):
            dates = parse_date_range(line)
            year = None
            if not dates:
                match = re.search(r"\b((?:19|20)\d{2})\b", line)
                year = parse_date_token(match.group(1)) if match else None
            name = line
            org = None
            pieces = _ORG.split(line, maxsplit=1)
            if len(pieces) == 2:
                name, org = pieces[0].strip(), pieces[1].strip()
            items.append(
                CertificationItem(
                    name=name.strip() or None,
                    issuing_organization=org,
                    issue_date=dates.start if dates else year,
                    expiration_date=dates.end if dates else None,
                    confidence=0.75,
                )
            )
        return items
