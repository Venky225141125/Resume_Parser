from collections import defaultdict

from app.layout.base import LayoutAnalyzer
from app.schemas.document import Block, Document


class CoordinateLayoutAnalyzer(LayoutAnalyzer):
    """Sort blocks into column-aware reading order (left column, then right)."""

    def analyze(self, document: Document) -> Document:
        by_page: dict[int, list[Block]] = defaultdict(list)
        for block in document.blocks:
            by_page[block.page].append(block)
        ordered: list[Block] = []
        for page_number in sorted(by_page):
            ordered.extend(_order_page(by_page[page_number]))
        document.blocks = ordered
        return document


def _order_page(blocks: list[Block]) -> list[Block]:
    columns = {block.column for block in blocks if block.column is not None}
    if 0 in columns and 1 in columns:
        left = _sort_blocks([block for block in blocks if block.column == 0])
        right = _sort_blocks([block for block in blocks if block.column == 1])
        rest = _sort_blocks([block for block in blocks if block.column not in {0, 1}])
        return left + right + rest
    return _sort_blocks(blocks)


def _sort_blocks(blocks: list[Block]) -> list[Block]:
    return sorted(
        blocks,
        key=lambda block: (
            block.bbox.y0 if block.bbox else 0.0,
            block.bbox.x0 if block.bbox else 0.0,
        ),
    )
