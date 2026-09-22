from io import BytesIO

from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph

from app.core.exceptions import CorruptFileError, ExtractionError
from app.extraction.base import DocumentExtractor
from app.extraction.sniff import FileKind
from app.schemas.document import Block, BlockType, Document, DocumentMetadata, Line, Page, Table


class DocxExtractor(DocumentExtractor):
    def supports(self, file_type: str) -> bool:
        return file_type == FileKind.DOCX.value or file_type == FileKind.DOCX

    def extract(self, data: bytes, filename: str, content_type: str) -> Document:
        try:
            docx = DocxDocument(BytesIO(data))
        except Exception as exc:
            raise CorruptFileError("DOCX is corrupt or unreadable.") from exc

        try:
            return self._from_docx(docx, filename, content_type)
        except (CorruptFileError, ExtractionError):
            raise
        except Exception as exc:
            raise ExtractionError("DOCX extraction failed.") from exc

    def _from_docx(self, docx: DocxDocument, filename: str, content_type: str) -> Document:
        blocks: list[Block] = []
        lines: list[Line] = []
        tables: list[Table] = []
        page = 1

        for child in docx.element.body:
            tag = child.tag
            if tag == qn("w:p"):
                paragraph = Paragraph(child, docx)
                text = paragraph.text.strip()
                if not text:
                    continue
                block_type = _paragraph_type(paragraph)
                if block_type == "list_item" and not text.startswith(("-", "*", "•", "●")):
                    # Word keeps the bullet in numbering properties rather than
                    # in the text, so a DOCX bullet arrives glyph-less while the
                    # same resume as a PDF carries a real "•". Normalize here so
                    # downstream parsers see one shape regardless of source
                    # format — otherwise every bullet reads as a new entry.
                    text = f"• {text}"
                line = Line(text=text, page=page, confidence=1.0)
                lines.append(line)
                blocks.append(
                    Block(
                        text=text,
                        page=page,
                        block_type=block_type,
                        column=0,
                        confidence=1.0,
                        lines=[line],
                    )
                )
            elif tag == qn("w:tbl"):
                table = DocxTable(child, docx)
                rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
                tables.append(Table(page=page, rows=rows, confidence=1.0))
                for row in rows:
                    for cell_text in row:
                        if not cell_text:
                            continue
                        line = Line(text=cell_text, page=page, confidence=1.0)
                        lines.append(line)
                        blocks.append(
                            Block(
                                text=cell_text,
                                page=page,
                                block_type="table_cell",
                                column=0,
                                confidence=1.0,
                                lines=[line],
                            )
                        )

        plain = "\n".join(block.text for block in blocks)
        return Document(
            pages=[Page(number=1, text=plain)],
            blocks=blocks,
            lines=lines,
            words=[],
            tables=tables,
            metadata=DocumentMetadata(
                filename=filename,
                content_type=content_type,
                file_type=FileKind.DOCX.value,
                page_count=1,
                char_count=len(plain),
                extractor="python-docx",
                column_count=1,
            ),
        )


def _paragraph_type(paragraph: Paragraph) -> BlockType:
    style_name = (paragraph.style.name or "") if paragraph.style is not None else ""
    lowered = style_name.lower()
    if "heading" in lowered or "title" in lowered:
        return "heading"
    if _is_list_paragraph(paragraph, lowered):
        return "list_item"
    text = paragraph.text.strip()
    if text.startswith(("-", "*", "•")):
        return "list_item"
    return "paragraph"


def _is_list_paragraph(paragraph: Paragraph, lowered_style: str) -> bool:
    """Word stores bullets as numbering properties (`w:numPr`), not as text —
    so a bulleted line usually carries no bullet glyph at all. Without this,
    every bullet in a DOCX arrives as an ordinary paragraph and the field
    parsers read each one as a new role/entry."""
    if "list" in lowered_style:
        return True
    pPr = paragraph._p.find(qn("w:pPr"))
    if pPr is None:
        return False
    return pPr.find(qn("w:numPr")) is not None
