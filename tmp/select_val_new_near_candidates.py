from pathlib import Path
import csv
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"C:/Users/Admin/Desktop/毕设")
IMAGES_DIR = ROOT / "all_datasets/cowDataset/images/val_new"
LABELS_DIR = ROOT / "all_datasets/cowDataset/labels/val_new"
RESULTS_CSV = ROOT / "output/counting_experiment_val_new/yolov8_counting_val_new_results.csv"
OUT = ROOT / "tmp/figures/val_new_near_count_candidates.png"


def load_font(size: int):
    for path in [
        r"C:/Windows/Fonts/msyh.ttc",
        r"C:/Windows/Fonts/arial.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def label_area_score(label_path: Path) -> tuple[float, int]:
    """Return max normalized bbox area and number of labels for this image."""
    if not label_path.exists():
        return 0.0, 0
    max_area = 0.0
    count = 0
    for line in label_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            w = float(parts[3])
            h = float(parts[4])
        except ValueError:
            continue
        max_area = max(max_area, w * h)
        count += 1
    return max_area, count


rows = []
with RESULTS_CSV.open("r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        true_count = int(float(row["true_count"]))
        pred_count = int(float(row["pred_count"]))
        if true_count != pred_count:
            continue
        if true_count < 2:
            continue
        img_path = IMAGES_DIR / row["image_name"]
        if not img_path.exists():
            continue
        max_area, label_count = label_area_score(LABELS_DIR / (img_path.stem + ".txt"))
        if label_count != true_count:
            continue
        rows.append(
            {
                "image_name": row["image_name"],
                "true_count": true_count,
                "pred_count": pred_count,
                "max_area": max_area,
                "score": max_area / max(1, true_count),
            }
        )

rows.sort(key=lambda item: (item["max_area"], -item["true_count"]), reverse=True)

# Keep a balanced candidate set: high-area examples plus several multi-cow examples.
selected = []
used = set()
for row in rows:
    if row["image_name"] in used:
        continue
    selected.append(row)
    used.add(row["image_name"])
    if len(selected) >= 24:
        break

thumb_w, thumb_h = 360, 220
label_h = 44
cols = 4
rows_n = (len(selected) + cols - 1) // cols
canvas = Image.new("RGB", (cols * thumb_w, rows_n * (thumb_h + label_h)), "white")
draw = ImageDraw.Draw(canvas)
font = load_font(24)
small = load_font(18)

for idx, row in enumerate(selected):
    x0 = (idx % cols) * thumb_w
    y0 = (idx // cols) * (thumb_h + label_h)
    img = Image.open(IMAGES_DIR / row["image_name"]).convert("RGB")
    img.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
    tile = Image.new("RGB", (thumb_w, thumb_h), (245, 245, 245))
    tx = (thumb_w - img.width) // 2
    ty = (thumb_h - img.height) // 2
    tile.paste(img, (tx, ty))
    canvas.paste(tile, (x0, y0))
    text = "{}  真值={}  预测={}  面积={:.3f}".format(
        row["image_name"], row["true_count"], row["pred_count"], row["max_area"]
    )
    draw.rectangle([x0, y0 + thumb_h, x0 + thumb_w, y0 + thumb_h + label_h], fill=(255, 255, 255))
    draw.text((x0 + 8, y0 + thumb_h + 4), text, fill=(0, 0, 0), font=small)
    draw.rectangle([x0, y0, x0 + thumb_w - 1, y0 + thumb_h + label_h - 1], outline=(210, 210, 210), width=1)

OUT.parent.mkdir(parents=True, exist_ok=True)
canvas.save(OUT, quality=95)
print(OUT)
for row in selected[:12]:
    print("{} true={} pred={} max_area={:.4f}".format(
        row["image_name"], row["true_count"], row["pred_count"], row["max_area"]
    ))
