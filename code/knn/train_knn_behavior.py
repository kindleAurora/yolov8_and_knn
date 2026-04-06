from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import numpy as np

from knn_utils import (
    DEFAULT_CLASS_NAMES,
    NumpyKNNClassifier,
    build_feature_matrix,
    compute_confusion_matrix,
    compute_class_accuracy,
    format_confusion_matrix,
    load_split_image_paths,
)


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[2]
    default_dataset = project_root / "code" / "knn" / "bahavior_dateset"
    default_output = project_root / "code" / "knn" / "knn_behavior_model.npz"
    default_report = project_root / "code" / "knn" / "knn_behavior_metrics.txt"

    parser = argparse.ArgumentParser(description="Train a posture-behavior KNN model with fixed train/valid/test splits.")
    parser.add_argument("--dataset", type=Path, default=default_dataset, help="Dataset root with split/class subfolders.")
    parser.add_argument("--output", type=Path, default=default_output, help="Output .npz file for the KNN model.")
    parser.add_argument("--report", type=Path, default=default_report, help="Text report path for evaluation metrics.")
    parser.add_argument("--classes", nargs="+", default=list(DEFAULT_CLASS_NAMES), help="Class names in folder order.")
    parser.add_argument("--k", type=int, default=9, help="Number of nearest neighbors.")
    parser.add_argument("--image-size", type=int, default=64, help="Input size used before HOG feature extraction.")
    return parser.parse_args()


def build_distribution(labels: list[int], class_names: list[str]) -> dict[str, int]:
    counter = Counter(labels)
    return {class_name: counter.get(class_index, 0) for class_index, class_name in enumerate(class_names)}


def evaluate_split(
    classifier: NumpyKNNClassifier,
    split_name: str,
    features: np.ndarray,
    labels_array: np.ndarray,
    class_names: list[str],
) -> list[str]:
    predictions = classifier.predict_batch(features)
    accuracy = float(np.mean(predictions == labels_array))
    confusion_matrix = compute_confusion_matrix(labels_array, predictions, num_classes=len(class_names))

    return [
        f"{split_name} result",
        f"Overall accuracy: {accuracy:.4f}",
        *compute_class_accuracy(labels_array, predictions, class_names),
        "Confusion matrix (rows=true, cols=pred):",
        *format_confusion_matrix(confusion_matrix, class_names),
        "",
    ]


def main() -> None:
    args = parse_args()

    if not (args.dataset / "train").exists():
        raise FileNotFoundError(
            f"Expected split-aware dataset under {args.dataset}. "
            "Please rerun build_behavior_dataset.py to generate train/valid/test folders."
        )

    train_paths, train_labels = load_split_image_paths(args.dataset, "train", args.classes)
    valid_paths, valid_labels = load_split_image_paths(args.dataset, "valid", args.classes)
    test_paths, test_labels = load_split_image_paths(args.dataset, "test", args.classes)

    print("Dataset loaded successfully.")
    print(f"Dataset root: {args.dataset}")
    print(f"Classes: {args.classes}")
    print(f"Train images: {len(train_paths)}")
    print(f"Valid images: {len(valid_paths)}")
    print(f"Test images: {len(test_paths)}")
    print(f"Train class distribution: {build_distribution(train_labels, args.classes)}")
    print(f"Valid class distribution: {build_distribution(valid_labels, args.classes)}")
    print(f"Test class distribution: {build_distribution(test_labels, args.classes)}")

    print("\nExtracting train features...")
    train_features = build_feature_matrix(train_paths, image_size=args.image_size)
    train_labels_array = np.asarray(train_labels, dtype=np.int32)

    print("Extracting valid features...")
    valid_features = build_feature_matrix(valid_paths, image_size=args.image_size)
    valid_labels_array = np.asarray(valid_labels, dtype=np.int32)

    print("Extracting test features...")
    test_features = build_feature_matrix(test_paths, image_size=args.image_size)
    test_labels_array = np.asarray(test_labels, dtype=np.int32)

    classifier = NumpyKNNClassifier(k=args.k)
    classifier.fit(
        train_features=train_features,
        train_labels=train_labels_array,
        class_names=list(args.classes),
        image_size=args.image_size,
    )

    valid_report_lines = evaluate_split(classifier, "Valid", valid_features, valid_labels_array, list(args.classes))
    test_report_lines = evaluate_split(classifier, "Test", test_features, test_labels_array, list(args.classes))

    report_lines = [
        "KNN behavior classification report",
        f"Dataset root: {args.dataset}",
        f"Classes: {args.classes}",
        f"k: {args.k}",
        f"image_size: {args.image_size}",
        f"Train images: {len(train_paths)}",
        f"Valid images: {len(valid_paths)}",
        f"Test images: {len(test_paths)}",
        f"Train class distribution: {build_distribution(train_labels, args.classes)}",
        f"Valid class distribution: {build_distribution(valid_labels, args.classes)}",
        f"Test class distribution: {build_distribution(test_labels, args.classes)}",
        "",
        *valid_report_lines,
        *test_report_lines,
    ]

    print("\nValid/Test evaluation completed.")
    print("\n".join(valid_report_lines))
    print("\n".join(test_report_lines))

    classifier.save(args.output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nKNN model saved to: {args.output}")
    print(f"Evaluation report saved to: {args.report}")


if __name__ == "__main__":
    main()
