from __future__ import annotations

import csv
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ["YOLO_CONFIG_DIR"] = str(PROJECT_ROOT / "code" / "yolov8" / "yolo_config")
sys.path.insert(0, str(PROJECT_ROOT / "code" / "yolov8" / "ultralytics"))

from ultralytics import YOLO  # noqa: E402


def get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def get_font_prop() -> font_manager.FontProperties | None:
    path = Path(r"C:\Windows\Fonts\msyh.ttc")
    return font_manager.FontProperties(fname=str(path)) if path.exists() else None


def main() -> None:
    out_dir = PROJECT_ROOT / "output" / "counting_experiment_dedup035"
    pic_dir = PROJECT_ROOT / "图片"
    images_dir = PROJECT_ROOT / "all_datasets" / "cowDataset" / "images" / "val"
    model_path = PROJECT_ROOT / "runs" / "detect" / "cow_120_on_basecommon" / "weights" / "best.pt"
    pic_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "yolov8_counting_dedup035_results.csv").open(encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    samples = []
    for target_count in (2, 6, 7):
        sample = next(
            row
            for row in rows
            if int(row["true_count"]) == target_count and int(row["pred_count"]) == target_count
        )
        samples.append(sample)

    model = YOLO(str(model_path))
    header_font = get_font(34)
    label_font = get_font(28)

    panel_w, panel_h = 520, 390
    header_h, caption_h = 54, 54
    gap, pad = 28, 26
    canvas = Image.new(
        "RGB",
        (pad * 2 + panel_w * 3 + gap * 2, pad * 2 + header_h + panel_h + caption_h),
        "white",
    )
    draw = ImageDraw.Draw(canvas)

    for index, row in enumerate(samples):
        image_path = images_dir / row["image_name"]
        result = model.predict(
            source=str(image_path),
            conf=0.35,
            iou=0.45,
            imgsz=832,
            device="cpu",
            verbose=False,
        )[0]
        bgr = cv2.imdecode(np.fromfile(str(image_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        annotated = image.copy()
        annotated_draw = ImageDraw.Draw(annotated)
        boxes = [] if result.boxes is None else result.boxes.xyxy.cpu().numpy()
        for box in boxes:
            x1, y1, x2, y2 = [float(value) for value in box]
            annotated_draw.rectangle(
                (x1, y1, x2, y2),
                outline=(255, 196, 0),
                width=max(3, round(min(image.size) / 180)),
            )

        annotated.thumbnail((panel_w, panel_h), Image.Resampling.LANCZOS)
        x = pad + index * (panel_w + gap)
        y = pad + header_h
        tile = Image.new("RGB", (panel_w, panel_h), (247, 248, 246))
        tile.paste(annotated, ((panel_w - annotated.width) // 2, (panel_h - annotated.height) // 2))
        canvas.paste(tile, (x, y))
        draw.rectangle((x, y, x + panel_w - 1, y + panel_h - 1), outline=(65, 105, 65), width=2)

        header = "真实数量：{}    预测数量：{}".format(row["true_count"], row["pred_count"])
        bbox = draw.textbbox((0, 0), header, font=header_font)
        draw.text((x + (panel_w - (bbox[2] - bbox[0])) // 2, pad + 6), header, fill=(0, 0, 0), font=header_font)

        caption = "（{}）计数结果示例".format(chr(97 + index))
        caption_bbox = draw.textbbox((0, 0), caption, font=label_font)
        draw.text(
            (x + (panel_w - (caption_bbox[2] - caption_bbox[0])) // 2, y + panel_h + 10),
            caption,
            fill=(0, 0, 0),
            font=label_font,
        )

    example_path = out_dir / "yolov8_counting_examples_dedup035.png"
    canvas.save(example_path)
    shutil.copyfile(example_path, pic_dir / "图4-X_YOLOv8牛只计数结果示例.png")

    error_counter = Counter(int(row["abs_error"]) for row in rows)
    xs = ["0", "1", "2", "3", "4", "5", ">=6"]
    ys = [error_counter.get(index, 0) for index in range(6)]
    ys.append(sum(value for key, value in error_counter.items() if key >= 6))
    font_prop = get_font_prop()

    plt.figure(figsize=(8, 4.6), dpi=180)
    plt.bar(xs, ys, color="#4f7f6a")
    plt.xlabel("绝对计数误差", fontproperties=font_prop)
    plt.ylabel("图像数量", fontproperties=font_prop)
    plt.xticks(fontproperties=font_prop)
    plt.yticks(fontproperties=font_prop)
    for index, value in enumerate(ys):
        plt.text(index, value + max(ys) * 0.01, str(value), ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    error_path = out_dir / "yolov8_count_error_distribution_dedup035.png"
    plt.savefig(error_path)
    plt.close()
    shutil.copyfile(error_path, pic_dir / "图4-X_YOLOv8计数误差分布.png")

    print(example_path)
    print(error_path)
    for row in samples:
        print(row["image_name"], row["true_count"], row["pred_count"])


if __name__ == "__main__":
    main()
