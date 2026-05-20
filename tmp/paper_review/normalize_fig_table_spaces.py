from __future__ import annotations

from pathlib import Path
import re

from docx import Document


DOCX = Path("余涛初稿改3.docx")
no_space_re = re.compile(r"([图表])(?=\d+\s*[-－]\s*\d+)")


def iter_paragraphs(container):
    for paragraph in getattr(container, "paragraphs", []):
        yield paragraph
    for table in getattr(container, "tables", []):
        for row in table.rows:
            for cell in row.cells:
                yield from iter_paragraphs(cell)


def normalize_paragraph(paragraph) -> int:
    count = 0
    for run in paragraph.runs:
        new_text, changed = no_space_re.subn(r"\1 ", run.text)
        if changed:
            run.text = new_text
            count += changed
    return count


def main() -> None:
    doc = Document(DOCX)
    changes = 0

    for paragraph in iter_paragraphs(doc):
        changes += normalize_paragraph(paragraph)

    for section in doc.sections:
        for part in (section.header, section.footer, section.first_page_header, section.first_page_footer):
            for paragraph in iter_paragraphs(part):
                changes += normalize_paragraph(paragraph)

    doc.save(DOCX)
    print(f"normalized_spaces={changes}")


if __name__ == "__main__":
    main()
