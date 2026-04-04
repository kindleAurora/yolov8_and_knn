from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import cv2
import numpy as np

from knn_utils import NumpyKNNClassifier, extract_hog_feature, imread_unicode


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ULTRALYTICS_ROOT = PROJECT_ROOT / "code" / "yolov8" / "ultralytics"
YOLO_CONFIG_DIR = PROJECT_ROOT / "code" / "yolov8" / "yolo_config"

os.environ.setdefault("YOLO_CONFIG_DIR", str(YOLO_CONFIG_DIR))
if str(ULTRALYTICS_ROOT) not in sys.path:
    sys.path.insert(0, str(ULTRALYTICS_ROOT))

from ultralytics import YOLO  # noqa: E402


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}


def parse_args() -> argparse.Namespace:
    default_yolo_model = PROJECT_ROOT / "runs" / "detect" / "cow_120_on_basecommon" / "weights" / "best.pt"
    default_knn_model = PROJECT_ROOT / "code" / "knn" / "knn_behavior_model.npz"
    default_output = PROJECT_ROOT / "code" / "knn" / "outputs"
    default_picture = r"C:\Users\Admin\Desktop\毕设\all_datasets\cowDataset\images\train\000000114246.jpg"
    parser = argparse.ArgumentParser(description="Run cow detection with YOLO, then classify each crop using KNN.")
    parser.add_argument("--source", type=Path, default=default_picture,help="Input image or video path.")
    parser.add_argument("--yolo-model", type=Path, default=default_yolo_model, help="YOLO detection model path.")
    parser.add_argument("--knn-model", type=Path, default=default_knn_model, help="Saved KNN model path.")
    parser.add_argument("--output-dir", type=Path, default=default_output, help="Directory for annotated outputs.")
    parser.add_argument("--conf", type=float, default=0.25, help="YOLO confidence threshold.")
    parser.add_argument("--iou", type=float, default=0.45, help="YOLO IoU threshold.")
    parser.add_argument("--k", type=int, default=None, help="Override saved KNN k value if needed.")
    parser.add_argument("--fps", type=float, default=25.0, help="Fallback FPS when saving video.")
    return parser.parse_args()


def clamp_box(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> tuple[int, int, int, int]:
    x1 = max(0, min(int(round(x1)), width - 1))
    y1 = max(0, min(int(round(y1)), height - 1))
    x2 = max(0, min(int(round(x2)), width - 1))
    y2 = max(0, min(int(round(y2)), height - 1))
    return x1, y1, x2, y2


def annotate_frame(frame: np.ndarray, result, classifier: NumpyKNNClassifier) -> np.ndarray:
    annotated = frame.copy()
    height, width = annotated.shape[:2]

    if result.boxes is None:
        return annotated

    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        x1, y1, x2, y2 = clamp_box(x1, y1, x2, y2, width, height)

        if x2 <= x1 or y2 <= y1:
            continue

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            continue

        feature = extract_hog_feature(crop, image_size=classifier.image_size)
        prediction = classifier.predict(feature)

        detection_conf = float(box.conf[0]) if box.conf is not None else 0.0
        label = f"{prediction.label_name} | knn={prediction.confidence:.2f} | yolo={detection_conf:.2f}"

        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 215, 255), 2)
        cv2.rectangle(annotated, (x1, max(0, y1 - 28)), (x1 + 260, y1), (0, 215, 255), -1)
        cv2.putText(
            annotated,
            label,
            (x1 + 4, max(18, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (20, 20, 20),
            2,
            cv2.LINE_AA,
        )

    return annotated


def process_image(source: Path, model: YOLO, classifier: NumpyKNNClassifier, output_path: Path, conf: float, iou: float) -> None:
    frame = imread_unicode(source)
    results = model.predict(source=frame, conf=conf, iou=iou, verbose=False)
    annotated = annotate_frame(frame, results[0], classifier)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(output_path.suffix or ".jpg", annotated)
    if not success:
        raise ValueError(f"Failed to encode output image: {output_path}")
    encoded.tofile(str(output_path))
    print(f"Annotated image saved to: {output_path}")


def process_video(
    source: Path,
    model: YOLO,
    classifier: NumpyKNNClassifier,
    output_path: Path,
    conf: float,
    iou: float,
    fallback_fps: float,
) -> None:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"Failed to open video: {source}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    if not fps or np.isnan(fps) or fps <= 1:
        fps = fallback_fps
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise ValueError(f"Failed to create output video: {output_path}")

    try:
        for result in model.predict(source=str(source), conf=conf, iou=iou, stream=True, verbose=False):
            frame = result.orig_img
            annotated = annotate_frame(frame, result, classifier)
            writer.write(annotated)
    finally:
        writer.release()

    print(f"Annotated video saved to: {output_path}")


def main() -> None:
    args = parse_args()

    if not args.source.exists():
        raise FileNotFoundError(f"Source not found: {args.source}")
    if not args.yolo_model.exists():
        raise FileNotFoundError(f"YOLO model not found: {args.yolo_model}")
    if not args.knn_model.exists():
        raise FileNotFoundError(f"KNN model not found: {args.knn_model}")

    classifier = NumpyKNNClassifier.load(args.knn_model)
    if args.k is not None:
        classifier.k = args.k

    model = YOLO(str(args.yolo_model))
    args.output_dir.mkdir(parents=True, exist_ok=True)

    source_suffix = args.source.suffix.lower()
    output_name = f"{args.source.stem}_yolo_knn{args.source.suffix}"
    output_path = args.output_dir / output_name

    if source_suffix in IMAGE_SUFFIXES:
        process_image(args.source, model, classifier, output_path, conf=args.conf, iou=args.iou)
    elif source_suffix in VIDEO_SUFFIXES:
        process_video(
            args.source,
            model,
            classifier,
            output_path,
            conf=args.conf,
            iou=args.iou,
            fallback_fps=args.fps,
        )
    else:
        raise ValueError(f"Unsupported source type: {args.source}")


if __name__ == "__main__":
    main()
