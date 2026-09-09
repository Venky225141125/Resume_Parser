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
    - several bullets are long enough to word-wrap across two visual PDF
      lines within one paragraph block (wrapped-bullet-shredded-into-a-
      bogus-title/company-pair bug)
    """
    import fitz

    doc = fitz.open()
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text((72, 60), "JANE DOE", fontsize=18, fontname="hebo")
    p1.insert_text((72, 84), "Java Full Stack Developer", fontsize=12)
    p1.insert_text((72, 104), "jane.doe@example.com | +1 415 555 0100", fontsize=10)
    p1.insert_text((72, 150), "WORK EXPERIENCE", fontsize=14, fontname="hebo")
    p1.insert_text((72, 176), "Associate Software Engineer", fontsize=11, fontname="hebo")
    p1.insert_text((430, 176), "Feb 2026 - Present", fontsize=10)
    p1.insert_text((72, 192), "Acme Scientific Pvt. Ltd. | Hyderabad, Telangana", fontsize=10)
    p1.insert_textbox(
        fitz.Rect(80, 212, 540, 244),
        "- Build and maintain scalable, production-grade web applications using core Java, "
        "Spring MVC, and Spring Boot, following OOP principles.",
        fontsize=10,
    )
    p1.insert_text((80, 250), "- Design and implement REST APIs.", fontsize=10)
    p1.insert_text((72, 282), "Java Trainer", fontsize=11, fontname="hebo")
    p1.insert_text((430, 282), "May 2025 - Jan 2026", fontsize=10)
    p1.insert_text((72, 298), "Freelance / Institute-based Training", fontsize=10)
    p1.insert_textbox(
        fitz.Rect(80, 318, 540, 350),
        "- Delivered structured training on Core Java, JDBC, OOP, and backend development "
        "with Spring Boot to 40+ students.",
        fontsize=10,
    )

    p2 = doc.new_page(width=612, height=792)
    p2.insert_text((72, 50), "PROJECTS", fontsize=14, fontname="hebo")
    p2.insert_text((72, 76), "Grievance Management System", fontsize=11, fontname="hebo")
    p2.insert_text((72, 92), "Tech Stack: Spring Boot, React.js, MySQL", fontsize=9)
    p2.insert_textbox(
        fitz.Rect(80, 112, 540, 144),
        "- Built a full-stack civic-issue reporting platform enabling villagers to report "
        "problems such as road damage and water supply issues.",
        fontsize=10,
    )
    p2.insert_text((72, 160), "Employee Data Management System", fontsize=11, fontname="hebo")
    p2.insert_text((72, 176), "Tech Stack: Java, Spring Boot, MySQL", fontsize=9)
    p2.insert_text((80, 196), "- Developed a backend system to manage employee records.", fontsize=10)
    p2.insert_text((72, 230), "CERTIFICATIONS", fontsize=14, fontname="hebo")
    p2.insert_text((80, 250), "Full Stack Development - Example Institute (2022)", fontsize=10)

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
