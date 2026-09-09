from app.schemas.document import Document
from app.sections.base import DetectedSection


def sections_named(sections: list[DetectedSection], *names: str) -> list[DetectedSection]:
    wanted = set(names)
    return [section for section in sections if section.canonical in wanted]


def section_lines(sections: list[DetectedSection], *names: str) -> list[str]:
    lines: list[str] = []
    for section in sections_named(sections, *names):
        for block in section.blocks:
            text = block.text.strip()
            if text:
                lines.append(text)
    return lines


def combined_text(sections: list[DetectedSection], *names: str) -> str:
    return "\n".join(section_lines(sections, *names))


def preamble_lines(sections: list[DetectedSection], document: Document) -> list[str]:
    header = sections_named(sections, "header")
    if header:
        return [block.text.strip() for block in header[0].blocks if block.text.strip()]
    lines: list[str] = []
    for block in document.blocks:
        if block.block_type in {"header", "footer"}:
            continue
        text = block.text.strip()
        if text:
            lines.append(text)
        if len(lines) >= 8:
            break
    return lines


def all_lines(document: Document) -> list[str]:
    return [block.text.strip() for block in document.blocks if block.text.strip()]
