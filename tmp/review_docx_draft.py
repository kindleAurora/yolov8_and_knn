from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from collections import Counter, defaultdict
import re


DOCX = Path("余涛初稿改3.docx")
OUT = Path("tmp/doc_review/余涛初稿改3_初稿检查.txt")

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}


def text_of(node):
    return "".join(t.text or "" for t in node.findall(".//w:t", NS))


def compact(text):
    return re.sub(r"\s+", "", text)


def read_parts():
    parts = []
    with ZipFile(DOCX) as zf:
        names = ["word/document.xml"] + sorted(
            n
            for n in zf.namelist()
            if n.startswith("word/header") or n.startswith("word/footer")
        )
        for name in names:
            root = ET.fromstring(zf.read(name))
            for p in root.findall(".//w:p", NS):
                text = text_of(p).strip()
                if not text:
                    continue
                style = ""
                pstyle = p.find("./w:pPr/w:pStyle", NS)
                if pstyle is not None:
                    style = pstyle.attrib.get(f"{{{NS['w']}}}val", "")
                parts.append({"source": name, "style": style, "text": text})
    return parts


def find_numbered(lines, prefix):
    pat = re.compile(rf"{prefix}\s*([0-9]+)\s*[-－]\s*([0-9]+)")
    found = []
    for idx, item in enumerate(lines, 1):
        for match in pat.finditer(item["text"]):
            found.append((idx, item["source"], item["text"], int(match.group(1)), int(match.group(2)), match.group(0)))
    return found


def seq_issues(found):
    by_chapter = defaultdict(list)
    for idx, src, text, ch, no, raw in found:
        by_chapter[ch].append((no, idx, text, raw))
    issues = []
    for ch, values in sorted(by_chapter.items()):
        counts = Counter(no for no, *_ in values)
        duplicates = sorted(no for no, count in counts.items() if count > 1)
        existing = sorted(counts)
        missing = [n for n in range(existing[0], existing[-1] + 1) if n not in counts] if existing else []
        if duplicates or missing:
            issues.append((ch, duplicates, missing, existing))
    return issues


def find_refs(lines, prefix):
    pat = re.compile(rf"{prefix}\s*([0-9]+)\s*[-－]\s*([0-9]+)")
    refs = []
    for idx, item in enumerate(lines, 1):
        text = item["text"]
        if text.startswith(prefix):
            continue
        for match in pat.finditer(text):
            refs.append((idx, item["source"], text, int(match.group(1)), int(match.group(2)), match.group(0)))
    return refs


paragraphs = read_parts()
main_paragraphs = [p for p in paragraphs if p["source"] == "word/document.xml"]
full_text = "\n".join(p["text"] for p in main_paragraphs)

fig_caps = [x for x in find_numbered(main_paragraphs, "图") if x[2].lstrip().startswith("图")]
tab_caps = [x for x in find_numbered(main_paragraphs, "表") if x[2].lstrip().startswith("表")]
formula_nums = []
formula_pat = re.compile(r"[（(]\s*([0-9]+)\s*[-－]\s*([0-9]+)\s*[）)]")
for idx, item in enumerate(main_paragraphs, 1):
    # Exclude figure/table captions from formula label checks.
    if item["text"].lstrip().startswith(("图", "表")):
        continue
    for match in formula_pat.finditer(item["text"]):
        formula_nums.append(
            (idx, item["source"], item["text"], int(match.group(1)), int(match.group(2)), match.group(0))
        )

fig_refs = find_refs(main_paragraphs, "图")
tab_refs = find_refs(main_paragraphs, "表")

report = []
report.append(f"文件: {DOCX}")
report.append(f"正文段落数: {len(main_paragraphs)}")
report.append(f"图题数量: {len(fig_caps)}")
report.append(f"表题数量: {len(tab_caps)}")
report.append(f"疑似公式编号数量: {len(formula_nums)}")
report.append("")

report.append("## 章节标题")
heading_like = []
for idx, item in enumerate(main_paragraphs, 1):
    text = item["text"]
    if re.match(r"^第[一二三四五六七八九十]+章", text) or re.match(r"^\d+(\.\d+){0,2}\s+", text):
        heading_like.append((idx, item["style"], text))
for idx, style, text in heading_like[:120]:
    report.append(f"[{idx}] style={style or '-'} {text}")
report.append("")

report.append("## 图题")
for idx, src, text, ch, no, raw in fig_caps:
    report.append(f"[{idx}] {text}")
report.append("")

report.append("## 表题")
for idx, src, text, ch, no, raw in tab_caps:
    report.append(f"[{idx}] {text}")
report.append("")

report.append("## 图表编号连续性")
for name, found in [("图", fig_caps), ("表", tab_caps), ("公式", formula_nums)]:
    issues = seq_issues(found)
    report.append(f"{name}:")
    if not issues:
        report.append("  未发现重复或断号")
    for ch, duplicates, missing, existing in issues:
        report.append(f"  第{ch}章 existing={existing} duplicate={duplicates or '-'} missing={missing or '-'}")
report.append("")

report.append("## 引用但未找到对应题注")
fig_cap_set = {(ch, no) for _, _, _, ch, no, _ in fig_caps}
tab_cap_set = {(ch, no) for _, _, _, ch, no, _ in tab_caps}
missing_fig_refs = [r for r in fig_refs if (r[3], r[4]) not in fig_cap_set]
missing_tab_refs = [r for r in tab_refs if (r[3], r[4]) not in tab_cap_set]
for label, refs in [("图", missing_fig_refs), ("表", missing_tab_refs)]:
    report.append(f"{label}: {len(refs)}")
    for idx, src, text, ch, no, raw in refs[:80]:
        report.append(f"  [{idx}] {raw}: {text}")
report.append("")

report.append("## 可能需要人工检查的关键词")
keywords = [
    "图4-X",
    "图 4-X",
    "表4-X",
    "表 4-X",
    "这里放",
    "TODO",
    "待",
    "xxx",
    "XXX",
    "？？",
    "??",
    "目标连续跟踪对视频进行检测",
    "目标连续跟踪",
    "视频进行检测",
    "others",
    "Others",
]
for kw in keywords:
    hits = [(i, p["text"]) for i, p in enumerate(main_paragraphs, 1) if kw in p["text"]]
    if hits:
        report.append(f"{kw}: {len(hits)}")
        for i, text in hits[:30]:
            report.append(f"  [{i}] {text}")
report.append("")

report.append("## 英文术语大小写统计")
terms = [
    "YOLOv8", "yolov8", "Yolov8", "DeepSORT", "DeepSort", "deepsort",
    "KNN", "knn", "HOG", "hog", "IoU", "IOU", "iou", "mAP", "MAP",
    "Precision", "precision", "Recall", "recall", "Accuracy", "accuracy",
    "F1", "standing", "Standing", "walking", "Walking", "lying", "Lying",
    "BaseBehavior", "FinalBehavior", "Behavior", "Location", "Time",
    "Feeding", "Drinking", "Resting", "Others", "others",
]
for term in terms:
    count = len(re.findall(re.escape(term), full_text))
    if count:
        report.append(f"{term}: {count}")
report.append("")

report.append("## 英文半角引号/特殊符号")
quote_chars = ['"', "'", "“", "”", "‘", "’"]
for char in quote_chars:
    count = full_text.count(char)
    if count:
        report.append(f"{repr(char)}: {count}")
for idx, p in enumerate(main_paragraphs, 1):
    if '"' in p["text"] or "'" in p["text"]:
        report.append(f"  [{idx}] {p['text']}")
report.append("")

report.append("## 重点段落：第4章附近")
for idx, p in enumerate(main_paragraphs, 1):
    text = p["text"]
    if text.startswith("4.") or text.startswith("第4章") or text.startswith("第四章") or "图 4-" in text or "表 4-" in text:
        report.append(f"[{idx}] {text}")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(report), encoding="utf-8")
print(OUT)
