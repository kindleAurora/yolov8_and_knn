from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DEFAULT_CLASS_NAMES = ("lying", "standing", "walking")


def imread_unicode(image_path: str | Path) -> np.ndarray:
    """Read an image from a path that may contain Chinese characters."""
    image_path = Path(image_path)
    data = np.fromfile(str(image_path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Failed to read image: {image_path}")
    return image


def resize_with_padding(image: np.ndarray, size: int = 64) -> np.ndarray:
    """Resize while keeping aspect ratio, then pad to a square canvas."""
    height, width = image.shape[:2]
    if height == 0 or width == 0:
        raise ValueError("Image height or width is zero.")

    scale = min(size / width, size / height)
    resized_width = max(1, int(round(width * scale)))
    resized_height = max(1, int(round(height * scale)))
    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_AREA)

    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    x_offset = (size - resized_width) // 2
    y_offset = (size - resized_height) // 2
    canvas[y_offset : y_offset + resized_height, x_offset : x_offset + resized_width] = resized
    return canvas


def extract_hog_feature(image: np.ndarray, image_size: int = 64) -> np.ndarray:
    """
    Convert a crop into a fixed-length feature vector.

    We use HOG because it captures posture/shape better than raw pixels
    and works well with traditional classifiers like KNN.
    """
    original_image = image
    image = resize_with_padding(image, image_size)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    hog = cv2.HOGDescriptor(
        _winSize=(image_size, image_size),
        _blockSize=(16, 16),
        _blockStride=(8, 8),
        _cellSize=(8, 8),
        _nbins=9,
    )
    hog_feature = hog.compute(gray).reshape(-1).astype(np.float32)

    aspect_ratio = np.array([original_image.shape[0] / max(original_image.shape[1], 1)], dtype=np.float32)
    feature = np.concatenate([hog_feature, aspect_ratio], axis=0)
    return feature


def load_image_paths(dataset_root: str | Path, class_names: Iterable[str]) -> tuple[list[Path], list[int]]:
    dataset_root = Path(dataset_root)
    image_paths: list[Path] = []
    labels: list[int] = []

    for class_index, class_name in enumerate(class_names):
        class_dir = dataset_root / class_name
        if not class_dir.exists():
            raise FileNotFoundError(f"Class directory not found: {class_dir}")

        class_images = sorted(
            path for path in class_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        image_paths.extend(class_images)
        labels.extend([class_index] * len(class_images))

    if not image_paths:
        raise FileNotFoundError(f"No images found under dataset root: {dataset_root}")

    return image_paths, labels


def load_split_image_paths(dataset_root: str | Path, split_name: str, class_names: Iterable[str]) -> tuple[list[Path], list[int]]:
    dataset_root = Path(dataset_root)
    split_root = dataset_root / split_name
    if not split_root.exists():
        raise FileNotFoundError(f"Split directory not found: {split_root}")

    image_paths: list[Path] = []
    labels: list[int] = []

    for class_index, class_name in enumerate(class_names):
        class_dir = split_root / class_name
        if not class_dir.exists():
            raise FileNotFoundError(f"Class directory not found: {class_dir}")

        class_images = sorted(
            path for path in class_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        image_paths.extend(class_images)
        labels.extend([class_index] * len(class_images))

    if not image_paths:
        raise FileNotFoundError(f"No images found under split directory: {split_root}")

    return image_paths, labels


def stratified_split(
    image_paths: list[Path], labels: list[int], val_ratio: float = 0.2, seed: int = 42
) -> tuple[list[Path], list[int], list[Path], list[int]]:
    rng = np.random.default_rng(seed)

    train_paths: list[Path] = []
    train_labels: list[int] = []
    val_paths: list[Path] = []
    val_labels: list[int] = []

    unique_labels = sorted(set(labels))
    for label in unique_labels:
        class_items = [path for path, item_label in zip(image_paths, labels) if item_label == label]
        order = rng.permutation(len(class_items))
        class_items = [class_items[index] for index in order]

        val_count = max(1, int(round(len(class_items) * val_ratio)))
        val_subset = class_items[:val_count]
        train_subset = class_items[val_count:]

        if not train_subset:
            train_subset = val_subset[1:]
            val_subset = val_subset[:1]

        train_paths.extend(train_subset)
        train_labels.extend([label] * len(train_subset))
        val_paths.extend(val_subset)
        val_labels.extend([label] * len(val_subset))

    return train_paths, train_labels, val_paths, val_labels


def build_feature_matrix(image_paths: list[Path], image_size: int = 64) -> np.ndarray:
    features = [extract_hog_feature(imread_unicode(path), image_size=image_size) for path in image_paths]
    return np.stack(features, axis=0).astype(np.float32)


def compute_class_accuracy(y_true: np.ndarray, y_pred: np.ndarray, class_names: Iterable[str]) -> list[str]:
    lines: list[str] = []
    for class_index, class_name in enumerate(class_names):
        mask = y_true == class_index
        if not np.any(mask):
            lines.append(f"{class_name}: no samples")
            continue
        accuracy = float(np.mean(y_pred[mask] == y_true[mask]))
        lines.append(f"{class_name}: {accuracy:.4f}")
    return lines


def compute_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray, num_classes: int) -> np.ndarray:
    confusion_matrix = np.zeros((num_classes, num_classes), dtype=np.int32)
    for true_label, pred_label in zip(y_true.astype(np.int32), y_pred.astype(np.int32)):
        confusion_matrix[int(true_label), int(pred_label)] += 1
    return confusion_matrix


def format_confusion_matrix(confusion_matrix: np.ndarray, class_names: Iterable[str]) -> list[str]:
    class_names = list(class_names)
    cell_width = max(9, max(len(name) for name in class_names) + 2)

    header = "true\\pred".ljust(cell_width) + "".join(name.rjust(cell_width) for name in class_names)
    lines = [header]

    for class_name, row in zip(class_names, confusion_matrix):
        row_text = "".join(str(int(value)).rjust(cell_width) for value in row)
        lines.append(class_name.ljust(cell_width) + row_text)

    return lines


@dataclass
class PredictionResult:
    label_index: int
    label_name: str
    confidence: float


class NumpyKNNClassifier:
    def __init__(self, k: int = 5):
        if k <= 0:
            raise ValueError("k must be greater than 0.")
        self.k = k
        self.train_features: np.ndarray | None = None
        self.train_labels: np.ndarray | None = None
        self.class_names: list[str] | None = None
        self.feature_mean: np.ndarray | None = None
        self.feature_std: np.ndarray | None = None
        self.image_size = 64

    def fit(self, train_features: np.ndarray, train_labels: np.ndarray, class_names: list[str], image_size: int) -> None:
        self.feature_mean = train_features.mean(axis=0)
        self.feature_std = train_features.std(axis=0)
        self.feature_std[self.feature_std < 1e-6] = 1.0

        self.train_features = self._normalize(train_features)
        self.train_labels = train_labels.astype(np.int32)
        self.class_names = class_names
        self.image_size = image_size

    def _normalize(self, features: np.ndarray) -> np.ndarray:
        if self.feature_mean is None or self.feature_std is None:
            raise ValueError("Classifier is not fitted yet.")
        return (features - self.feature_mean) / self.feature_std

    def predict(self, feature: np.ndarray) -> PredictionResult:
        if self.train_features is None or self.train_labels is None or self.class_names is None:
            raise ValueError("Classifier is not fitted or loaded yet.")

        feature = self._normalize(feature.reshape(1, -1))[0]
        distances = np.linalg.norm(self.train_features - feature, axis=1)
        nearest_indices = np.argsort(distances)[: self.k]

        scores = np.zeros(len(self.class_names), dtype=np.float32)
        for index in nearest_indices:
            label = int(self.train_labels[index])
            weight = 1.0 / max(float(distances[index]), 1e-6)
            scores[label] += weight

        label_index = int(np.argmax(scores))
        confidence = float(scores[label_index] / max(scores.sum(), 1e-6))
        return PredictionResult(
            label_index=label_index,
            label_name=self.class_names[label_index],
            confidence=confidence,
        )

    def predict_batch(self, features: np.ndarray) -> np.ndarray:
        predictions = [self.predict(feature).label_index for feature in features]
        return np.asarray(predictions, dtype=np.int32)

    def save(self, model_path: str | Path) -> None:
        if (
            self.train_features is None
            or self.train_labels is None
            or self.class_names is None
            or self.feature_mean is None
            or self.feature_std is None
        ):
            raise ValueError("Classifier is not fitted yet.")

        model_path = Path(model_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            model_path,
            k=np.array([self.k], dtype=np.int32),
            image_size=np.array([self.image_size], dtype=np.int32),
            train_features=self.train_features.astype(np.float32),
            train_labels=self.train_labels.astype(np.int32),
            class_names=np.asarray(self.class_names),
            feature_mean=self.feature_mean.astype(np.float32),
            feature_std=self.feature_std.astype(np.float32),
        )

    @classmethod
    def load(cls, model_path: str | Path) -> "NumpyKNNClassifier":
        model_path = Path(model_path)
        data = np.load(model_path, allow_pickle=False)

        classifier = cls(k=int(data["k"][0]))
        classifier.image_size = int(data["image_size"][0])
        classifier.train_features = data["train_features"].astype(np.float32)
        classifier.train_labels = data["train_labels"].astype(np.int32)
        classifier.class_names = data["class_names"].astype(str).tolist()
        classifier.feature_mean = data["feature_mean"].astype(np.float32)
        classifier.feature_std = data["feature_std"].astype(np.float32)
        return classifier
