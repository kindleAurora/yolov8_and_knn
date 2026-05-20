from __future__ import annotations

import re
from pathlib import Path

from docx import Document


TEXT = Path("tmp/paper_review/docx_paragraphs.txt").read_text(encoding="utf-8")
LINES = TEXT.splitlines()
DOC = Document("余涛初稿改3.docx")
RAW_PARAGRAPHS = [p.text.strip() for p in DOC.paragraphs if p.text.strip()]
RAW_TEXT = "\n".join(RAW_PARAGRAPHS)


def expand_citation(token: str) -> list[int]:
    nums: list[int] = []
    for part in re.split(r"\s*,\s*", token):
        if "-" in part:
            start, end = part.split("-", 1)
            if start.isdigit() and end.isdigit():
                nums.extend(range(int(start), int(end) + 1))
        elif part.isdigit():
            nums.append(int(part))
    return nums


def citations() -> None:
    used: list[int] = []
    for match in re.finditer(r"\[([0-9,\-\s]+)\]", RAW_TEXT):
        used.extend(expand_citation(match.group(1)))

    refs = []
    in_refs = False
    for para in RAW_PARAGRAPHS:
        if para == "参考文献":
            in_refs = True
            continue
        if para.replace(" ", "") == "致谢":
            in_refs = False
        if in_refs:
            match = re.match(r"\[(\d+)\]", para)
            if match:
                refs.append(int(match.group(1)))

    print("citations_used", sorted(set(used)))
    print("references", refs)
    print("missing_reference_for_used", sorted(set(used) - set(refs)))
    print("unused_references", sorted(set(refs) - set(used)))


def figures_tables() -> None:
    fig_captions = []
    table_captions = []
    fig_refs = []
    table_refs = []
    for line in LINES:
        text = re.sub(r"^\[\d+\]\s+\([^)]+\)\s*", "", line)
        if re.match(r"图\s*\d+-\d+", text):
            fig_captions.append(text)
        if re.match(r"表\s*\d+-\d+", text):
            table_captions.append(text)
        fig_refs.extend(re.findall(r"图\s*\d+-\d+", text))
        table_refs.extend(re.findall(r"表\s*\d+-\d+", text))

    print("\nfigure_captions")
    for item in fig_captions:
        print(item)
    print("\ntable_captions")
    for item in table_captions:
        print(item)
    print("\nfigure_refs_unique", sorted(set(fig_refs), key=lambda s: [int(x) for x in re.findall(r"\d+", s)]))
    print("table_refs_unique", sorted(set(table_refs), key=lambda s: [int(x) for x in re.findall(r"\d+", s)]))


def suspicious_lines() -> None:
    rules = [
        ("missing_sentence_period", r"[\u4e00-\u9fffA-Za-z0-9]$"),
        ("figure_number_mismatch_hint", r"如图\s*4-6|如图\s*4-7"),
        ("missing_space_after_section_number", r"^\[\d+\].*\)\s+\d+\.\d+[\u4e00-\u9fffA-Za-z]"),
        ("quote_style", r"‘|’|“|”"),
    ]
    for name, regex in rules:
        print(f"\n{name}")
        for line in LINES:
            if re.search(regex, line):
                print(line)


if __name__ == "__main__":
    citations()
    figures_tables()
    suspicious_lines()
