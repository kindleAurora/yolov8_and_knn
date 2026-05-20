from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROWS = list(
    csv.DictReader(
        (PROJECT_ROOT / "output/counting_experiment_val_new/yolov8_counting_val_new_results.csv").open(
            encoding="utf-8"
        )
    )
)
IMG_DIR = PROJECT_ROOT / "all_datasets/cowDataset/images/val_new"
LABEL_DIR = PROJECT_ROOT / "all_datasets/cowDataset/labels/val_new"


def get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = Path(r"C:\Windows\Fonts\msyh.ttc")
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def box_area_scores(name: str) -> tuple[float, float]:
    label_path = LABEL_DIR / (Path(name).stem + ".txt")
    areas = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split()
        areas.append(float(parts[3]) * float(parts[4]))
    return (max(areas), sum(areas) / len(areas)) if areas else (0.0, 0.0)


def main() -> None:
    candidates = []
    for target_count in (2, 6, 7):
        exact_rows = [
            row
            for row in ROWS
            if int(row["true_count"]) == target_count and int(row["pred_count"]) == target_count
        ]
        scored = []
        for row in exact_rows:
            max_area, avg_area = box_area_scores(row["image_name"])
            scored.append((max_area, avg_area, row))
        scored.sort(reverse=True, key=lambda item: (item[0], item[1]))
        print("TARGET", target_count, "n", len(scored))
        for index, (max_area, avg_area, row) in enumerate(scored[:12], start=1):
            print(index, row["image_name"], "max", f"{max_area:.4f}", "avg", f"{avg_area:.4f}")
        candidates.extend((target_count, max_area, avg_area, row) for max_area, avg_area, row in scored[:8])

    font = get_font(18)
    thumb_w, thumb_h, label_h = 280, 190, 44
    cols = 4
    canvas = Image.new(
        "RGB",
        (cols * thumb_w, ((len(candidates) + cols - 1) // cols) * (thumb_h + label_h)),
        "white",
    )
    draw = ImageDraw.Draw(canvas)
    for index, (target_count, max_area, avg_area, row) in enumerate(candidates):
        image = Image.open(IMG_DIR / row["image_name"]).convert("RGB")
        image.thumbnail((thumb_w - 12, thumb_h - 12), Image.Resampling.LANCZOS)
        grid_row, grid_col = divmod(index, cols)
        x = grid_col * thumb_w
        y = grid_row * (thumb_h + label_h)
        canvas.paste(image, (x + (thumb_w - image.width) // 2, y + (thumb_h - image.height) // 2))
        draw.rectangle((x + 3, y + 3, x + thumb_w - 4, y + thumb_h - 4), outline=(60, 100, 60), width=2)
        draw.text((x + 8, y + thumb_h + 4), f"{target_count} {row['image_name']}", fill=(0, 0, 0), font=font)
        draw.text((x + 8, y + thumb_h + 24), f"max={max_area:.3f} avg={avg_area:.3f}", fill=(0, 0, 0), font=font)

    out = PROJECT_ROOT / "tmp/figures/val_new_near_count_candidates.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    print("sheet", out)


if __name__ == "__main__":
    main()
