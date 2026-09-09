import re

from app.schemas.document import Block, Document
from app.sections.base import DetectedSection

_BULLET_STRIP_CHARS = " \t\n\r-–—|•●▪◦‣⁃·*#."
_WHITESPACE = re.compile(r"\s+")
_LABEL_PREFIX = re.compile(r"^[A-Za-z][A-Za-z0-9 /&'\-]{1,30}:\s+(?=\S)")


def clean_line(text: str) -> str:
    """Strip bullet glyphs/whitespace noise that extraction leaves on a line."""
    cleaned = _WHITESPACE.sub(" ", text)
    return cleaned.strip(_BULLET_STRIP_CHARS)


def split_label_prefix(text: str) -> tuple[str | None, str]:
    """Split a "Label: rest" line (e.g. "Languages: Java") into (label, rest).

    Returns (None, text) when there is no short leading label — avoids
    mangling ordinary sentences that merely contain a colon.
    """
    match = _LABEL_PREFIX.match(text)
    if not match:
        return None, text
    label = match.group(0)[:-1].strip()
    rest = text[match.end():].strip()
    return (label or None), rest


def _block_lines(block: Block) -> list[str]:
    """A layout Block can span several visual PDF lines for two different
    reasons that need opposite handling:

    - it clusters two distinct items (e.g. a job title and the company/
      location line right below it) — these must be split back out so
      parsers see one semantic line per item.
    - it is a single bullet/paragraph that merely *word-wraps* onto a second
      visual line — that continuation belongs to the same logical line and
      must stay joined, or its second half gets parsed as a bogus new item.

    A block already carries which case it is: `list_item`/`table_cell`
    blocks are one semantic unit no matter how many visual lines they wrap
    across, so only split blocks that aren't already known to be one unit.
    """
    if block.block_type in {"list_item", "table_cell"}:
        text = block.text.replace("\n", " ").strip()
        return [text] if text else []
    if block.lines:
        split = [line.text.strip() for line in block.lines if line.text.strip()]
        if split:
            return split
    text = block.text.strip()
    return [text] if text else []


def sections_named(sections: list[DetectedSection], *names: str) -> list[DetectedSection]:
    wanted = set(names)
    return [section for section in sections if section.canonical in wanted]


def section_lines(sections: list[DetectedSection], *names: str) -> list[str]:
    lines: list[str] = []
    for section in sections_named(sections, *names):
        for block in section.blocks:
            lines.extend(_block_lines(block))
    return lines


def combined_text(sections: list[DetectedSection], *names: str) -> str:
    return "\n".join(section_lines(sections, *names))


def preamble_lines(sections: list[DetectedSection], document: Document) -> list[str]:
    header = sections_named(sections, "header")
    if header:
        lines: list[str] = []
        for block in header[0].blocks:
            lines.extend(_block_lines(block))
        return lines
    lines = []
    for block in document.blocks:
        if block.block_type in {"header", "footer"}:
            continue
        lines.extend(_block_lines(block))
        if len(lines) >= 8:
            break
    return lines


def all_lines(document: Document) -> list[str]:
    lines: list[str] = []
    for block in document.blocks:
        lines.extend(_block_lines(block))
    return lines
