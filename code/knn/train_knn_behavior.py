from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import numpy as np

from knn_utils import (
    DEFAULT_CLASS_NAMES,
    NumpyKNNClassifier,
    build_feature_matrix,
    compute_class_accuracy,
    load_image_paths,
    stratified_split,
)


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[2]
    default_dataset = project_root / "code" / "knn" / "bahavior_dateset"
    default_output = project_root / "code" / "knn" / "knn_behavior_model.npz"

    parser = argparse.ArgumentParser(description="Train a posture-behavior KNN model from folder-organized images.")
    parser.add_argument("--dataset", type=Path, default=default_dataset, help="Dataset root with class subfolders.")
    parser.add_argument("--output", type=Path, default=default_output, help="Output .npz file for the KNN model.")
    parser.add_argument("--classes", nargs="+", default=list(DEFAULT_CLASS_NAMES), help="Class names in folder order.")
    parser.add_argument("--k", type=int, default=5, help="Number of nearest neighbors.")
    parser.add_argument("--image-size", type=int, default=64, help="Input size used before HOG feature extraction.")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Validation split ratio.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for the split.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    image_paths, labels = load_image_paths(args.dataset, args.classes)
    train_paths, train_labels, val_paths, val_labels = stratified_split(
        image_paths=image_paths,
        labels=labels,
        val_ratio=args.val_ratio,
        seed=args.seed,
    )

    print("Dataset loaded successfully.")
    print(f"Dataset root: {args.dataset}")
    print(f"Classes: {args.classes}")
    print(f"Total images: {len(image_paths)}")
    print(f"Train images: {len(train_paths)}")
    print(f"Validation images: {len(val_paths)}")
    print(f"Train class distribution: {dict(Counter(train_labels))}")
    print(f"Validation class distribution: {dict(Counter(val_labels))}")

    print("\nExtracting train features...")
    train_features = build_feature_matrix(train_paths, image_size=args.image_size)
    train_labels_array = np.asarray(train_labels, dtype=np.int32)

    print("Extracting validation features...")
    val_features = build_feature_matrix(val_paths, image_size=args.image_size)
    val_labels_array = np.asarray(val_labels, dtype=np.int32)

    classifier = NumpyKNNClassifier(k=args.k)
    classifier.fit(
        train_features=train_features,
        train_labels=train_labels_array,
        class_names=list(args.classes),
        image_size=args.image_size,
    )

    val_predictions = classifier.predict_batch(val_features)
    val_accuracy = float(np.mean(val_predictions == val_labels_array))

    print("\nValidation result")
    print(f"Overall accuracy: {val_accuracy:.4f}")
    for line in compute_class_accuracy(val_labels_array, val_predictions, args.classes):
        print(line)

    classifier.save(args.output)
    print(f"\nKNN model saved to: {args.output}")


if __name__ == "__main__":
    main()
