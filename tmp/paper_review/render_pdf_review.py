from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import pypdfium2 as pdfium


ROOT = Path.cwd()
OUT = ROOT / "tmp" / "paper_review"
PAGES = OUT / "pages"
SHEETS = OUT / "sheets"
PDF_PATH = ROOT / "余涛初稿.pdf"


def make_contact_sheets() -> None:
    PAGES.mkdir(parents=True, exist_ok=True)
    SHEETS.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(PDF_PATH)
    thumbs: list[Path] = []
    font = ImageFont.load_default()

    for idx in range(len(pdf)):
        page = pdf[idx]
        bitmap = page.render(scale=0.45)
        image = bitmap.to_pil().convert("RGB")
        draw = ImageDraw.Draw(image)
        label = f"PDF page {idx + 1}"
        draw.rectangle((0, 0, 110, 18), fill="white")
        draw.text((4, 3), label, fill="black", font=font)
        path = PAGES / f"page_{idx + 1:02d}.png"
        image.save(path)
        thumbs.append(path)

    columns = 3
    rows = 3
    pad = 18
    for sheet_idx, start in enumerate(range(0, len(thumbs), columns * rows), 1):
        group = thumbs[start : start + columns * rows]
        images = [Image.open(path).convert("RGB") for path in group]
        width = max(image.width for image in images)
        height = max(image.height for image in images)
        sheet = Image.new(
            "RGB",
            (columns * width + (columns + 1) * pad, rows * height + (rows + 1) * pad),
            "white",
        )
        for offset, image in enumerate(images):
            row = offset // columns
            col = offset % columns
            x = pad + col * (width + pad)
            y = pad + row * (height + pad)
            sheet.paste(image, (x, y))
        sheet_path = SHEETS / f"sheet_{sheet_idx:02d}.png"
        sheet.save(sheet_path)
        print(sheet_path)


def render_selected_pages(pages: list[int]) -> None:
    selected = OUT / "selected_pages"
    selected.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(PDF_PATH)
    for page_no in pages:
        if page_no < 1 or page_no > len(pdf):
            continue
        page = pdf[page_no - 1]
        bitmap = page.render(scale=1.6)
        image = bitmap.to_pil().convert("RGB")
        path = selected / f"page_{page_no:02d}.png"
        image.save(path)
        print(path)


if __name__ == "__main__":
    make_contact_sheets()
    render_selected_pages(
        [
            1, 2, 3, 4, 5, 6,
            14, 15, 16, 17, 18, 22, 23,
            28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41,
            51, 52, 53,
        ]
    )
