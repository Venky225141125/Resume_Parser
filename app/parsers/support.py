import re

from app.parsers.dates import parse_date_range
from app.schemas.document import Block, Document
from app.sections.base import DetectedSection
from app.taxonomy_data import load_section_taxonomy

_BULLET_STRIP_CHARS = " \t\n\r-–—|•●▪◦‣⁃·*#."
_WHITESPACE = re.compile(r"\s+")
_LABEL_PREFIX = re.compile(r"^[A-Za-z][A-Za-z0-9 /&'\-]{1,30}:\s+(?=\S)")
_NON_ALNUM = re.compile(r"[^a-z0-9\s]+")


def _normalize_heading(text: str) -> str:
    lowered = text.lower().strip()
    cleaned = _NON_ALNUM.sub(" ", lowered)
    return _WHITESPACE.sub(" ", cleaned).strip()


def _heading_alias_map() -> dict[str, str]:
    alias_map: dict[str, str] = {}
    for canonical, aliases in load_section_taxonomy().items():
        alias_map[_normalize_heading(canonical)] = canonical
        for alias in aliases:
            alias_map[_normalize_heading(alias)] = canonical
    return alias_map


def is_known_section_heading(text: str) -> bool:
    """Whole-line match against the section taxonomy (same aliases the
    section detector uses) — used to reject a line as a name/value candidate
    when it's really a heading like "Work Experience" or "Professional
    Summary" that a field parser fell through to."""
    normalized = _normalize_heading(text)
    if not normalized or len(normalized.split()) > 6:
        return False
    return normalized in _heading_alias_map()


def fallback_section_lines(document: Document, canonical: str) -> list[str]:
    """Collect lines under `canonical`'s heading when no DetectedSection
    exists for it. Stops at the next line that names ANY recognized
    section (via the same taxonomy the main detector uses) — not just a
    hardcoded few — so a creatively-worded heading after this section
    (e.g. "Personal Accomplishments", "References:") doesn't get silently
    absorbed into it.
    """
    alias_map = _heading_alias_map()
    collect = False
    lines: list[str] = []
    for line in all_lines(document):
        normalized = _normalize_heading(line)
        matched = alias_map.get(normalized) if normalized and len(normalized.split()) <= 6 else None
        if matched == canonical:
            collect = True
            continue
        if matched and matched != canonical:
            if collect:
                break
            continue
        if collect:
            lines.append(line)
    return _merge_wrapped_lines(lines)


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
    # group(0) ends with the colon plus its trailing space, so dropping one
    # character left the colon on the label ("Role:", "Languages:").
    label = match.group(0).rstrip().rstrip(":").strip()
    rest = text[match.end():].strip()
    return (label or None), rest


_NEW_LINE_GAP_PT = 1.0  # points; see _block_lines for what this threshold means


_WRAPPED_LINE_REACH = 0.85


def _reached_right_margin(previous_row: list, left_margin: float, right_margin: float) -> bool:
    width = right_margin - left_margin
    if width <= 0:
        return True
    reach = (max(item.bbox.x1 for item in previous_row) - left_margin) / width
    return reach >= _WRAPPED_LINE_REACH


def _starts_new_line_regardless_of_gap(previous_row: list, row_text: str) -> bool:
    if row_text.lstrip().startswith(("•", "●", "▪", "◦", "‣", "⁃")):
        return True
    return len(previous_row) > 1


def _looks_like_wrap_continuation(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped:
        return False
    first = stripped[0]
    if first in _BULLET_STRIP_CHARS:
        return False
    return first.islower()


def _row_groups(lines: list) -> list[list]:
    """Group a block's Lines into visual rows: entries whose y-ranges
    meaningfully overlap sit on the same row (e.g. a bullet glyph and its
    text, or a title and its right-aligned date), ordered left to right.

    Overlap is checked against the most recently added item in the row, not
    an accumulated min/max envelope of everything in it. A row's envelope
    only grows as items join — a single much-taller item (e.g. a large-font
    name sharing a row with a small-font address column) would otherwise
    stretch that envelope down far enough to falsely "overlap" the next
    visual row too, chain-merging rows that don't belong together.

    The overlap must also be *substantial*, not merely non-zero. In tightly
    typeset resumes consecutive stacked lines overlap by a fraction of a
    point (~1% of a line), which would chain a whole section into one row;
    genuinely side-by-side items (a title and its right-aligned date) share
    most of their height.
    """
    ordered = sorted(lines, key=lambda ln: (ln.bbox.y0, ln.bbox.x0))
    rows: list[list] = []
    for ln in ordered:
        if rows and _shares_row(rows[-1][-1], ln):
            rows[-1].append(ln)
            continue
        rows.append([ln])
    for row in rows:
        row.sort(key=lambda ln: ln.bbox.x0)
    return rows


_SAME_ROW_OVERLAP = 0.5


def _shares_row(previous, candidate) -> bool:
    overlap = min(previous.bbox.y1, candidate.bbox.y1) - max(previous.bbox.y0, candidate.bbox.y0)
    if overlap <= 0:
        return False
    shortest = min(previous.bbox.y1 - previous.bbox.y0, candidate.bbox.y1 - candidate.bbox.y0)
    if shortest <= 0:
        return False
    return overlap / shortest >= _SAME_ROW_OVERLAP


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

    That absolute point gap isn't reliable across every PDF renderer, though
    — one real resume's ordinary word-wrap gap measured ~1.8pt, comfortably
    over the threshold tuned against a different PDF's tighter spacing,
    which split a wrapped sentence into a bogus second entry. A gap that
    large is still recognizably a wrap, not a new line, when the row starts
    lowercase with no bullet marker — a genuine new bullet/title/label
    always starts with a capital letter or a bullet glyph, so that signal
    is checked as a fallback whenever the gap alone says "new line".

    The gap can also be *too small* to be informative: tightly typeset
    resumes stack lines with near-zero (even slightly negative) gaps, which
    would merge a whole section into one string. Two layout facts override
    a small gap: a row starting with a bullet glyph is always a new line,
    and a multi-column row (a title beside its right-aligned date) always
    ends one — a wrap continuation never carries a right-aligned date.

    Finally, text only wraps because the next word didn't fit, so the line
    it wrapped from necessarily runs close to the column's right margin. A
    line ending well short of it (a centred name above a contact bar, a
    short sidebar label) was a complete line, however tightly the next one
    is stacked beneath it.
    """
    if block.lines and all(line.bbox is not None for line in block.lines):
        rows = _row_groups(block.lines)
        right_margin = max(line.bbox.x1 for line in block.lines)
        left_margin = min(line.bbox.x0 for line in block.lines)
        groups: list[list[list]] = [[rows[0]]]
        for prev_row, row in zip(rows, rows[1:]):
            # min(), not max(): a much-taller item in prev_row (e.g. a
            # large-font name sharing a row with a small-font column) must
            # not stretch the row's bottom edge down far enough to make an
            # unrelated next row look like a same-line wrap continuation.
            prev_y1 = min(item.bbox.y1 for item in prev_row)
            row_y0 = min(item.bbox.y0 for item in row)
            row_text = " ".join(item.text.strip() for item in row if item.text.strip())
            if _starts_new_line_regardless_of_gap(prev_row, row_text):
                groups.append([row])
            elif _looks_like_wrap_continuation(row_text):
                groups[-1].append(row)
            elif row_y0 - prev_y1 > _NEW_LINE_GAP_PT:
                groups.append([row])
            elif not _reached_right_margin(prev_row, left_margin, right_margin):
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


# A line ending on any of these cannot be a finished line: the sentence is
# still open, so whatever follows is the rest of it rather than a new item.
_UNFINISHED_TAIL = re.compile(
    r"(?:[,;\-–—/&(]|→|➜|\b(?:and|or|with|of|to|in|for|by|from|using|across|on|at|the|a|an)\b)\s*$",
    re.I,
)


def _merge_wrapped_lines(lines: list[str]) -> list[str]:
    """Rejoin lines that are only word-wrap continuations of the line above.

    `_block_lines` already does this *within* a layout block, but PDF
    extraction frequently emits every visual line as its own block, and then
    nothing merges them: each bullet arrives split at the wrap point. The
    halves are not harmless — the orphaned tail of a wrapped bullet is short
    and header-shaped, so downstream parsers read fragments like "supply
    issues, garbage collection, and streetlight failures" as a project name
    or a job title.

    Three signals mark a continuation, and any one is enough:

    - the line starts lowercase;
    - the line above ends mid-sentence, on a trailing comma, conjunction or
      arrow — this catches wraps falling before a capitalized word, as in
      "…(Submitted -> In Review -> Assigned ->" / "Resolved) and full
      complaint history.";
    - the line above is a long, unfinished bullet AND this line closes its
      sentence. A wrap can land before an ordinary capitalized word
      ("…utilizing Java, and Selenium" / "WebDriver."), where neither of the
      first two signals fires.

    That third signal needs all of its conditions. "Bullet above did not end
    in a full stop" alone is far too weak — plenty of resumes simply omit the
    trailing period, and then the *next entry's header* gets swallowed into
    the bullet, collapsing two jobs (or two projects) into one. A real wrap
    only happens on a line that ran out of room, so the bullet must be long,
    and its continuation must finish the sentence the bullet left open.

    A line is never absorbed when it carries meaning of its own: a bullet, a
    labelled field ("Environment: …"), a section heading, or anything naming
    a date range.
    """
    merged: list[str] = []
    previous_was_bullet = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        is_bullet = stripped.startswith(("•", "●", "▪", "◦", "‣", "⁃", "*"))
        if merged and not is_bullet and not _stands_alone(stripped):
            previous = merged[-1]
            if (
                _looks_like_wrap_continuation(stripped)
                or _UNFINISHED_TAIL.search(previous)
                or (
                    previous_was_bullet
                    and not _TERMINAL_PUNCTUATION.search(previous)
                    and len(previous) >= _MIN_WRAPPED_LINE_CHARS
                    and _SENTENCE_CLOSE.search(stripped)
                )
            ):
                merged[-1] = f"{previous.rstrip()} {stripped}"
                continue
        merged.append(stripped)
        previous_was_bullet = is_bullet
    return merged


_TERMINAL_PUNCTUATION = re.compile(r"[.!?:][\"')\]]?\s*$")
# The candidate must *close* a sentence to count as a wrap tail. A colon does
# not: a line ending in one introduces what follows rather than finishing it.
_SENTENCE_CLOSE = re.compile(r"[.!?][\"')\]]?\s*$")
# Text only wraps when it runs out of room, so the line it wrapped from must
# be long. Resume bullets that wrap measure ~90-120 characters.
_MIN_WRAPPED_LINE_CHARS = 70


def _stands_alone(text: str) -> bool:
    """True for a line that carries its own meaning and so must never be
    absorbed into the one above: a labelled field, a section heading, or any
    line naming a date range.

    The date check is deliberately not limited to short lines. A full entry
    header carries its dates inline — "Junior Engineer Jun 2019 - Dec 2020"
    is seven words — and absorbing one into the bullet above it is exactly
    how two jobs collapse into one.
    """
    if _LABEL_PREFIX.match(text) or is_known_section_heading(text):
        return True
    return parse_date_range(text) is not None


# Only an explicitly *subordinate* project label. A bare "Project:" is left
# alone on purpose: in many resumes (Indian IT ones especially) it is the
# primary structure of the experience section — one block per client
# engagement — and pulling those out would delete the work history.
_EMBEDDED_PROJECT = re.compile(
    r"(?i)^(?:key|major|notable|highlighted|significant)\s+projects?\s*[:\-]\s*(?P<name>.+)$"
)
_PROJECT_METADATA = re.compile(
    r"(?i)^(?:role|stack|tech(?:nolog(?:y|ies))?\s*stack|tech(?:nolog(?:y|ies))?|tools|"
    r"duration|team\s*size|environment|client)\s*[:\-]"
)
_BULLET_LINE = re.compile(r"^\s*(?:[\-*•●▪◦‣⁃]|\d+[.)])\s+")


def embedded_project_name(text: str) -> str | None:
    """The name from a "Key Project: HRMS …" line written inside a role, or
    None. Such a block describes work carried out within the role above it
    and opens its own entry, inheriting that role's employer."""
    match = _EMBEDDED_PROJECT.match(text)
    return match.group("name").strip() if match else None


def is_project_metadata(text: str) -> bool:
    """True for the "Role: … | Stack: …" line under an embedded project
    header, which names fields rather than describing work."""
    return bool(_PROJECT_METADATA.match(text))


def sections_named(sections: list[DetectedSection], *names: str) -> list[DetectedSection]:
    wanted = set(names)
    return [section for section in sections if section.canonical in wanted]


def section_lines(sections: list[DetectedSection], *names: str) -> list[str]:
    lines: list[str] = []
    for section in sections_named(sections, *names):
        for block in section.blocks:
            lines.extend(_block_lines(block))
    return _merge_wrapped_lines(lines)


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
