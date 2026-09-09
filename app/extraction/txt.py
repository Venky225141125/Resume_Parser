from app.core.exceptions import ExtractionError
from app.extraction.base import DocumentExtractor
from app.extraction.sniff import FileKind
from app.schemas.document import Block, Document, DocumentMetadata, Line, Page, Word


class TxtExtractor(DocumentExtractor):
    def supports(self, file_type: str) -> bool:
        return file_type == FileKind.TXT.value or file_type == FileKind.TXT

    def extract(self, data: bytes, filename: str, content_type: str) -> Document:
        text = _decode_text(data)
        lines_raw = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        blocks: list[Block] = []
        lines: list[Line] = []
        words: list[Word] = []
        for raw in lines_raw:
            stripped = raw.strip()
            if not stripped:
                continue
            line = Line(text=stripped, page=1, confidence=1.0)
            lines.append(line)
            blocks.append(
                Block(
                    text=stripped,
                    page=1,
                    block_type="paragraph",
                    column=0,
                    confidence=1.0,
                    lines=[line],
                )
            )
            for token in stripped.split():
                words.append(Word(text=token, page=1, confidence=1.0))

        plain = "\n".join(block.text for block in blocks)
        return Document(
            pages=[Page(number=1, text=plain)],
            blocks=blocks,
            lines=lines,
            words=words,
            tables=[],
            metadata=DocumentMetadata(
                filename=filename,
                content_type=content_type,
                file_type=FileKind.TXT.value,
                page_count=1,
                char_count=len(plain),
                extractor="txt",
                column_count=1,
            ),
        )


def _decode_text(data: bytes) -> str:
    if data.startswith(b"\xff\xfe"):
        return data.decode("utf-16-le")
    if data.startswith(b"\xfe\xff"):
        return data.decode("utf-16-be")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise ExtractionError("Text encoding is not supported.") from exc
