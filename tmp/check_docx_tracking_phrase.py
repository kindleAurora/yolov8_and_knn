from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import re


DOCX = Path("余涛初稿改3.docx")
TERMS = [
    "目标连续跟踪对视频进行检测",
    "目标连续跟踪",
    "连续跟踪",
    "视频进行检测",
]
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


paragraphs = []
with ZipFile(DOCX) as zf:
    names = ["word/document.xml"] + sorted(
        name
        for name in zf.namelist()
        if name.startswith("word/header") or name.startswith("word/footer")
    )
    for name in names:
        root = ET.fromstring(zf.read(name))
        for paragraph in root.findall(".//w:p", NS):
            text = "".join(node.text or "" for node in paragraph.findall(".//w:t", NS)).strip()
            if text:
                paragraphs.append((name, text))

for term in TERMS:
    hits = [
        (index, source, text)
        for index, (source, text) in enumerate(paragraphs, 1)
        if term in text or compact(term) in compact(text)
    ]
    print(f"### {term} | hits={len(hits)}")
    for index, source, text in hits[:80]:
        print(f"[{index}] {source}: {text}")
    print()

print("### 同时包含“视频”和“跟踪/检测”的段落")
count = 0
for index, (source, text) in enumerate(paragraphs, 1):
    if "视频" in text and ("跟踪" in text or "检测" in text):
        count += 1
        print(f"[{index}] {source}: {text}")
print(f"合计: {count}")
