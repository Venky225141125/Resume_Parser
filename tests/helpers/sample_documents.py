"""Synthetic resume bytes for tests. No real candidate PII."""

from __future__ import annotations

from io import BytesIO

from docx import Document as DocxDocument


def simple_txt() -> bytes:
    return (
        "Jane Doe\n"
        "jane.doe@example.com\n"
        "+1 415 555 0100\n"
        "Experience\n"
        "Software Engineer, Acme Corp, Jan 2021 - Present\n"
        "Education\n"
        "B.Sc Computer Science, State University, 2019\n"
        "Skills\n"
        "Python, Django, AWS, PostgreSQL\n"
    ).encode("utf-8")


def simple_pdf(*, two_column: bool = False, pages: int = 1, header: str | None = None) -> bytes:
    import fitz

    doc = fitz.open()
    if two_column:
        page = doc.new_page(width=612, height=792)
        left = ["Skills", "Python", "Django", "AWS"]
        right = ["Experience", "Acme Corp", "Software Engineer", "2021-Present"]
        for index, text in enumerate(left):
            page.insert_text((48, 80 + index * 28), text, fontsize=11)
        for index, text in enumerate(right):
            page.insert_text((330, 80 + index * 28), text, fontsize=11)
    else:
        for page_index in range(pages):
            page = doc.new_page(width=612, height=792)
            if header:
                page.insert_text((72, 28), header, fontsize=9)
            page.insert_text((72, 80), "Jane Doe", fontsize=18)
            page.insert_text((72, 110), "jane.doe@example.com", fontsize=11)
            page.insert_text((72, 150), "Experience", fontsize=14)
            page.insert_text((72, 176), f"Software Engineer at Acme — page {page_index + 1}", fontsize=11)
            page.insert_text((72, 220), "Education", fontsize=14)
            page.insert_text((72, 246), "B.Sc Computer Science", fontsize=11)
    buffer = BytesIO()
    doc.save(buffer)
    doc.close()
    return buffer.getvalue()


def empty_text_pdf() -> bytes:
    import fitz

    doc = fitz.open()
    doc.new_page(width=612, height=792)
    buffer = BytesIO()
    doc.save(buffer)
    doc.close()
    return buffer.getvalue()


def encrypted_pdf(password: str = "secret") -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Locked resume")
    buffer = BytesIO()
    doc.save(
        buffer,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw=password,
        owner_pw=f"{password}-owner",
    )
    doc.close()
    return buffer.getvalue()


def simple_docx() -> bytes:
    document = DocxDocument()
    document.add_heading("Jane Doe", level=0)
    document.add_paragraph("jane.doe@example.com")
    document.add_heading("Experience", level=1)
    document.add_paragraph("Software Engineer at Acme Corp")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Skill"
    table.cell(0, 1).text = "Level"
    table.cell(1, 0).text = "Python"
    table.cell(1, 1).text = "Expert"
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def ole_doc_bytes() -> bytes:
    return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64
