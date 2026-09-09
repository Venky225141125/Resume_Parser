from pathlib import Path
from app.pipeline.orchestrator import ParsePipeline


def main() -> None:
    resume_path = Path(r"C:\Users\19802\Documents\Purna_Chandra_Reddy.pdf")

    if not resume_path.exists():
        sample = (
            "Jane Doe\n"
            "jane.doe@example.com\n"
            "+1 415 555 0100\n"
            "Experience\n"
            "Software Engineer at Acme Corp, Jan 2021 - Present\n"
            "Education\n"
            "B.Sc Computer Science, State University, 2019\n"
            "Skills\n"
            "Python, Django, AWS, PostgreSQL\n"
        )
        resume_path.write_text(sample, encoding="utf-8")
        print(f"Created sample resume file: {resume_path}")

    data = resume_path.read_bytes()
    result = ParsePipeline().parse_bytes(data, resume_path.name, "text/plain")

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
