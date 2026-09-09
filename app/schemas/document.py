"""Intermediate document representation. Extractors emit this, not candidate JSON."""

from typing import Literal

from pydantic import BaseModel, Field


BlockType = Literal[
    "paragraph",
    "heading",
    "list_item",
    "table_cell",
    "header",
    "footer",
    "unknown",
]


class BBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float

    def as_list(self) -> list[float]:
        return [self.x0, self.y0, self.x1, self.y1]


class Word(BaseModel):
    text: str
    page: int
    bbox: BBox | None = None
    confidence: float | None = None


class Line(BaseModel):
    text: str
    page: int
    bbox: BBox | None = None
    words: list[Word] = Field(default_factory=list)
    confidence: float | None = None


class Block(BaseModel):
    text: str
    page: int
    bbox: BBox | None = None
    block_type: BlockType = "unknown"
    column: int | None = None
    confidence: float | None = None
    lines: list[Line] = Field(default_factory=list)


class Table(BaseModel):
    page: int
    bbox: BBox | None = None
    rows: list[list[str]] = Field(default_factory=list)
    confidence: float | None = None


class Page(BaseModel):
    number: int
    width: float | None = None
    height: float | None = None
    text: str = ""


class DocumentMetadata(BaseModel):
    filename: str | None = None
    content_type: str | None = None
    file_type: str | None = None
    page_count: int = 0
    char_count: int = 0
    ocr_used: bool = False
    needs_ocr: bool = False
    encrypted: bool = False
    extension_mismatch: bool = False
    column_count: int | None = None
    extractor: str | None = None
    extra: dict[str, str] = Field(default_factory=dict)


class Document(BaseModel):
    pages: list[Page] = Field(default_factory=list)
    blocks: list[Block] = Field(default_factory=list)
    lines: list[Line] = Field(default_factory=list)
    words: list[Word] = Field(default_factory=list)
    tables: list[Table] = Field(default_factory=list)
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)

    def plain_text(self) -> str:
        if self.blocks:
            return "\n".join(block.text for block in self.blocks if block.text)
        return "\n".join(page.text for page in self.pages if page.text)
