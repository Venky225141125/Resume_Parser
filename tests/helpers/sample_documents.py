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


def multi_role_multi_project_pdf() -> bytes:
    """Reproduces a real-world layout bug pattern (with placeholder data, no PII):

    - a job title and its right-aligned date share one visual row, which PDF
      extraction clusters into a single multi-line block (title/company merge bug)
    - a second role follows on its own title line with no shared date row
      (missing-role-transition bug)
    - a bullet's text happens to contain a word ("Java") that is also a
      role-line keyword (bullet-misread-as-role-line bug)
    - the PROJECTS heading is the very first thing on page 2 (page-top
      mistaken for a running header bug)
    - each project is followed by a "Tech Stack:" metadata line before its
      bullets (project-metadata-treated-as-new-project bug)
    - bullets word-wrap across two visual PDF lines *within the same PDF
      block as the following role's header* — the exact real-world layout
      that produces a block mixing a wrapped bullet continuation with a new
      title/date/company (wrapped-bullet-and-next-role-crammed-into-one-
      block bug). Line placement below is deliberately baseline-precise
      (not `insert_textbox`) to reproduce the real PDF's spacing: a wrapped
      continuation sits ~0.4pt below the previous line, while a genuinely
      new line sits >=1.4pt below — see `_block_lines` in
      app/parsers/support.py, which relies on exactly that distinction.
    """
    import fitz

    line_height = 13.74  # measured PyMuPDF line bbox height at fontsize=10 (helv)
    wrap_gap = 0.4
    item_gap = 2.0

    def next_baseline(baseline: float, gap: float) -> float:
        return baseline + line_height + gap

    doc = fitz.open()
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text((72, 60), "JANE DOE", fontsize=18, fontname="hebo")
    p1.insert_text((72, 84), "Java Full Stack Developer", fontsize=12)
    p1.insert_text((72, 104), "jane.doe@example.com | +1 415 555 0100", fontsize=10)
    p1.insert_text((72, 150), "WORK EXPERIENCE", fontsize=14, fontname="hebo")

    y = 176.0
    p1.insert_text((72, y), "Associate Software Engineer", fontsize=11, fontname="hebo")
    p1.insert_text((430, y), "Feb 2026 - Present", fontsize=10)
    y = next_baseline(y, item_gap)
    p1.insert_text((72, y), "Acme Scientific Pvt. Ltd. | Hyderabad, Telangana", fontsize=10)
    y = next_baseline(y, item_gap)
    p1.insert_text((72, y), "- Build and maintain scalable, production-grade web applications", fontsize=10)
    y = next_baseline(y, wrap_gap)
    p1.insert_text((72, y), "using core Java, Spring MVC, and Spring Boot, following OOP principles.", fontsize=10)
    y = next_baseline(y, item_gap)
    p1.insert_text((72, y), "- Design and implement REST APIs.", fontsize=10)
    # The next role's title/date/company crammed into the same PDF block as
    # the previous bullet's wrap — reproduces the real document exactly.
    # The gap here is still smaller than the normal inter-item gap (as it
    # was in the real PDF, ~3.5pt vs ~1.4pt) but must clear the threshold.
    y = next_baseline(y, item_gap * 1.5)
    p1.insert_text((72, y), "Java Trainer", fontsize=11, fontname="hebo")
    p1.insert_text((430, y), "May 2025 - Jan 2026", fontsize=10)
    y = next_baseline(y, item_gap)
    p1.insert_text((72, y), "Freelance / Institute-based Training", fontsize=10)
    y = next_baseline(y, item_gap)
    p1.insert_text((72, y), "- Delivered structured training on Core Java, JDBC, OOP, and backend", fontsize=10)
    y = next_baseline(y, wrap_gap)
    p1.insert_text((72, y), "development with Spring Boot to 40+ students.", fontsize=10)

    p2 = doc.new_page(width=612, height=792)
    p2.insert_text((72, 50), "PROJECTS", fontsize=14, fontname="hebo")
    y = 76.0
    p2.insert_text((72, y), "Grievance Management System", fontsize=11, fontname="hebo")
    y = next_baseline(y, item_gap)
    p2.insert_text((72, y), "Tech Stack: Spring Boot, React.js, MySQL", fontsize=9)
    y = next_baseline(y, item_gap)
    p2.insert_text((72, y), "- Built a full-stack civic-issue reporting platform enabling villagers to", fontsize=10)
    y = next_baseline(y, wrap_gap)
    p2.insert_text((72, y), "report problems such as road damage and water supply issues.", fontsize=10)
    y = next_baseline(y, 20)
    p2.insert_text((72, y), "Employee Data Management System", fontsize=11, fontname="hebo")
    y = next_baseline(y, item_gap)
    p2.insert_text((72, y), "Tech Stack: Java, Spring Boot, MySQL", fontsize=9)
    y = next_baseline(y, item_gap)
    p2.insert_text((72, y), "- Developed a backend system to manage employee records.", fontsize=10)
    y = next_baseline(y, 20)
    p2.insert_text((72, y), "CERTIFICATIONS", fontsize=14, fontname="hebo")
    y = next_baseline(y, item_gap)
    p2.insert_text((72, y), "Full Stack Development - Example Institute (2022)", fontsize=10)

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
