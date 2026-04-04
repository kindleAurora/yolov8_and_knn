from __future__ import annotations

import shutil
from pathlib import Path


DATASET_ROOT = Path(
    "C:\\Users\\Admin\\Desktop\\\u6bd5\u8bbe\\all_datasets\\\u725b\u53ea\u884c\u4e3a\u59ff\u6001\u6570\u636e\u96c6"
)
TRAIN_IMAGES_DIR = DATASET_ROOT / "train" / "images"
TRAIN_LABELS_DIR = DATASET_ROOT / "train" / "labels"
OUTPUT_ROOT = Path("C:\\Users\\Admin\\Desktop\\\u6bd5\u8bbe\\code\\knn\\bahavior_dateset")

# The Roboflow project name is "cow-lie-stand-walk", while data.yaml stores
# class names as 0/1/2. We therefore map the YOLO ids in that order here.
CLASS_TO_FOLDER = {
    "0": "lying",
    "1": "standing",
    "2": "walking",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def parse_label_class_ids(label_path: Path) -> list[str]:
    class_ids: list[str] = []
    for line in label_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        class_ids.append(line.split()[0])
    return class_ids


def prepare_output_dirs() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for folder_name in CLASS_TO_FOLDER.values():
        destination_dir = OUTPUT_ROOT / folder_name
        if destination_dir.exists():
            shutil.rmtree(destination_dir)
        destination_dir.mkdir(parents=True, exist_ok=True)


def copy_image_to_behavior_dir(image_path: Path, class_id: str) -> Path:
    destination_dir = OUTPUT_ROOT / CLASS_TO_FOLDER[class_id]
    destination_path = destination_dir / image_path.name
    shutil.copy2(image_path, destination_path)
    return destination_path


def main() -> None:
    if not TRAIN_IMAGES_DIR.exists():
        raise FileNotFoundError(f"Training image directory not found: {TRAIN_IMAGES_DIR}")
    if not TRAIN_LABELS_DIR.exists():
        raise FileNotFoundError(f"Training label directory not found: {TRAIN_LABELS_DIR}")

    prepare_output_dirs()

    image_paths = sorted(
        path for path in TRAIN_IMAGES_DIR.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )

    total_images = 0
    copied_images = 0
    skipped_missing_labels = 0
    skipped_unknown_classes = 0
    skipped_multiple_cows = 0

    for image_path in image_paths:
        total_images += 1
        label_path = TRAIN_LABELS_DIR / f"{image_path.stem}.txt"
        if not label_path.exists():
            skipped_missing_labels += 1
            continue

        class_ids = parse_label_class_ids(label_path)
        if not class_ids:
            skipped_unknown_classes += 1
            continue
        if any(class_id not in CLASS_TO_FOLDER for class_id in class_ids):
            skipped_unknown_classes += 1
            continue
        if len(class_ids) != 1:
            skipped_multiple_cows += 1
            continue

        class_id = class_ids[0]
        copy_image_to_behavior_dir(image_path, class_id)
        copied_images += 1

    print("Copy completed")
    print(f"Total images: {total_images}")
    print(f"Copied single-cow images: {copied_images}")
    print(f"Skipped for missing labels: {skipped_missing_labels}")
    print(f"Skipped for unknown classes: {skipped_unknown_classes}")
    print(f"Skipped for multiple cows: {skipped_multiple_cows}")
    print("Class mapping:")
    for class_id, folder_name in CLASS_TO_FOLDER.items():
        print(f"  {class_id} -> {folder_name}")


if __name__ == "__main__":
    main()
