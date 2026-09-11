"""Synthetic resume bytes for tests. No real candidate PII."""

from __future__ import annotations

from io import BytesIO

from docx import Document as DocxDocument

from app.extraction.pdf.native import import_fitz


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
    fitz = import_fitz()

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
    fitz = import_fitz()

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


def creative_headings_pdf() -> bytes:
    """Reproduces a real-world resume that broke both section detection and
    the education parser at once (placeholder data, no PII):

    - section headings phrased creatively rather than with an exact taxonomy
      word ("VCU Practical Experience:", "Personal Accomplishments", "Key
      Skills and Software", "Continuous Education, Licenses and
      Certificates", "References:") — an exact-alias-only heading matcher
      never recognizes these, so everything from "Education" onward
      (experience, awards, references — everything) gets absorbed into one
      giant "education" section.
    - ordinary bullet prose containing the bare two-letter substring "me"
      (as in "resulting in", "employment", or the pronoun "me" itself) —
      the degree regex for M.E./B.E. must not fire on every such line, or
      dozens of bogus "M.E." education entries get manufactured from
      unrelated experience/award/reference content.
    """
    fitz = import_fitz()

    doc = fitz.open()
    p = doc.new_page(width=612, height=792)
    p.insert_text((72, 60), "JANE DOE", fontsize=18, fontname="hebo")
    p.insert_text((72, 100), "Education", fontsize=14, fontname="hebo")
    p.insert_text((72, 130), "STATE UNIVERSITY", fontsize=11, fontname="hebo")
    p.insert_text((72, 150), "Bachelor of Arts, Cinema, December 2020", fontsize=10)
    p.insert_text((72, 190), "Continuous Education, Licenses and Certificates", fontsize=14, fontname="hebo")
    p.insert_text((72, 220), "Completed 55 E-learning courses, over 60 hours", fontsize=10)
    p.insert_text((72, 260), "Key Skills and Software", fontsize=14, fontname="hebo")
    p.insert_text((72, 300), "VCU Practical Experience:", fontsize=14, fontname="hebo")
    p.insert_text((72, 330), "AR/VR/XR Project Manager, Acme Experiences, JUL 2020 - Present", fontsize=11, fontname="hebo")
    p.insert_text((80, 350), "- Guided new customers through sales funnel to retain customers.", fontsize=10)
    p.insert_text((80, 370), "- Estimated budgets for labor, software, advertising, to apply for grant funding.", fontsize=10)
    p.insert_text((72, 410), "Personal Accomplishments", fontsize=14, fontname="hebo")
    p.insert_text((80, 440), "- Pioneered a VR experience, awarded funding to develop the project.", fontsize=10)
    p.insert_text((72, 480), "References:", fontsize=14, fontname="hebo")
    p.insert_text((72, 510), "Jordan Smith", fontsize=10)
    p.insert_text((80, 530), "Chair of Communication Arts and Program Director.", fontsize=10)
    buffer = BytesIO()
    doc.save(buffer)
    doc.close()
    return buffer.getvalue()


def empty_text_pdf() -> bytes:
    fitz = import_fitz()

    doc = fitz.open()
    doc.new_page(width=612, height=792)
    buffer = BytesIO() 
    doc.save(buffer)
    doc.close()
    return buffer.getvalue()


def encrypted_pdf(password: str = "secret") -> bytes:
    fitz = import_fitz()

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


def ats_plus_technical_skills_resume() -> bytes:
    """ATS wrapper page + detailed resume: a 'Languages' skill category
    must not steal experience/education, and skills must be harvested from
    the whole document. Placeholder identity, no real PII.
    """
    return (
        "JANE DOE\n"
        "Java Developer, jane.doe@example.com\n"
        "Location\n"
        "Tampa, Florida (33601) United States\n"
        "Work History\n"
        "Java Developer, Northwind (Sep 2019)\n"
        "Java Developer, Contoso (Oct 2011 - Oct 2015)\n"
        "Skills\n"
        "• analysis • methodologies • agile software development\n"
        "Education\n"
        "master in master of technology in communication systems engineering engineering state university (2011)\n"
        "Master's Degree in Master of Technology in Communication Systems State University (2011)\n"
        "jane.doe@example.com Java Developer +1 415 555 0100 Professional Summary:\n"
        "● Total 6 years of IT experience in analysis, design and implementation.\n"
        "Technical Skills:\n"
        "Languages\n"
        "CoreJava, Java, J2EE, SQL, PL/SQL, HTML, CSS, JavaScript, Spring, Hibernate\n"
        "Web Servers\n"
        "Tomcat, Web Logic, Web Sphere\n"
        "Tools\n"
        "GIT, Git Hub, SVN, Ant, Maven, Log4j, JUnit\n"
        "Databases\n"
        "Oracle, SQL, MySQL\n"
        "Professional Experience: Northwind, Boston MA Sep 2019 to Present Java Developer\n"
        "● Participating in system design, planning, estimation and implementation.\n"
        "● Developing application components using Spring, Spring-Data, Spring Boot and Oracle.\n"
        "Environment: Java 8, Spring, JUnit, Git, HTML5, CSS3 Contoso, India Oct 2011 to Oct2015\n"
        "Java Developer\n"
        "● Worked with JSPs and Servlets on the front end.\n"
        "● Used Hibernate ORM to integrate with Oracle Database.\n"
        "Environment: Core Java, JDBC, Oracle, PL/SQL, Tomcat, JUnit, Spring Education\n"
        "● Master of Technology in Communication Systems from State University -2011\n"
        "● Bachelor of Technology in E.C.E from JNTU - 2009\n"
    ).encode("utf-8")


def ole_doc_bytes() -> bytes:
    return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64
