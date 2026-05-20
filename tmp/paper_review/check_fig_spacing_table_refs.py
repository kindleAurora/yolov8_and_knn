from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re

from docx import Document


DOCX = Path("余涛初稿改3.docx")
OUT = Path("tmp/paper_review/fig_spacing_table_refs.txt")

fig_no_space_re = re.compile(r"图(?=\d+\s*[-－]\s*\d+)")
fig_any_re = re.compile(r"图\s*\d+\s*[-－]\s*\d+")
table_any_re = re.compile(r"表\s*\d+\s*[-－]\s*\d+")
caption_re = re.compile(r"^\s*(图|表)\s*([0-9]+)\s*[-－]\s*([0-9]+)\s*(.*)$")


def norm(match_text: str) -> str:
    m = re.match(r"\s*([图表])\s*([0-9]+)\s*[-－]\s*([0-9]+)", match_text)
    if not m:
        return match_text
    return f"{m.group(1)} {int(m.group(2))}-{int(m.group(3))}"


def sort_key(key: str) -> tuple[int, int, int]:
    kind = 0 if key.startswith("图") else 1
    nums = [int(x) for x in re.findall(r"\d+", key)]
    return (kind, nums[0], nums[1])


def main() -> None:
    doc = Document(DOCX)
    paragraphs = [(i, p.text.strip()) for i, p in enumerate(doc.paragraphs, 1) if p.text.strip()]

    lines: list[str] = [f"source: {DOCX}"]

    lines.append("\n== 图编号未加空格的位置 ==")
    found = False
    for idx, text in paragraphs:
        if fig_no_space_re.search(text):
            found = True
            lines.append(f"{idx}: {text}")
    if not found:
        lines.append("无")

    captions: dict[str, list[tuple[int, str]]] = defaultdict(list)
    refs: dict[str, list[tuple[int, str]]] = defaultdict(list)
    caption_lines: set[int] = set()

    for idx, text in paragraphs:
        cap = caption_re.match(text)
        if cap:
            key = norm(cap.group(0))
            captions[key].append((idx, text))
            caption_lines.add(idx)
        for m in table_any_re.finditer(text):
            key = norm(m.group(0))
            refs[key].append((idx, text))

    lines.append("\n== 表题注 ==")
    for key in sorted([k for k in captions if k.startswith("表")], key=sort_key):
        for idx, text in captions[key]:
            lines.append(f"{idx}: {text}")

    lines.append("\n== 正文表引用但无对应题注 ==")
    missing = False
    for key in sorted([k for k in refs if k.startswith("表")], key=sort_key):
        if key not in captions:
            missing = True
            lines.append(key)
            for idx, text in refs[key]:
                if idx not in caption_lines:
                    lines.append(f"  {idx}: {text}")
    if not missing:
        lines.append("无")

    lines.append("\n== 表题注存在但正文未引用 ==")
    unused = False
    for key in sorted([k for k in captions if k.startswith("表")], key=sort_key):
        non_caption_refs = [(idx, text) for idx, text in refs.get(key, []) if idx not in caption_lines]
        if not non_caption_refs:
            unused = True
            for idx, text in captions[key]:
                lines.append(f"{key} -> {idx}: {text}")
    if not unused:
        lines.append("无")

    lines.append("\n== 正文表引用清单 ==")
    for key in sorted([k for k in refs if k.startswith("表")], key=sort_key):
        for idx, text in refs[key]:
            if idx not in caption_lines:
                lines.append(f"{key} @ {idx}: {text}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
