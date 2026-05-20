from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import re

from docx import Document


DOCX = Path("余涛初稿改3.docx")
OUT = Path("tmp/paper_review/fig_table_report.txt")


def normalize(kind: str, chapter: str, number: str) -> str:
    return f"{kind}{int(chapter)}-{int(number)}"


def display(kind: str, key: str) -> str:
    return key.replace(kind, f"{kind} ")


caption_re = re.compile(r"^\s*(图|表)\s*([0-9]+)\s*[-－]\s*([0-9]+)\s*(.*)$")
ref_re = re.compile(r"(图|表)\s*([0-9]+)\s*[-－]\s*([0-9]+)")


def main() -> None:
    doc = Document(DOCX)
    paragraphs = [(idx, p.text.strip()) for idx, p in enumerate(doc.paragraphs, 1) if p.text.strip()]

    captions: dict[str, list[tuple[int, str]]] = defaultdict(list)
    refs: dict[str, list[tuple[int, str]]] = defaultdict(list)
    inline_refs: dict[str, list[tuple[int, str]]] = defaultdict(list)
    all_ref_forms: dict[str, set[str]] = defaultdict(set)
    all_caption_forms: dict[str, set[str]] = defaultdict(set)

    for idx, text in paragraphs:
        cap = caption_re.match(text)
        if cap:
            kind, chapter, number, _title = cap.groups()
            key = normalize(kind, chapter, number)
            captions[key].append((idx, text))
            all_caption_forms[key].add(cap.group(0).split()[0] if " " in cap.group(0) else cap.group(0)[: len(kind + chapter + "-" + number)])

        for match in ref_re.finditer(text):
            kind, chapter, number = match.groups()
            key = normalize(kind, chapter, number)
            refs[key].append((idx, text))
            all_ref_forms[key].add(match.group(0))
            if not cap:
                inline_refs[key].append((idx, text))

    lines: list[str] = []
    lines.append(f"source: {DOCX}")

    for kind in ("图", "表"):
        kind_caps = {k: v for k, v in captions.items() if k.startswith(kind)}
        lines.append(f"\n== {kind}题注 ==")
        for key in sorted(kind_caps, key=lambda x: [int(n) for n in re.findall(r"\d+", x)]):
            for idx, text in kind_caps[key]:
                lines.append(f"{idx}: {text}")

        lines.append(f"\n== {kind}重复题注 ==")
        duplicates = [(k, v) for k, v in kind_caps.items() if len(v) > 1]
        if not duplicates:
            lines.append("无")
        for key, items in duplicates:
            lines.append(f"{display(kind, key)} 重复 {len(items)} 次")
            for idx, text in items:
                lines.append(f"  {idx}: {text}")

        lines.append(f"\n== {kind}正文引用但无对应题注 ==")
        missing = sorted(
            [k for k, v in inline_refs.items() if k.startswith(kind) and k not in kind_caps],
            key=lambda x: [int(n) for n in re.findall(r"\d+", x)],
        )
        if not missing:
            lines.append("无")
        for key in missing:
            lines.append(display(kind, key))
            for idx, text in inline_refs[key]:
                lines.append(f"  {idx}: {text}")

        lines.append(f"\n== {kind}有题注但正文未引用 ==")
        not_referenced = sorted(
            [k for k in kind_caps if not inline_refs.get(k)],
            key=lambda x: [int(n) for n in re.findall(r"\d+", x)],
        )
        if not not_referenced:
            lines.append("无")
        for key in not_referenced:
            for idx, text in kind_caps[key]:
                lines.append(f"{idx}: {text}")

        lines.append(f"\n== {kind}编号格式混用 ==")
        mixed = []
        for key in sorted(set(all_ref_forms) | set(all_caption_forms), key=lambda x: [int(n) for n in re.findall(r"\d+", x)]):
            if not key.startswith(kind):
                continue
            forms = set()
            forms.update(all_ref_forms.get(key, set()))
            forms.update(all_caption_forms.get(key, set()))
            normalized_forms = {re.sub(r"\s+", "", f).replace("－", "-") for f in forms}
            if len(forms) > 1 and len(normalized_forms) == 1:
                mixed.append((key, forms))
        if not mixed:
            lines.append("无")
        for key, forms in mixed:
            lines.append(f"{display(kind, key)}: {', '.join(sorted(forms))}")

        lines.append(f"\n== {kind}章节序列检查 ==")
        by_chapter: dict[int, list[int]] = defaultdict(list)
        for key in kind_caps:
            nums = [int(n) for n in re.findall(r"\d+", key)]
            by_chapter[nums[0]].append(nums[1])
        for chapter, nums in sorted(by_chapter.items()):
            counts = Counter(nums)
            max_num = max(nums)
            missing_nums = [n for n in range(1, max_num + 1) if n not in counts]
            dup_nums = [n for n, count in counts.items() if count > 1]
            lines.append(
                f"{kind}{chapter}: captions={len(nums)}, max={max_num}, "
                f"missing={missing_nums or '无'}, duplicate={dup_nums or '无'}"
            )

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
