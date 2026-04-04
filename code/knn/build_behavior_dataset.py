from __future__ import annotations

from collections import Counter
from pathlib import Path
import shutil

import cv2
import numpy as np


DATASET_ROOT = Path(r"C:\Users\Admin\Desktop\毕设\all_datasets\牛只行为姿态数据集")
OUTPUT_ROOT = Path(r"C:\Users\Admin\Desktop\毕设\code\knn\bahavior_dateset")

SPLITS = ("train", "valid", "test")
CLASS_TO_FOLDER = {
    "0": "lying",
    "1": "standing",
    "2": "walking",
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def imread_unicode(image_path: Path) -> np.ndarray:
    """Use OpenCV safely with Chinese paths."""
    data = np.fromfile(str(image_path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Failed to read image: {image_path}")
    return image


def imwrite_unicode(image_path: Path, image: np.ndarray) -> None:
    suffix = image_path.suffix or ".jpg"
    success, encoded = cv2.imencode(suffix, image)
    if not success:
        raise ValueError(f"Failed to encode image for saving: {image_path}")
    encoded.tofile(str(image_path))


def prepare_output_dirs() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for folder_name in CLASS_TO_FOLDER.values():
        output_dir = OUTPUT_ROOT / folder_name
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)


def parse_label_file(label_path: Path) -> list[tuple[str, float, float, float, float]]:
    annotations: list[tuple[str, float, float, float, float]] = []

    for line_number, raw_line in enumerate(label_path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid YOLO label format at {label_path}:{line_number} -> {raw_line!r}")

        class_id, x_center, y_center, box_width, box_height = parts
        annotations.append((class_id, float(x_center), float(y_center), float(box_width), float(box_height)))

    return annotations


def yolo_box_to_xyxy(
    x_center: float,
    y_center: float,
    box_width: float,
    box_height: float,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    """Convert normalized YOLO coordinates to pixel coordinates."""
    x1 = int(round((x_center - box_width / 2) * image_width))
    y1 = int(round((y_center - box_height / 2) * image_height))
    x2 = int(round((x_center + box_width / 2) * image_width))
    y2 = int(round((y_center + box_height / 2) * image_height))

    x1 = max(0, min(x1, image_width - 1))
    y1 = max(0, min(y1, image_height - 1))
    x2 = max(x1 + 1, min(x2, image_width))
    y2 = max(y1 + 1, min(y2, image_height))
    return x1, y1, x2, y2


def crop_and_save_annotations(image_path: Path, label_path: Path, split_name: str, saved_by_class: Counter[str]) -> int:
    image = imread_unicode(image_path)
    image_height, image_width = image.shape[:2]
    annotations = parse_label_file(label_path)

    saved_count = 0
    for annotation_index, (class_id, x_center, y_center, box_width, box_height) in enumerate(annotations, start=1):
        if class_id not in CLASS_TO_FOLDER:
            continue

        x1, y1, x2, y2 = yolo_box_to_xyxy(
            x_center=x_center,
            y_center=y_center,
            box_width=box_width,
            box_height=box_height,
            image_width=image_width,
            image_height=image_height,
        )

        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        folder_name = CLASS_TO_FOLDER[class_id]
        save_name = f"{split_name}_{image_path.stem}_{annotation_index:02d}{image_path.suffix.lower()}"
        save_path = OUTPUT_ROOT / folder_name / save_name
        imwrite_unicode(save_path, crop)

        saved_count += 1
        saved_by_class[folder_name] += 1

    return saved_count


def main() -> None:
    prepare_output_dirs()

    total_images = 0
    total_saved_crops = 0
    skipped_missing_labels = 0
    skipped_missing_split_dirs = 0
    saved_by_class: Counter[str] = Counter()

    for split_name in SPLITS:
        images_dir = DATASET_ROOT / split_name / "images"
        labels_dir = DATASET_ROOT / split_name / "labels"

        if not images_dir.exists() or not labels_dir.exists():
            skipped_missing_split_dirs += 1
            print(f"Skip split '{split_name}' because images or labels directory is missing.")
            continue

        image_paths = sorted(
            path for path in images_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        print(f"Processing split: {split_name}, images: {len(image_paths)}")

        for image_path in image_paths:
            total_images += 1
            label_path = labels_dir / f"{image_path.stem}.txt"

            if not label_path.exists():
                skipped_missing_labels += 1
                continue

            saved_count = crop_and_save_annotations(
                image_path=image_path,
                label_path=label_path,
                split_name=split_name,
                saved_by_class=saved_by_class,
            )
            total_saved_crops += saved_count

    print("\nBuild behavior dataset completed.")
    print(f"Total images scanned: {total_images}")
    print(f"Total cropped cows saved: {total_saved_crops}")
    print(f"Skipped for missing labels: {skipped_missing_labels}")
    print(f"Skipped missing split directories: {skipped_missing_split_dirs}")
    print("Saved crops by class:")
    for class_name in CLASS_TO_FOLDER.values():
        print(f"  {class_name}: {saved_by_class[class_name]}")


if __name__ == "__main__":
    main()
