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


_NEW_LINE_GAP_PT = 1.0  # points; see _block_lines for what this threshold means


def _row_groups(lines: list) -> list[list]:
    """Group a block's Lines into visual rows: entries whose y-ranges
    meaningfully overlap sit on the same row (e.g. a bullet glyph and its
    text, or a title and its right-aligned date), ordered left to right.
    """
    ordered = sorted(lines, key=lambda ln: (ln.bbox.y0, ln.bbox.x0))
    rows: list[list] = []
    for ln in ordered:
        if rows:
            row = rows[-1]
            row_y0 = min(item.bbox.y0 for item in row)
            row_y1 = max(item.bbox.y1 for item in row)
            if ln.bbox.y0 < row_y1 and ln.bbox.y1 > row_y0:
                row.append(ln)
                continue
        rows.append([ln])
    for row in rows:
        row.sort(key=lambda ln: ln.bbox.x0)
    return rows


def _block_lines(block: Block) -> list[str]:
    """A layout Block can span several visual PDF lines for two different
    reasons that need opposite handling:

    - it clusters distinct items (e.g. a job title and the company/location
      line right below it, or a bullet that happens to butt up against the
      next role's title with no section heading between them) — these must
      be split back out so parsers see one semantic line per item.
    - it is a single bullet/paragraph that merely *word-wraps* onto a second
      visual line — that continuation belongs to the same logical line and
      must stay joined, or its second half gets parsed as a bogus new item.

    Both cases can occur *within the same block* (a wrapped bullet whose
    block PDF extraction happened to cluster with the next role's header),
    so this can't be decided once for the whole block — it's decided per
    gap, using the vertical distance between consecutive visual rows.
    Measured on real resume PDFs, a wrapped continuation sits ~0.3-0.5pt
    below the previous row (essentially touching), while any genuinely new
    line — a new bullet, a new title, a label line — sits >=1.3pt below.
    """
    if block.lines and all(line.bbox is not None for line in block.lines):
        rows = _row_groups(block.lines)
        groups: list[list[list]] = [[rows[0]]]
        for prev_row, row in zip(rows, rows[1:]):
            prev_y1 = max(item.bbox.y1 for item in prev_row)
            row_y0 = min(item.bbox.y0 for item in row)
            if row_y0 - prev_y1 > _NEW_LINE_GAP_PT:
                groups.append([row])
            else:
                groups[-1].append(row)
        texts: list[str] = []
        for group in groups:
            combined = " ".join(
                " ".join(item.text.strip() for item in row if item.text.strip())
                for row in group
            ).strip()
            if combined:
                texts.append(combined)
        if texts:
            return texts
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
