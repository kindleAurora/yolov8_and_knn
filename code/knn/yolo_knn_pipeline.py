from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass, field
import os
from pathlib import Path
import sys

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


@dataclass
class TrackState:
    centers: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=6))
    last_seen_frame: int = 0


def parse_args() -> argparse.Namespace:
    default_yolo_model = PROJECT_ROOT / "runs" / "detect" / "cow_120_on_basecommon" / "weights" / "best.pt"
    default_knn_model = PROJECT_ROOT / "code" / "knn" / "knn_behavior_model.npz"
    default_output = PROJECT_ROOT / "code" / "knn" / "outputs"
    default_picture = r"C:\Users\Admin\Desktop\毕设\all_datasets\cow_video\一群奶牛在牧场草地上吃草.mp4"

    parser = argparse.ArgumentParser(description="Run cow detection with YOLO, then classify each crop using KNN.")
    parser.add_argument("--source", type=Path, default=default_picture, help="Input image or video path.")
    parser.add_argument("--yolo-model", type=Path, default=default_yolo_model, help="YOLO detection model path.")
    parser.add_argument("--knn-model", type=Path, default=default_knn_model, help="Saved KNN model path.")
    parser.add_argument("--output-dir", type=Path, default=default_output, help="Directory for annotated outputs.")
    parser.add_argument("--conf", type=float, default=0.25, help="YOLO confidence threshold.")
    parser.add_argument("--iou", type=float, default=0.45, help="YOLO IoU threshold.")
    parser.add_argument("--k", type=int, default=None, help="Override saved KNN k value if needed.")
    parser.add_argument("--fps", type=float, default=25.0, help="Fallback FPS when saving video.")
    parser.add_argument(
        "--motion-window",
        type=int,
        default=6,
        help="Number of recent tracked centers used to estimate movement.",
    )
    parser.add_argument(
        "--motion-low-threshold",
        type=float,
        default=0.005,
        help="Low movement threshold, normalized by box size, below which lying may be kept.",
    )
    parser.add_argument(
        "--motion-threshold",
        type=float,
        default=0.01,
        help="High movement threshold, normalized by box size, above which walking is forced.",
    )
    parser.add_argument(
        "--track-max-age",
        type=int,
        default=10,
        help="How many frames to keep an unseen track before forgetting its movement history.",
    )
    return parser.parse_args()


def clamp_box(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> tuple[int, int, int, int]:
    x1 = max(0, min(int(round(x1)), width - 1))
    y1 = max(0, min(int(round(y1)), height - 1))
    x2 = max(0, min(int(round(x2)), width - 1))
    y2 = max(0, min(int(round(y2)), height - 1))
    return x1, y1, x2, y2


def get_track_id(box) -> int | None:
    if getattr(box, "id", None) is None:
        return None

    raw_value = box.id[0]
    if hasattr(raw_value, "item"):
        raw_value = raw_value.item()
    return int(raw_value)


def get_box_center(x1: int, y1: int, x2: int, y2: int) -> tuple[float, float]:
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def update_track_state(
    track_states: dict[int, TrackState],
    track_id: int,
    center: tuple[float, float],
    frame_index: int,
    motion_window: int,
) -> TrackState:
    state = track_states.get(track_id)
    if state is None:
        state = TrackState(centers=deque(maxlen=motion_window), last_seen_frame=frame_index)
        track_states[track_id] = state

    if state.centers.maxlen != motion_window:
        state.centers = deque(state.centers, maxlen=motion_window)

    state.centers.append(center)
    state.last_seen_frame = frame_index
    return state


def prune_track_states(track_states: dict[int, TrackState], frame_index: int, track_max_age: int) -> None:
    stale_track_ids = [
        track_id
        for track_id, state in track_states.items()
        if frame_index - state.last_seen_frame > track_max_age
    ]
    for track_id in stale_track_ids:
        del track_states[track_id]


def compute_motion_score(state: TrackState, box_width: int, box_height: int) -> float:
    if len(state.centers) < 2:
        return 0.0

    centers = list(state.centers)
    step_distances = [
        float(np.hypot(curr_x - prev_x, curr_y - prev_y))
        for (prev_x, prev_y), (curr_x, curr_y) in zip(centers[:-1], centers[1:])
    ]
    average_step = float(np.mean(step_distances))
    reference_scale = max(float(box_width), float(box_height), 1.0)
    return average_step / reference_scale


def refine_behavior_label(
    knn_label: str,
    track_state: TrackState | None,
    box_width: int,
    box_height: int,
    motion_window: int,
    motion_low_threshold: float,
    motion_high_threshold: float,
) -> tuple[str, float | None, str]:
    if track_state is None or len(track_state.centers) < motion_window:
        return knn_label, None, "history-short"

    motion_score = compute_motion_score(track_state, box_width=box_width, box_height=box_height)
    if motion_score >= motion_high_threshold:
        return "walking", motion_score, "motion-high"

    if motion_score <= motion_low_threshold:
        if knn_label == "lying":
            return "lying", motion_score, "motion-low-lying"
        if knn_label == "walking":
            return "standing", motion_score, "motion-low-walking-to-standing"
        return "standing", motion_score, "motion-low-standing"

    return knn_label, motion_score, "motion-middle-knn"


def annotate_frame(
    frame: np.ndarray,
    result,
    classifier: NumpyKNNClassifier,
    frame_index: int = 0,
    track_states: dict[int, TrackState] | None = None,
    motion_window: int = 6,
    motion_low_threshold: float = 0.015,
    motion_threshold: float = 0.03,
) -> np.ndarray:
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

        box_width = x2 - x1
        box_height = y2 - y1
        track_id = get_track_id(box)
        use_motion_rule = track_states is not None and track_id is not None
        track_state = None
        if use_motion_rule:
            center = get_box_center(x1, y1, x2, y2)
            track_state = update_track_state(
                track_states=track_states,
                track_id=track_id,
                center=center,
                frame_index=frame_index,
                motion_window=motion_window,
            )

        if use_motion_rule:
            final_label, motion_score, motion_reason = refine_behavior_label(
                knn_label=prediction.label_name,
                track_state=track_state,
                box_width=box_width,
                box_height=box_height,
                motion_window=motion_window,
                motion_low_threshold=motion_low_threshold,
                motion_high_threshold=motion_threshold,
            )
        else:
            final_label = prediction.label_name
            motion_score = None
            motion_reason = "knn-only"

        detection_conf = float(box.conf[0]) if box.conf is not None else 0.0

        label_parts = [final_label]
        if use_motion_rule and final_label != prediction.label_name:
            label_parts.append(f"knn={prediction.label_name}")
        if use_motion_rule and track_id is not None:
            label_parts.append(f"id={track_id}")
        if use_motion_rule and motion_score is not None:
            label_parts.append(f"move={motion_score:.3f}")
        label_parts.append(f"knn={prediction.confidence:.2f}")
        label_parts.append(f"yolo={detection_conf:.2f}")
        if use_motion_rule:
            label_parts.append(f"rule={motion_reason}")
        label = " | ".join(label_parts)

        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 215, 255), 2)
        text_width = min(width - x1, max(280, 9 * len(label)))
        cv2.rectangle(annotated, (x1, max(0, y1 - 28)), (x1 + text_width, y1), (0, 215, 255), -1)
        cv2.putText(
            annotated,
            label,
            (x1 + 4, max(18, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
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
    motion_window: int,
    motion_low_threshold: float,
    motion_threshold: float,
    track_max_age: int,
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

    track_states: dict[int, TrackState] = {}

    try:
        for frame_index, result in enumerate(
            model.track(source=str(source), conf=conf, iou=iou, stream=True, persist=True, verbose=False),
            start=1,
        ):
            prune_track_states(track_states, frame_index=frame_index, track_max_age=track_max_age)
            frame = result.orig_img
            annotated = annotate_frame(
                frame=frame,
                result=result,
                classifier=classifier,
                frame_index=frame_index,
                track_states=track_states,
                motion_window=motion_window,
                motion_low_threshold=motion_low_threshold,
                motion_threshold=motion_threshold,
            )
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
    if args.motion_low_threshold > args.motion_threshold:
        raise ValueError("--motion-low-threshold must be less than or equal to --motion-threshold.")

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
            motion_window=args.motion_window,
            motion_low_threshold=args.motion_low_threshold,
            motion_threshold=args.motion_threshold,
            track_max_age=args.track_max_age,
        )
    else:
        raise ValueError(f"Unsupported source type: {args.source}")


if __name__ == "__main__":
    main()
