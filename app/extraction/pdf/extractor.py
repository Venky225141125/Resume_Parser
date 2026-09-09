from __future__ import annotations

import re
from statistics import median

from app.core.exceptions import CorruptFileError, EncryptedDocumentError, ExtractionError
from app.extraction.base import DocumentExtractor
from app.extraction.sniff import FileKind
from app.schemas.document import BBox, Block, BlockType, Document, DocumentMetadata, Line, Page, Table, Word

_OCR_CHAR_THRESHOLD = 40
_LIST_PREFIX = re.compile(
    r"^(?:[\-\*\u2022\u00b7\u25cf\u25aa\u25e6\u2023\u2043]|\d+[.)])\s+"
)


class PdfExtractor(DocumentExtractor):
    def supports(self, file_type: str) -> bool:
        return file_type == FileKind.PDF.value or file_type == FileKind.PDF

    def extract(self, data: bytes, filename: str, content_type: str) -> Document:
        try:
            import fitz
        except ImportError as exc:
            raise ExtractionError("PyMuPDF is not installed.") from exc

        try:
            pdf = fitz.open(stream=data, filetype="pdf")
        except Exception as exc:
            raise CorruptFileError("PDF is corrupt or unreadable.") from exc

        try:
            if pdf.needs_pass:
                raise EncryptedDocumentError()
            return self._from_pdf(pdf, filename, content_type)
        except (EncryptedDocumentError, CorruptFileError, ExtractionError):
            raise
        except Exception as exc:
            raise ExtractionError("PDF extraction failed.") from exc
        finally:
            pdf.close()

    def _from_pdf(self, pdf: object, filename: str, content_type: str) -> Document:
        pages: list[Page] = []
        blocks: list[Block] = []
        lines: list[Line] = []
        words: list[Word] = []
        tables: list[Table] = []
        column_counts: list[int] = []

        page_count = int(pdf.page_count)  # type: ignore[attr-defined]
        for index in range(page_count):
            page = pdf.load_page(index)  # type: ignore[attr-defined]
            number = index + 1
            width = float(page.rect.width)
            height = float(page.rect.height)
            page_dict = page.get_text("dict")
            page_blocks, page_lines, sizes, block_font_sizes = _blocks_from_dict(
                page_dict, number
            )
            _tag_headings(page_blocks, sizes, block_font_sizes)
            col_count = _assign_columns(page_blocks, width)
            column_counts.append(col_count)
            pages.append(
                Page(
                    number=number,
                    width=width,
                    height=height,
                    text="\n".join(block.text for block in page_blocks if block.text),
                )
            )
            blocks.extend(page_blocks)
            lines.extend(page_lines)
            words.extend(_words_from_page(page, number))
            tables.extend(_tables_from_page(page, number))

        _mark_headers_footers(blocks, pages)
        char_count = sum(len(block.text) for block in blocks)
        needs_ocr = char_count < _OCR_CHAR_THRESHOLD
        column_count = max(column_counts) if column_counts else 1

        return Document(
            pages=pages,
            blocks=blocks,
            lines=lines,
            words=words,
            tables=tables,
            metadata=DocumentMetadata(
                filename=filename,
                content_type=content_type,
                file_type=FileKind.PDF.value,
                page_count=len(pages),
                char_count=char_count,
                ocr_used=False,
                needs_ocr=needs_ocr,
                extractor="pymupdf",
                column_count=column_count,
            ),
        )


def _rect_to_bbox(rect: list[float] | tuple[float, ...]) -> BBox:
    return BBox(x0=float(rect[0]), y0=float(rect[1]), x1=float(rect[2]), y1=float(rect[3]))


def _blocks_from_dict(
    page_dict: dict,
    page_number: int,
) -> tuple[list[Block], list[Line], list[float], list[float]]:
    blocks: list[Block] = []
    lines: list[Line] = []
    sizes: list[float] = []
    block_font_sizes: list[float] = []
    for raw_block in page_dict.get("blocks", []):
        if raw_block.get("type", 0) != 0:
            continue
        block_lines: list[Line] = []
        local_sizes: list[float] = []
        for raw_line in raw_block.get("lines", []):
            spans = raw_line.get("spans", [])
            text = "".join(str(span.get("text", "")) for span in spans).strip()
            for span in spans:
                size = span.get("size")
                if size:
                    value = float(size)
                    sizes.append(value)
                    local_sizes.append(value)
            if not text:
                continue
            line_bbox = _rect_to_bbox(raw_line["bbox"]) if "bbox" in raw_line else None
            line = Line(text=text, page=page_number, bbox=line_bbox, confidence=1.0)
            block_lines.append(line)
            lines.append(line)
        block_text = "\n".join(line.text for line in block_lines)
        if not block_text:
            continue
        bbox = _rect_to_bbox(raw_block["bbox"]) if "bbox" in raw_block else None
        block_type = _infer_block_type(block_text)
        blocks.append(
            Block(
                text=block_text,
                page=page_number,
                bbox=bbox,
                block_type=block_type,
                confidence=1.0,
                lines=block_lines,
            )
        )
        block_font_sizes.append(max(local_sizes) if local_sizes else 0.0)
    order = sorted(
        range(len(blocks)),
        key=lambda i: (
            blocks[i].page,
            blocks[i].bbox.y0 if blocks[i].bbox else 0,
            blocks[i].bbox.x0 if blocks[i].bbox else 0,
        ),
    )
    blocks = [blocks[i] for i in order]
    block_font_sizes = [block_font_sizes[i] for i in order]
    return blocks, lines, sizes, block_font_sizes


def _infer_block_type(text: str) -> BlockType:
    """Position alone must not decide header/footer — see _mark_headers_footers,
    which uses cross-page repetition instead. A block that merely starts near
    the top of a page (e.g. a section heading right after a page break) is not
    a running header."""
    first = text.split("\n", 1)[0]
    if _LIST_PREFIX.match(first):
        return "list_item"
    return "paragraph"


def _tag_headings(blocks: list[Block], sizes: list[float], block_font_sizes: list[float]) -> None:
    if not sizes or len(block_font_sizes) != len(blocks):
        return
    cutoff = median(sizes) * 1.2
    for block, font_size in zip(blocks, block_font_sizes, strict=True):
        if block.block_type in {"header", "footer", "list_item"}:
            continue
        span_text = block.text.strip()
        if "@" in span_text or len(span_text) > 80:
            continue
        if font_size >= cutoff:
            block.block_type = "heading"


def _assign_columns(blocks: list[Block], page_width: float) -> int:
    if page_width <= 0 or len(blocks) < 4:
        for block in blocks:
            block.column = 0
        return 1
    mid = page_width * 0.48
    left = [block for block in blocks if block.bbox and block.bbox.x0 < mid]
    right = [block for block in blocks if block.bbox and block.bbox.x0 >= mid]
    if len(left) >= 2 and len(right) >= 2:
        for block in left:
            block.column = 0
        for block in right:
            block.column = 1
        return 2
    for block in blocks:
        block.column = 0
    return 1


def _mark_headers_footers(blocks: list[Block], pages: list[Page]) -> None:
    if len(pages) < 2:
        return
    by_text: dict[str, list[Block]] = {}
    for block in blocks:
        if not block.bbox:
            continue
        page = next((item for item in pages if item.number == block.page), None)
        if not page or not page.height:
            continue
        zone_header = block.bbox.y1 < page.height * 0.12
        zone_footer = block.bbox.y0 > page.height * 0.88
        if not (zone_header or zone_footer):
            continue
        key = " ".join(block.text.lower().split())
        by_text.setdefault(key, []).append(block)
    for group in by_text.values():
        pages_seen = {item.page for item in group}
        if len(pages_seen) < 2:
            continue
        for block in group:
            page = next(item for item in pages if item.number == block.page)
            assert block.bbox and page.height
            if block.bbox.y1 < page.height * 0.12:
                block.block_type = "header"
            else:
                block.block_type = "footer"


def _words_from_page(page: object, page_number: int) -> list[Word]:
    extracted: list[Word] = []
    for item in page.get_text("words"):  # type: ignore[attr-defined]
        x0, y0, x1, y1, text, *_ = item
        if not str(text).strip():
            continue
        extracted.append(
            Word(
                text=str(text),
                page=page_number,
                bbox=BBox(x0=float(x0), y0=float(y0), x1=float(x1), y1=float(y1)),
                confidence=1.0,
            )
        )
    return extracted


def _tables_from_page(page: object, page_number: int) -> list[Table]:
    tables: list[Table] = []
    finder = getattr(page, "find_tables", None)
    if finder is None:
        return tables
    try:
        found = finder()
    except Exception:
        return tables
    raw_tables = getattr(found, "tables", found) or []
    for table in raw_tables:
        try:
            rows = table.extract()
            bbox_raw = getattr(table, "bbox", None)
        except Exception:
            continue
        cleaned = [["" if cell is None else str(cell).strip() for cell in row] for row in rows]
        bbox = _rect_to_bbox(bbox_raw) if bbox_raw is not None else None
        tables.append(Table(page=page_number, bbox=bbox, rows=cleaned, confidence=0.8))
    return tables
