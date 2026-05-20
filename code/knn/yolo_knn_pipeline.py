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
PROGRESS_BAR_WIDTH = 30


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
    parser.add_argument(
        "--no-motion",
        action="store_true",
        help="Disable motion-based label refinement and run pure YOLO + KNN classification.",
    )
    parser.add_argument("--box-thickness", type=int, default=4, help="Bounding box line thickness in pixels.")
    parser.add_argument("--label-font-scale", type=float, default=0.9, help="OpenCV font scale for labels.")
    parser.add_argument("--label-thickness", type=int, default=2, help="Label text thickness in pixels.")
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


def print_video_progress(frame_index: int, total_frames: int) -> None:
    if total_frames > 0:
        percent = min(frame_index / total_frames, 1.0)
        filled_width = int(PROGRESS_BAR_WIDTH * percent)
        bar = "#" * filled_width + "-" * (PROGRESS_BAR_WIDTH - filled_width)
        message = f"\rProcessing video: [{bar}] {percent * 100:6.2f}% ({frame_index}/{total_frames})"
    else:
        message = f"\rProcessing video: {frame_index} frames"

    print(message, end="", flush=True)


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


def wrap_label_parts(
    label_parts: list[str],
    max_width: int,
    font_face: int,
    font_scale: float,
    thickness: int,
) -> list[str]:
    lines: list[str] = []
    current = ""
    for part in label_parts:
        candidate = part if not current else f"{current} | {part}"
        text_width = cv2.getTextSize(candidate, font_face, font_scale, thickness)[0][0]
        if not current or text_width <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = part

    if current:
        lines.append(current)
    return lines


def annotate_frame(
    frame: np.ndarray,
    result,
    classifier: NumpyKNNClassifier,
    frame_index: int = 0,
    track_states: dict[int, TrackState] | None = None,
    motion_window: int = 6,
    motion_low_threshold: float = 0.015,
    motion_threshold: float = 0.03,
    box_thickness: int = 4,
    label_font_scale: float = 0.9,
    label_thickness: int = 2,
) -> np.ndarray:
    annotated = frame.copy()
    height, width = annotated.shape[:2]
    font_face = cv2.FONT_HERSHEY_SIMPLEX
    box_thickness = max(1, box_thickness)
    label_font_scale = max(0.1, label_font_scale)
    label_thickness = max(1, label_thickness)
    label_padding = max(8, int(round(label_font_scale * 10)))
    line_gap = max(5, int(round(label_font_scale * 6)))

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

        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 215, 255), box_thickness)

        max_text_width = max(120, width - x1 - label_padding * 2 - 1)
        label_lines = wrap_label_parts(
            label_parts=label_parts,
            max_width=max_text_width,
            font_face=font_face,
            font_scale=label_font_scale,
            thickness=label_thickness,
        )
        text_metrics = [
            cv2.getTextSize(line, font_face, label_font_scale, label_thickness)
            for line in label_lines
        ]
        text_width = max((size[0][0] for size in text_metrics), default=0)
        text_height = sum(size[0][1] + size[1] for size in text_metrics)
        label_width = min(width - x1 - 1, text_width + label_padding * 2)
        label_height = min(
            height,
            text_height + label_padding * 2 + line_gap * max(0, len(label_lines) - 1),
        )
        label_top = max(0, y1 - label_height)
        label_bottom = min(height - 1, label_top + label_height)
        cv2.rectangle(annotated, (x1, label_top), (x1 + label_width, label_bottom), (0, 215, 255), -1)

        text_y = label_top + label_padding
        for line, (size, baseline) in zip(label_lines, text_metrics):
            text_y += size[1]
            cv2.putText(
                annotated,
                line,
                (x1 + label_padding, text_y),
                font_face,
                label_font_scale,
                (20, 20, 20),
                label_thickness,
                cv2.LINE_AA,
            )
            text_y += baseline + line_gap

    return annotated


def process_image(
    source: Path,
    model: YOLO,
    classifier: NumpyKNNClassifier,
    output_path: Path,
    conf: float,
    iou: float,
    box_thickness: int,
    label_font_scale: float,
    label_thickness: int,
) -> None:
    frame = imread_unicode(source)
    results = model.predict(source=frame, conf=conf, iou=iou, verbose=False)
    annotated = annotate_frame(
        frame,
        results[0],
        classifier,
        box_thickness=box_thickness,
        label_font_scale=label_font_scale,
        label_thickness=label_thickness,
    )

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
    use_motion: bool,
    box_thickness: int,
    label_font_scale: float,
    label_thickness: int,
) -> None:
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError(f"Failed to open video: {source}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    if not fps or np.isnan(fps) or fps <= 1:
        fps = fallback_fps
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
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
    result_stream = (
        model.track(source=str(source), conf=conf, iou=iou, stream=True, persist=True, verbose=False)
        if use_motion
        else model.predict(source=str(source), conf=conf, iou=iou, stream=True, verbose=False)
    )

    try:
        for frame_index, result in enumerate(result_stream, start=1):
            if use_motion:
                prune_track_states(track_states, frame_index=frame_index, track_max_age=track_max_age)
            frame = result.orig_img
            annotated = annotate_frame(
                frame=frame,
                result=result,
                classifier=classifier,
                frame_index=frame_index,
                track_states=track_states if use_motion else None,
                motion_window=motion_window,
                motion_low_threshold=motion_low_threshold,
                motion_threshold=motion_threshold,
                box_thickness=box_thickness,
                label_font_scale=label_font_scale,
                label_thickness=label_thickness,
            )
            writer.write(annotated)
            print_video_progress(frame_index, total_frames)
    finally:
        writer.release()

    print()
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
    motion_suffix = "_no_motion" if source_suffix in VIDEO_SUFFIXES and args.no_motion else ""
    output_name = f"{args.source.stem}_yolo_knn{motion_suffix}{args.source.suffix}"
    output_path = args.output_dir / output_name

    if source_suffix in IMAGE_SUFFIXES:
        process_image(
            args.source,
            model,
            classifier,
            output_path,
            conf=args.conf,
            iou=args.iou,
            box_thickness=args.box_thickness,
            label_font_scale=args.label_font_scale,
            label_thickness=args.label_thickness,
        )
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
            use_motion=not args.no_motion,
            box_thickness=args.box_thickness,
            label_font_scale=args.label_font_scale,
            label_thickness=args.label_thickness,
        )
    else:
        raise ValueError(f"Unsupported source type: {args.source}")


if __name__ == "__main__":
    main()
