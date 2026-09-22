"""Regression tests from a real resume whose candidate block parsed wrong in
three separate ways:

1. The centred name sat only 0.024pt above the contact bar beneath it — far
   below the wrap-gap threshold — so `_block_lines` merged them, yielding
   name="Nick Xavier Smith Austin" and location="Nick Xavier Smith Austin,
   TX". Gap alone cannot separate lines this tightly stacked; a line that
   ends well short of the column's right margin never word-wrapped.
2. Consecutive lines in that document overlap vertically by ~0.1pt, and
   `_row_groups` treated *any* overlap as "same row", chaining a whole job
   (title, company, every bullet, the date) into one row.
3. The single US phone number was reported twice — once as +1... (US
   region) and again as +91... (IN region) in `alternate_phone`.

Geometry below is taken from the real PDF; identity is placeholder.
"""

from app.parsers.contact import _extract_phones
from app.parsers.support import _block_lines, _row_groups
from app.schemas.document import BBox, Block, Line

_NAME_BBOX = BBox(x0=301.73, y0=36.000, x1=405.07, y1=50.064)
_CONTACT_BBOX = BBox(x0=231.77, y0=50.088, x1=474.62, y1=62.464)


def _header_block() -> Block:
    name_text = "Jane Q Doe"
    contact_text = "Austin, TX | 631-806-6076 | jane.doe@example.com"
    return Block(
        text=f"{name_text}\n{contact_text}",
        page=1,
        bbox=BBox(x0=231.77, y0=36.0, x1=474.62, y1=62.464),
        block_type="paragraph",
        confidence=1.0,
        lines=[
            Line(text=name_text, page=1, bbox=_NAME_BBOX, confidence=1.0),
            Line(text=contact_text, page=1, bbox=_CONTACT_BBOX, confidence=1.0),
        ],
    )


def test_centred_name_is_not_merged_into_the_contact_bar_below_it():
    # Confirms the fixture reproduces the real geometry: the gap is far too
    # small for the gap rule alone to separate these lines.
    assert _CONTACT_BBOX.y0 - _NAME_BBOX.y1 < 1.0
    lines = _block_lines(_header_block())
    assert lines == ["Jane Q Doe", "Austin, TX | 631-806-6076 | jane.doe@example.com"]


def test_slightly_overlapping_stacked_lines_are_not_one_row():
    title = Line(text="IT Service Desk Manager", page=1, bbox=BBox(x0=128.06, y0=101.108, x1=251.61, y1=113.484))
    date = Line(text="Dec 2020 - Dec 2021", page=1, bbox=BBox(x0=476.02, y0=101.108, x1=578.42, y1=113.484))
    company = Line(text="Example Corp, Austin, TX", page=1, bbox=BBox(x0=128.06, y0=113.348, x1=281.25, y1=125.724))

    rows = _row_groups([title, date, company])

    # title + right-aligned date share ~100% of their height -> one row;
    # the company line below overlaps by only ~1% -> its own row.
    assert len(rows) == 2
    assert [item.text for item in rows[0]] == ["IT Service Desk Manager", "Dec 2020 - Dec 2021"]
    assert [item.text for item in rows[1]] == ["Example Corp, Austin, TX"]


def test_one_phone_number_is_not_reported_twice_under_two_regions():
    phones = _extract_phones("Austin, TX | 631-806-6076 | jane.doe@example.com")
    assert phones == ["+16318066076"]
