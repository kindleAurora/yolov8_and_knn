from __future__ import annotations

import math
import mimetypes
import statistics
import sys
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

from app.core.config import settings
from app.schemas.inference import (
    BehaviorEventCandidate,
    InferenceMetaResponse,
    InferenceRequest,
    InferenceResponse,
    YoloModelOption,
)

from .yolo_knn_stub import run_stub_inference

SUPPORTED_SOURCE_TYPES = ["image", "video", "stream", "edge-report"]
SUPPORTED_INFERENCE_MODES = ["yolo-knn", "yolo-only"]
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}
PREVIEW_MAX_WIDTH = 1440
COW_CLASS_ALIASES = {"cow", "cattle", "bovine", "calf", "bull", "ox", "牛", "奶牛", "黄牛", "肉牛"}
BEHAVIOR_LABEL_MAP = {
    "lying": "躺卧",
    "lie": "躺卧",
    "rest": "休息",
    "resting": "休息",
    "standing": "站立",
    "stand": "站立",
    "walking": "行走",
    "walk": "行走",
    "drinking": "饮水",
    "drink": "饮水",
    "feeding": "采食",
    "feed": "采食",
    "eating": "采食",
    "eat": "采食",
    "躺卧": "躺卧",
    "休息": "休息",
    "站立": "站立",
    "行走": "行走",
    "饮水": "饮水",
    "采食": "采食",
}
ZONE_TYPE_MAP = {
    "water": "water",
    "drink": "water",
    "drinking": "water",
    "feeding": "feeding",
    "feed": "feeding",
    "eating": "feeding",
    "eat": "feeding",
    "rest": "rest",
    "resting": "rest",
}


@dataclass
class TrackState:
    centers: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=6))
    last_seen_frame: int = 0


@dataclass
class TrackObservation:
    labels: list[str] = field(default_factory=list)
    confidences: list[float] = field(default_factory=list)
    first_offset_seconds: float | None = None
    total_observed_seconds: float = 0.0
    zone_dwell_seconds: dict[str, float] = field(default_factory=dict)
    zone_hit_counts: Counter[str] = field(default_factory=Counter)
    zone_types: dict[str, str] = field(default_factory=dict)
    zone_relations: dict[str, Counter[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class ZoneCandidate:
    name: str
    zone_type: str
    shape_type: str
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class ZoneMatch:
    name: str
    zone_type: str
    relation: str
    distance: float


def _normalize_label(value: str) -> str:
    return value.strip().lower().replace("_", " ").replace("-", " ")


def _translate_behavior_label(raw_label: str) -> str | None:
    normalized = _normalize_label(raw_label)
    if normalized in BEHAVIOR_LABEL_MAP:
        return BEHAVIOR_LABEL_MAP[normalized]

    if "饮水" in raw_label or "drink" in normalized:
        return "饮水"
    if "采食" in raw_label or "feed" in normalized or "eat" in normalized:
        return "采食"
    if "躺" in raw_label or "lying" in normalized or "rest" in normalized:
        return "躺卧" if "lying" in normalized or "躺" in raw_label else "休息"
    if "站" in raw_label or "stand" in normalized:
        return "站立"
    if "走" in raw_label or "walk" in normalized:
        return "行走"
    return None


def _is_cow_label(raw_label: str) -> bool:
    normalized = _normalize_label(raw_label)
    return any(alias in normalized or alias in raw_label for alias in COW_CLASS_ALIASES)


def _normalize_zone_type(raw_value: str) -> str | None:
    normalized = _normalize_label(raw_value)
    if normalized in ZONE_TYPE_MAP:
        return ZONE_TYPE_MAP[normalized]

    if "water" in normalized or "drink" in normalized:
        return "water"
    if "feed" in normalized or "eat" in normalized:
        return "feeding"
    if "rest" in normalized:
        return "rest"
    return None


def _canonical_behavior_key(raw_label: str) -> str:
    normalized = _normalize_label(raw_label)
    mapping = {
        "lying": "lying",
        "lie": "lying",
        "rest": "resting",
        "resting": "resting",
        "standing": "standing",
        "stand": "standing",
        "walking": "walking",
        "walk": "walking",
        "drinking": "drinking",
        "drink": "drinking",
        "feeding": "feeding",
        "feed": "feeding",
        "eating": "feeding",
        "eat": "feeding",
    }
    for behavior_key in ("lying", "resting", "standing", "walking", "drinking", "feeding"):
        translated_label = _translate_behavior_label(behavior_key)
        if translated_label:
            mapping[translated_label] = behavior_key
    return mapping.get(normalized, mapping.get(raw_label, normalized))


def _coerce_zone_points(raw_points: object) -> tuple[tuple[float, float], ...]:
    if not isinstance(raw_points, list):
        return ()

    parsed_points: list[tuple[float, float]] = []
    for item in raw_points:
        if not isinstance(item, dict):
            continue

        x = item.get("x")
        y = item.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            continue

        parsed_points.append(
            (
                max(0.0, min(float(x), 1.0)),
                max(0.0, min(float(y), 1.0)),
            )
        )

    return tuple(parsed_points)


def _extract_zone_candidates(payload: InferenceRequest) -> list[ZoneCandidate]:
    raw_candidates = payload.metadata.get("zone_candidates")
    if not isinstance(raw_candidates, list):
        return []

    zone_candidates: list[ZoneCandidate] = []
    for item in raw_candidates:
        if not isinstance(item, dict):
            continue

        zone_name = item.get("name")
        raw_zone_type = item.get("zone_type")
        if not isinstance(zone_name, str) or not zone_name:
            continue
        if not isinstance(raw_zone_type, str):
            continue

        zone_type = _normalize_zone_type(raw_zone_type)
        if zone_type is None:
            continue

        points = _coerce_zone_points(item.get("points"))
        if len(points) < 3:
            continue

        shape_type = item.get("shape_type")
        zone_candidates.append(
            ZoneCandidate(
                name=zone_name,
                zone_type=zone_type,
                shape_type=str(shape_type) if isinstance(shape_type, str) else "polygon",
                points=points,
            )
        )

    return zone_candidates


def _point_in_polygon(point: tuple[float, float], polygon: tuple[tuple[float, float], ...]) -> bool:
    x, y = point
    inside = False
    point_count = len(polygon)
    for index in range(point_count):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % point_count]
        intersects = ((y1 > y) != (y2 > y)) and (
            x < ((x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9)) + x1
        )
        if intersects:
            inside = not inside
    return inside


def _point_to_segment_distance(
    point: tuple[float, float],
    segment_start: tuple[float, float],
    segment_end: tuple[float, float],
) -> float:
    px, py = point
    ax, ay = segment_start
    bx, by = segment_end
    dx = bx - ax
    dy = by - ay
    segment_length_squared = dx * dx + dy * dy
    if segment_length_squared <= 1e-9:
        return math.hypot(px - ax, py - ay)

    projection = ((px - ax) * dx + (py - ay) * dy) / segment_length_squared
    projection = max(0.0, min(1.0, projection))
    closest_x = ax + projection * dx
    closest_y = ay + projection * dy
    return math.hypot(px - closest_x, py - closest_y)


def _distance_to_polygon(point: tuple[float, float], polygon: tuple[tuple[float, float], ...]) -> float:
    return min(
        _point_to_segment_distance(point, polygon[index], polygon[(index + 1) % len(polygon)])
        for index in range(len(polygon))
    )


def _polygon_centroid(polygon: tuple[tuple[float, float], ...]) -> tuple[float, float]:
    return (
        sum(point[0] for point in polygon) / max(len(polygon), 1),
        sum(point[1] for point in polygon) / max(len(polygon), 1),
    )


def _match_detection_zone(
    zone_candidates: list[ZoneCandidate],
    *,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    frame_width: int,
    frame_height: int,
) -> ZoneMatch | None:
    if not zone_candidates or frame_width <= 0 or frame_height <= 0:
        return None

    anchor_point = (
        max(0.0, min(((x1 + x2) / 2.0) / frame_width, 1.0)),
        max(0.0, min(y2 / frame_height, 1.0)),
    )
    inside_matches: list[tuple[float, ZoneCandidate]] = []
    near_matches: list[tuple[float, ZoneCandidate]] = []

    for zone in zone_candidates:
        if zone.shape_type != "polygon":
            continue

        if _point_in_polygon(anchor_point, zone.points):
            centroid_x, centroid_y = _polygon_centroid(zone.points)
            inside_matches.append((math.hypot(anchor_point[0] - centroid_x, anchor_point[1] - centroid_y), zone))
            continue

        distance = _distance_to_polygon(anchor_point, zone.points)
        if distance <= settings.zone_proximity_threshold:
            near_matches.append((distance, zone))

    if inside_matches:
        distance, zone = min(inside_matches, key=lambda item: item[0])
        return ZoneMatch(name=zone.name, zone_type=zone.zone_type, relation="inside", distance=distance)

    if near_matches:
        distance, zone = min(near_matches, key=lambda item: item[0])
        return ZoneMatch(name=zone.name, zone_type=zone.zone_type, relation="near", distance=distance)

    return None


def _build_zone_logic_metadata() -> dict[str, object]:
    return {
        "anchor_point": "bbox-bottom-center",
        "match_order": ["inside-zone", "near-zone"],
        "near_threshold": settings.zone_proximity_threshold,
        "behavior_rules": {
            "feeding": {
                "zone_type": "feeding",
                "min_dwell_seconds": settings.zone_feeding_min_dwell_seconds,
                "min_share": settings.zone_behavior_min_ratio,
            },
            "drinking": {
                "zone_type": "water",
                "min_dwell_seconds": settings.zone_drinking_min_dwell_seconds,
                "min_share": settings.zone_behavior_min_ratio,
            },
            "resting": {
                "zone_type": "rest",
                "min_dwell_seconds": settings.zone_resting_min_dwell_seconds,
                "min_share": settings.zone_behavior_min_ratio,
                "fallback_to_lying": True,
            },
        },
    }


def _build_events_from_overrides(payload: InferenceRequest) -> list[BehaviorEventCandidate]:
    overrides = payload.metadata.get("behavior_overrides")
    if not isinstance(overrides, list):
        return []

    behavior_events: list[BehaviorEventCandidate] = []
    for item in overrides:
        if not isinstance(item, dict):
            continue

        behavior_type = item.get("behavior_type")
        if not isinstance(behavior_type, str) or not behavior_type:
            continue

        offset_seconds = item.get("event_offset_seconds", 0)
        offset_value = float(offset_seconds) if isinstance(offset_seconds, (int, float)) else 0.0
        event_time = payload.occurred_at + timedelta(seconds=offset_value)

        cow_count = item.get("cow_count", 1)
        confidence = item.get("confidence", 0.8)
        zone_name = item.get("zone_name")
        notes = item.get("notes")

        behavior_events.append(
            BehaviorEventCandidate(
                device_code=payload.device_code or "unknown-device",
                event_time=event_time,
                behavior_type=str(behavior_type),
                cow_count=max(0, int(cow_count)) if isinstance(cow_count, (int, float)) else 0,
                confidence=float(confidence) if isinstance(confidence, (int, float)) else 0.0,
                zone_name=zone_name if isinstance(zone_name, str) else None,
                notes=notes if isinstance(notes, str) else None,
            )
        )

    return behavior_events


def _discover_model_paths() -> list[Path]:
    search_roots = [
        settings.workspace_root / "runs",
        settings.workspace_root / "code" / "yolov8",
    ]

    discovered_paths: list[Path] = []
    seen_paths: set[str] = set()

    for root in search_roots:
        if not root.exists():
            continue

        for candidate in root.rglob("*.pt"):
            if any(part in {"__pycache__", ".git", "node_modules"} for part in candidate.parts):
                continue

            resolved = str(candidate.resolve())
            if resolved in seen_paths:
                continue

            seen_paths.add(resolved)
            discovered_paths.append(candidate)

    default_path = settings.yolo_model_path
    if default_path.exists():
        resolved = str(default_path.resolve())
        if resolved not in seen_paths:
            discovered_paths.insert(0, default_path)

    def sort_key(path: Path) -> tuple[int, int, str]:
        relative = _to_model_key(path)
        return (
            0 if path.resolve() == settings.yolo_model_path.resolve() else 1,
            0 if path.name == "best.pt" else 1,
            relative,
        )

    return sorted(discovered_paths, key=sort_key)


def _to_model_key(path: Path) -> str:
    try:
        return path.resolve().relative_to(settings.workspace_root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


@lru_cache(maxsize=1)
def get_inference_meta() -> InferenceMetaResponse:
    available_models = [
        YoloModelOption(
            key=_to_model_key(model_path),
            label=_to_model_key(model_path),
            path=str(model_path.resolve()),
            is_default=model_path.resolve() == settings.yolo_model_path.resolve(),
        )
        for model_path in _discover_model_paths()
    ]

    default_key = None
    for item in available_models:
        if item.is_default:
            default_key = item.key
            break

    return InferenceMetaResponse(
        service="cow-monitor-inference",
        service_mode=settings.pipeline_mode,
        supported_sources=SUPPORTED_SOURCE_TYPES,
        available_inference_modes=SUPPORTED_INFERENCE_MODES,
        default_inference_mode="yolo-knn",
        default_yolo_model_key=default_key,
        default_yolo_confidence=settings.yolo_confidence,
        default_yolo_iou=settings.yolo_iou,
        default_knn_confidence_threshold=settings.knn_confidence_threshold,
        available_yolo_models=available_models,
        knn_model_loaded=settings.knn_model_path.exists(),
    )


def _resolve_model_path(model_key: str | None) -> Path:
    if not model_key:
        return settings.yolo_model_path

    for model_path in _discover_model_paths():
        if _to_model_key(model_path) == model_key:
            return model_path

    candidate = settings.workspace_root / model_key
    if candidate.exists():
        return candidate

    raise RuntimeError(f"未找到指定的 YOLO 模型：{model_key}")


def _load_runtime_dependencies() -> tuple[Any, Any, Any]:
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
        from ultralytics import YOLO  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - environment branch
        raise RuntimeError(
            "真实推理依赖尚未安装，请先安装 numpy、opencv-python-headless、ultralytics 等依赖。"
        ) from exc

    return cv2, np, YOLO


@lru_cache(maxsize=1)
def _load_torch_dependency() -> Any | None:
    try:
        import torch  # type: ignore[import-not-found]
    except Exception:
        return None
    return torch


@lru_cache(maxsize=1)
def _resolve_compute_device() -> str:
    preferred_device = settings.inference_device.strip().lower()
    if preferred_device and preferred_device != "auto":
        return settings.inference_device

    torch = _load_torch_dependency()
    if torch is not None and torch.cuda.is_available():
        return "cuda:0"

    return "cpu"


def _resolve_numeric_setting(
    raw_value: object,
    *,
    default_value: float,
    min_value: float = 0.0,
    max_value: float = 1.0,
) -> float:
    candidate: float | None = None
    if isinstance(raw_value, bool):
        candidate = None
    elif isinstance(raw_value, (int, float)):
        candidate = float(raw_value)
    elif isinstance(raw_value, str):
        try:
            candidate = float(raw_value.strip())
        except ValueError:
            candidate = None

    if candidate is None:
        return default_value

    return max(min(candidate, max_value), min_value)


def _resolve_request_budget(
    payload: InferenceRequest,
    *,
    metadata_key: str,
    default_value: int,
) -> int:
    raw_value = payload.metadata.get(metadata_key)
    if isinstance(raw_value, bool):
        return default_value
    if isinstance(raw_value, int):
        return max(raw_value, 1)
    if isinstance(raw_value, float):
        return max(int(raw_value), 1)
    return default_value


def _resolve_max_video_frames(payload: InferenceRequest) -> int:
    analysis_profile = str(payload.metadata.get("analysis_profile", "")).strip().lower()
    default_value = (
        settings.realtime_max_video_frames
        if analysis_profile == "realtime"
        else settings.max_video_frames
    )
    return _resolve_request_budget(
        payload,
        metadata_key="max_video_frames",
        default_value=default_value,
    )


def _resolve_frame_stride(payload: InferenceRequest) -> int:
    analysis_profile = str(payload.metadata.get("analysis_profile", "")).strip().lower()
    default_value = (
        settings.realtime_frame_stride
        if analysis_profile == "realtime"
        else settings.frame_stride
    )
    return _resolve_request_budget(
        payload,
        metadata_key="frame_stride",
        default_value=default_value,
    )


def _resolve_request_threshold(
    payload: InferenceRequest,
    *,
    metadata_key: str,
    default_value: float,
) -> float:
    return _resolve_numeric_setting(
        payload.metadata.get(metadata_key),
        default_value=default_value,
    )


def _resolve_yolo_confidence(payload: InferenceRequest) -> float:
    return _resolve_request_threshold(
        payload,
        metadata_key="yolo_confidence",
        default_value=settings.yolo_confidence,
    )


def _resolve_yolo_iou(payload: InferenceRequest) -> float:
    return _resolve_request_threshold(
        payload,
        metadata_key="yolo_iou",
        default_value=settings.yolo_iou,
    )


def _resolve_knn_confidence_threshold(payload: InferenceRequest) -> float:
    return _resolve_request_threshold(
        payload,
        metadata_key="knn_confidence_threshold",
        default_value=settings.knn_confidence_threshold,
    )


def _load_knn_tools() -> tuple[Any, Any, Any]:
    knn_root = settings.workspace_root / "code" / "knn"
    if not knn_root.exists():
        raise RuntimeError(f"未找到 KNN 工具目录：{knn_root}")

    if str(knn_root) not in sys.path:
        sys.path.insert(0, str(knn_root))

    try:
        from knn_utils import (  # type: ignore[import-not-found]
            NumpyKNNClassifier,
            extract_hog_feature,
            imread_unicode,
        )
    except Exception as exc:  # pragma: no cover - environment branch
        raise RuntimeError("无法加载 KNN 运行时工具，请检查 code/knn 目录与依赖是否完整。") from exc

    return NumpyKNNClassifier, extract_hog_feature, imread_unicode


@lru_cache(maxsize=8)
def _load_yolo_model(model_path: str) -> Any:
    _, _, YOLO = _load_runtime_dependencies()
    model = YOLO(model_path)
    try:
        model.to(_resolve_compute_device())
    except Exception as exc:  # pragma: no cover - environment branch
        raise RuntimeError(f"无法将 YOLO 模型切换到推理设备：{_resolve_compute_device()}") from exc
    return model


@lru_cache(maxsize=1)
def _load_knn_classifier(model_path: str) -> Any:
    NumpyKNNClassifier, _, _ = _load_knn_tools()
    return NumpyKNNClassifier.load(model_path)


def _resolve_file_path(raw_value: str) -> Path:
    normalized_value = raw_value.strip()
    if normalized_value.startswith("workspace/"):
        normalized_value = f"/{normalized_value}"

    parsed = urlparse(normalized_value)
    if parsed.scheme == "file":
        path_value = unquote(parsed.path)
        if path_value.startswith("/") and len(path_value) > 3 and path_value[2] == ":":
            path_value = path_value[1:]
        candidate = Path(path_value)
    else:
        candidate = Path(normalized_value)

    if candidate.exists():
        return candidate

    workspace_candidate = settings.workspace_root / normalized_value
    if workspace_candidate.exists():
        return workspace_candidate

    raise RuntimeError(
        "无法定位输入文件："
        f"{raw_value}。Docker 环境下请使用 /workspace/... 路径或项目根目录相对路径。"
    )


def _infer_source_type_from_uri(uri: str, fallback: str) -> str:
    parsed = urlparse(uri)
    lower_path = parsed.path.lower()

    if any(lower_path.endswith(suffix) for suffix in IMAGE_SUFFIXES):
        return "image"
    if any(lower_path.endswith(suffix) for suffix in VIDEO_SUFFIXES):
        return "video"
    if parsed.scheme in {"rtsp", "rtmp"}:
        return "stream"
    if parsed.scheme in {"http", "https"} and not lower_path:
        return "stream"
    return fallback


def _read_image_bytes(image_uri: str) -> Any:
    cv2, np, _ = _load_runtime_dependencies()
    parsed = urlparse(image_uri)
    if parsed.scheme in {"http", "https"}:
        with urlopen(image_uri, timeout=10) as response:
            image_bytes = response.read()
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"无法读取远程图片：{image_uri}")
        return image

    _, _, imread_unicode = _load_knn_tools()
    return imread_unicode(_resolve_file_path(image_uri))


def _capture_preview_frame(source_ref: str | Path) -> Any:
    cv2, _, _ = _load_runtime_dependencies()
    capture = cv2.VideoCapture(str(source_ref))
    if not capture.isOpened():
        raise RuntimeError(f"无法打开媒体源：{source_ref}")

    try:
        ok, frame = capture.read()
    finally:
        capture.release()

    if not ok or frame is None:
        raise RuntimeError(f"无法从媒体源读取预览帧：{source_ref}")

    return frame


def _encode_preview_image(image: Any, *, max_width: int = PREVIEW_MAX_WIDTH) -> bytes:
    cv2, _, _ = _load_runtime_dependencies()

    if image is None or getattr(image, "size", 0) == 0:
        raise RuntimeError("预览图像为空，无法编码")

    height, width = image.shape[:2]
    if width > max_width:
        scale = max_width / float(width)
        image = cv2.resize(
            image,
            (int(width * scale), int(height * scale)),
            interpolation=cv2.INTER_AREA,
        )

    success, encoded = cv2.imencode(
        ".jpg",
        image,
        [int(cv2.IMWRITE_JPEG_QUALITY), 88],
    )
    if not success:
        raise RuntimeError("无法编码预览图像")

    return encoded.tobytes()


def _to_preview_overlay_label(label: str) -> str:
    normalized = _normalize_label(label)
    mapping = {
        "躺卧": "lying",
        "休息": "resting",
        "站立": "standing",
        "行走": "walking",
        "饮水": "drinking",
        "采食": "feeding",
        "牛只检测": "cow",
        "cow detection": "cow",
        "lying": "lying",
        "resting": "resting",
        "standing": "standing",
        "walking": "walking",
        "drinking": "drinking",
        "feeding": "feeding",
        "cow": "cow",
    }
    return mapping.get(label, mapping.get(normalized, label))


def _draw_preview_annotation(
    image: Any,
    *,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    label: str,
    confidence: float,
) -> None:
    cv2, _, _ = _load_runtime_dependencies()
    box_color = (48, 236, 252)
    label_text = f"{_to_preview_overlay_label(label)} {round(confidence * 100)}%"
    cv2.rectangle(image, (x1, y1), (x2, y2), box_color, 2)

    label_origin_y = max(y1 - 10, 24)
    (text_width, text_height), _ = cv2.getTextSize(
        label_text,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        2,
    )
    cv2.rectangle(
        image,
        (x1, label_origin_y - text_height - 10),
        (x1 + text_width + 10, label_origin_y),
        box_color,
        thickness=-1,
    )
    cv2.putText(
        image,
        label_text,
        (x1 + 5, label_origin_y - 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (8, 18, 22),
        2,
        cv2.LINE_AA,
    )


def _annotate_preview_image(
    image: Any,
    *,
    yolo_model_key: str | None = None,
    inference_mode: str = "yolo-only",
    yolo_confidence: float | None = None,
    yolo_iou: float | None = None,
    knn_confidence_threshold: float | None = None,
) -> Any:
    cv2, _, _ = _load_runtime_dependencies()
    model_path = _resolve_model_path(yolo_model_key)
    model = _load_yolo_model(str(model_path))
    classifier = None
    extract_hog_feature = None
    resolved_yolo_confidence = _resolve_numeric_setting(
        yolo_confidence,
        default_value=settings.yolo_confidence,
    )
    resolved_yolo_iou = _resolve_numeric_setting(
        yolo_iou,
        default_value=settings.yolo_iou,
    )
    resolved_knn_confidence_threshold = _resolve_numeric_setting(
        knn_confidence_threshold,
        default_value=settings.knn_confidence_threshold,
    )

    if inference_mode == "yolo-knn" and settings.knn_model_path.exists():
        classifier = _load_knn_classifier(str(settings.knn_model_path))
        _, extract_hog_feature, _ = _load_knn_tools()

    results = model.predict(
        source=image,
        conf=resolved_yolo_confidence,
        iou=resolved_yolo_iou,
        verbose=False,
    )
    result = results[0]
    annotated = image.copy()
    boxes = getattr(result, "boxes", None)
    available_names = getattr(result, "names", {}) or {}
    if boxes is not None:
        for box in boxes:
            class_name = _extract_class_name(result, box)
            if not _should_use_detection_box(class_name, available_names):
                continue

            x1, y1, x2, y2 = _clamp_box(
                *box.xyxy[0].tolist(),
                image.shape[1],
                image.shape[0],
            )
            if x2 <= x1 or y2 <= y1:
                continue

            detection_confidence = (
                float(box.conf[0]) if getattr(box, "conf", None) is not None else 0.0
            )
            final_label, classifier_confidence = _resolve_box_behavior_label(
                image=image,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                class_name=class_name,
                available_names=available_names,
                classifier=classifier,
                extract_hog_feature=extract_hog_feature,
                knn_confidence_threshold=resolved_knn_confidence_threshold,
            )

            if not final_label:
                continue

            _draw_preview_annotation(
                annotated,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                label=final_label,
                confidence=_combine_confidences(detection_confidence, classifier_confidence),
            )

    cv2.putText(
        annotated,
        f"{'YOLO+KNN' if inference_mode == 'yolo-knn' else 'YOLO'} / {_resolve_compute_device()} / {model_path.stem}",
        (18, 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.64,
        (32, 236, 252),
        2,
        cv2.LINE_AA,
    )
    return annotated


def _resolve_preview_candidate(
    *,
    source_type: str,
    source_uri: str,
    frame_uri: str | None = None,
    prefer_frame: bool = True,
) -> tuple[str, str]:
    target_uri = frame_uri if prefer_frame and frame_uri else source_uri
    target_type = _infer_source_type_from_uri(target_uri, source_type)
    return target_type, target_uri


def get_media_preview_bytes(
    *,
    source_type: str,
    source_uri: str,
    frame_uri: str | None = None,
    prefer_frame: bool = True,
    annotated: bool = False,
    yolo_model_key: str | None = None,
    inference_mode: str = "yolo-only",
    yolo_confidence: float | None = None,
    yolo_iou: float | None = None,
    knn_confidence_threshold: float | None = None,
) -> bytes:
    preview_type, preview_uri = _resolve_preview_candidate(
        source_type=source_type,
        source_uri=source_uri,
        frame_uri=frame_uri,
        prefer_frame=prefer_frame,
    )

    if preview_type == "image":
        image = _read_image_bytes(preview_uri)
    else:
        parsed = urlparse(preview_uri)
        source_ref: str | Path
        if parsed.scheme in {"http", "https", "rtsp", "rtmp"}:
            source_ref = preview_uri
        else:
            source_ref = _resolve_file_path(preview_uri)
        image = _capture_preview_frame(source_ref)

    if annotated:
        image = _annotate_preview_image(
            image,
            yolo_model_key=yolo_model_key,
            inference_mode=inference_mode,
            yolo_confidence=yolo_confidence,
            yolo_iou=yolo_iou,
            knn_confidence_threshold=knn_confidence_threshold,
        )

    return _encode_preview_image(image)


def _guess_media_type(uri: str) -> str:
    media_type, _ = mimetypes.guess_type(uri)
    return media_type or "application/octet-stream"


def read_media_payload(
    *,
    source_type: str,
    source_uri: str,
    frame_uri: str | None = None,
    prefer_frame: bool = False,
) -> tuple[bytes, str, str]:
    media_type, media_uri = _resolve_preview_candidate(
        source_type=source_type,
        source_uri=source_uri,
        frame_uri=frame_uri,
        prefer_frame=prefer_frame,
    )

    if media_type == "stream":
        raise RuntimeError("实时视频流暂不支持直接输出原始媒体文件，请使用预览接口抓帧。")

    parsed = urlparse(media_uri)
    if parsed.scheme in {"http", "https"}:
        with urlopen(media_uri, timeout=20) as response:
            payload = response.read()
            response_type = response.headers.get_content_type()
        file_name = Path(parsed.path).name or "media"
        return payload, response_type or _guess_media_type(media_uri), file_name

    file_path = _resolve_file_path(media_uri)
    return file_path.read_bytes(), _guess_media_type(file_path.name), file_path.name


def _resolve_media_source(payload: InferenceRequest) -> str | Path:
    if payload.source_type == "edge-report":
        candidate = payload.frame_uri or payload.source_uri
    elif payload.source_type == "image":
        candidate = payload.frame_uri or payload.source_uri
    else:
        candidate = payload.source_uri

    if candidate.startswith("demo://"):
        raise RuntimeError(
            "真实推理模式不支持 demo:// 地址，请改用实际视频流地址或 /workspace 下的文件路径。"
        )

    parsed = urlparse(candidate)
    if parsed.scheme in {"http", "https", "rtsp", "rtmp"}:
        return candidate

    return _resolve_file_path(candidate)


def _clamp_box(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    x1 = max(0, min(int(round(x1)), width - 1))
    y1 = max(0, min(int(round(y1)), height - 1))
    x2 = max(0, min(int(round(x2)), width - 1))
    y2 = max(0, min(int(round(y2)), height - 1))
    return x1, y1, x2, y2


def _get_track_id(box: Any) -> str | None:
    if getattr(box, "id", None) is None:
        return None

    raw_value = box.id[0]
    if hasattr(raw_value, "item"):
        raw_value = raw_value.item()
    return str(int(raw_value))


def _get_box_center(x1: int, y1: int, x2: int, y2: int) -> tuple[float, float]:
    return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


def _update_track_state(
    track_states: dict[str, TrackState],
    track_id: str,
    center: tuple[float, float],
    frame_index: int,
) -> TrackState:
    state = track_states.get(track_id)
    if state is None:
        state = TrackState(
            centers=deque(maxlen=settings.motion_window),
            last_seen_frame=frame_index,
        )
        track_states[track_id] = state

    if state.centers.maxlen != settings.motion_window:
        state.centers = deque(state.centers, maxlen=settings.motion_window)

    state.centers.append(center)
    state.last_seen_frame = frame_index
    return state


def _prune_track_states(track_states: dict[str, TrackState], frame_index: int) -> None:
    stale_ids = [
        track_id
        for track_id, state in track_states.items()
        if frame_index - state.last_seen_frame > settings.track_max_age
    ]
    for track_id in stale_ids:
        del track_states[track_id]


def _compute_motion_score(
    state: TrackState,
    box_width: int,
    box_height: int,
    np: Any,
) -> float:
    if len(state.centers) < 2:
        return 0.0

    centers = list(state.centers)
    step_distances = [
        float(np.hypot(curr_x - prev_x, curr_y - prev_y))
        for (prev_x, prev_y), (curr_x, curr_y) in zip(centers[:-1], centers[1:], strict=False)
    ]
    average_step = float(np.mean(step_distances))
    reference_scale = max(float(box_width), float(box_height), 1.0)
    return average_step / reference_scale


def _refine_behavior_label(
    knn_label: str,
    track_state: TrackState | None,
    box_width: int,
    box_height: int,
    np: Any,
) -> str:
    if track_state is None or len(track_state.centers) < settings.motion_window:
        return knn_label

    motion_score = _compute_motion_score(
        track_state,
        box_width=box_width,
        box_height=box_height,
        np=np,
    )
    if motion_score >= settings.motion_high_threshold:
        return "walking"

    if motion_score <= settings.motion_low_threshold:
        if knn_label == "lying":
            return "lying"
        if knn_label == "walking":
            return "standing"
        return "standing"

    return knn_label


def _extract_class_name(result: Any, box: Any) -> str:
    raw_names = getattr(result, "names", {}) or {}
    names = raw_names if isinstance(raw_names, dict) else dict(enumerate(raw_names))
    class_index = int(box.cls[0]) if getattr(box, "cls", None) is not None else 0
    raw_name = names.get(class_index, str(class_index))
    return str(raw_name)


def _combine_confidences(detection_confidence: float, classifier_confidence: float | None) -> float:
    if classifier_confidence is None:
        return round(float(detection_confidence), 4)
    return round((float(detection_confidence) + float(classifier_confidence)) / 2.0, 4)


def _append_track_observation(
    track_observations: dict[str, TrackObservation],
    track_id: str,
    label: str,
    confidence: float,
    offset_seconds: float,
    *,
    zone_name: str | None = None,
    zone_type: str | None = None,
    zone_relation: str | None = None,
    observation_span_seconds: float = 0.0,
) -> None:
    observation = track_observations.setdefault(track_id, TrackObservation())
    observation.labels.append(label)
    observation.confidences.append(confidence)
    if observation.first_offset_seconds is None:
        observation.first_offset_seconds = offset_seconds
    observation.total_observed_seconds += max(float(observation_span_seconds), 0.0)
    if zone_name and zone_type:
        observation.zone_dwell_seconds[zone_name] = (
            observation.zone_dwell_seconds.get(zone_name, 0.0) + max(float(observation_span_seconds), 0.0)
        )
        observation.zone_hit_counts[zone_name] += 1
        observation.zone_types[zone_name] = zone_type
        if zone_relation:
            relation_counter = observation.zone_relations.setdefault(zone_name, Counter())
            relation_counter[zone_relation] += 1


def _select_dominant_zone(observation: TrackObservation) -> tuple[str | None, str | None, float, float, str | None]:
    if observation.zone_dwell_seconds:
        zone_name, dwell_seconds = max(
            observation.zone_dwell_seconds.items(),
            key=lambda item: (item[1], observation.zone_hit_counts.get(item[0], 0)),
        )
        total_seconds = max(observation.total_observed_seconds, 1e-9)
        share = dwell_seconds / total_seconds
    elif observation.zone_hit_counts:
        zone_name, hit_count = observation.zone_hit_counts.most_common(1)[0]
        dwell_seconds = 0.0
        share = hit_count / max(sum(observation.zone_hit_counts.values()), 1)
    else:
        return None, None, 0.0, 0.0, None

    relation_counter = observation.zone_relations.get(zone_name, Counter())
    relation = relation_counter.most_common(1)[0][0] if relation_counter else None
    return zone_name, observation.zone_types.get(zone_name), dwell_seconds, share, relation


def _resolve_zone_refined_behavior(
    observation: TrackObservation,
    majority_label: str,
) -> tuple[str, str | None, str | None]:
    base_key = _canonical_behavior_key(majority_label)
    final_key = base_key
    zone_name, zone_type, dwell_seconds, share, relation = _select_dominant_zone(observation)

    if zone_name and zone_type:
        if zone_type == "feeding" and base_key != "lying":
            if (
                dwell_seconds >= settings.zone_feeding_min_dwell_seconds
                and share >= settings.zone_behavior_min_ratio
            ):
                final_key = "feeding"
        elif zone_type == "water" and base_key != "lying":
            if (
                dwell_seconds >= settings.zone_drinking_min_dwell_seconds
                and share >= settings.zone_behavior_min_ratio
            ):
                final_key = "drinking"
        elif zone_type == "rest":
            if base_key == "lying":
                final_key = "lying"
            elif (
                base_key != "walking"
                and dwell_seconds >= settings.zone_resting_min_dwell_seconds
                and share >= settings.zone_behavior_min_ratio
            ):
                final_key = "resting"

    resolved_label = _translate_behavior_label(final_key) or majority_label
    if final_key == base_key or not zone_name or not zone_type:
        return resolved_label, zone_name, None

    rule_note = (
        f"zone-rule:{final_key} base={base_key} zone={zone_name} type={zone_type} "
        f"dwell={dwell_seconds:.1f}s share={share:.0%}"
    )
    if relation:
        rule_note += f" relation={relation}"
    return resolved_label, zone_name, rule_note


def _compose_event_notes(base_notes: str, reason_counts: Counter[str]) -> str:
    if not reason_counts:
        return base_notes

    top_reason, top_count = reason_counts.most_common(1)[0]
    if len(reason_counts) == 1:
        return f"{base_notes}; {top_reason} tracks={top_count}"

    return f"{base_notes}; {top_reason} tracks={top_count}; zone-rule-variants={len(reason_counts)}"


def _build_behavior_events(
    payload: InferenceRequest,
    track_observations: dict[str, TrackObservation],
    notes: str,
) -> list[BehaviorEventCandidate]:
    aggregated: dict[tuple[str, str | None], dict[str, Any]] = {}

    for observation in track_observations.values():
        if not observation.labels:
            continue

        majority_label = Counter(observation.labels).most_common(1)[0][0]
        resolved_label, zone_name, rule_note = _resolve_zone_refined_behavior(
            observation,
            majority_label=majority_label,
        )
        label_confidences = [
            confidence
            for label, confidence in zip(
                observation.labels,
                observation.confidences,
                strict=False,
            )
            if label == majority_label
        ]
        object_confidence = sum(label_confidences or observation.confidences) / max(
            len(label_confidences or observation.confidences), 1
        )

        bucket = aggregated.setdefault(
            (resolved_label, zone_name),
            {
                "count": 0,
                "confidences": [],
                "offsets": [],
                "zone_name": zone_name,
                "reason_counts": Counter(),
            },
        )
        bucket["count"] += 1
        bucket["confidences"].append(object_confidence)
        bucket["offsets"].append(observation.first_offset_seconds or 0.0)
        if rule_note:
            bucket["reason_counts"][rule_note] += 1

    behavior_events: list[BehaviorEventCandidate] = []
    sorted_items = sorted(
        aggregated.items(),
        key=lambda item: (-item[1]["count"], item[0][0], item[0][1] or ""),
    )
    for (behavior_type, zone_name), bucket in sorted_items:
        average_confidence = sum(bucket["confidences"]) / max(len(bucket["confidences"]), 1)
        event_offset_seconds = (
            float(statistics.median(bucket["offsets"]))
            if bucket["offsets"]
            else 0.0
        )
        behavior_events.append(
            BehaviorEventCandidate(
                device_code=payload.device_code or "unknown-device",
                event_time=payload.occurred_at + timedelta(seconds=event_offset_seconds),
                behavior_type=behavior_type,
                cow_count=int(bucket["count"]),
                confidence=round(average_confidence, 4),
                zone_name=zone_name,
                notes=_compose_event_notes(notes, bucket["reason_counts"]),
            )
        )

    return behavior_events


def _estimate_fps(source_ref: str | Path) -> float:
    cv2, _, _ = _load_runtime_dependencies()
    capture = cv2.VideoCapture(str(source_ref))
    if not capture.isOpened():
        return 25.0

    fps = capture.get(cv2.CAP_PROP_FPS)
    capture.release()
    return float(fps) if fps and fps > 1 else 25.0


def _should_use_detection_box(class_name: str, available_names: dict[int, Any] | list[Any]) -> bool:
    name_count = len(available_names)
    if _translate_behavior_label(class_name):
        return True
    if _is_cow_label(class_name):
        return True
    return name_count <= 1


def _resolve_yolo_only_label(
    class_name: str,
    available_names: dict[int, Any] | list[Any],
) -> str | None:
    translated = _translate_behavior_label(class_name)
    if translated:
        return translated
    if _is_cow_label(class_name) or len(available_names) <= 1:
        return "牛只检测"
    return None


def _resolve_box_behavior_label(
    *,
    image: Any,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    class_name: str,
    available_names: dict[int, Any] | list[Any],
    classifier: Any | None,
    extract_hog_feature: Any | None,
    knn_confidence_threshold: float,
) -> tuple[str | None, float | None]:
    if classifier is None or extract_hog_feature is None:
        return _resolve_yolo_only_label(class_name, available_names), None

    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return None, None

    feature = extract_hog_feature(crop, image_size=classifier.image_size)
    prediction = classifier.predict(feature)
    prediction_confidence = float(prediction.confidence)
    if prediction_confidence < knn_confidence_threshold:
        return _resolve_yolo_only_label(class_name, available_names), None

    return (
        _translate_behavior_label(prediction.label_name) or prediction.label_name,
        prediction_confidence,
    )


def _analyze_image_source(
    payload: InferenceRequest,
    model: Any,
    classifier: Any | None,
) -> tuple[list[BehaviorEventCandidate], dict[str, Any]]:
    _, extract_hog_feature, _ = _load_knn_tools() if classifier is not None else (None, None, None)
    zone_candidates = _extract_zone_candidates(payload)
    yolo_confidence = _resolve_yolo_confidence(payload)
    yolo_iou = _resolve_yolo_iou(payload)
    knn_confidence_threshold = _resolve_knn_confidence_threshold(payload)
    results = model.predict(
        source=_read_image_bytes(str(_resolve_media_source(payload))),
        conf=yolo_confidence,
        iou=yolo_iou,
        verbose=False,
    )
    result = results[0]
    image = result.orig_img

    track_observations: dict[str, TrackObservation] = {}
    boxes = getattr(result, "boxes", None)
    if boxes is not None:
        for box_index, box in enumerate(boxes, start=1):
            class_name = _extract_class_name(result, box)
            available_names = getattr(result, "names", {}) or {}
            if not _should_use_detection_box(class_name, available_names):
                continue

            x1, y1, x2, y2 = _clamp_box(*box.xyxy[0].tolist(), image.shape[1], image.shape[0])
            if x2 <= x1 or y2 <= y1:
                continue

            detection_confidence = (
                float(box.conf[0]) if getattr(box, "conf", None) is not None else 0.0
            )
            final_label, classifier_confidence = _resolve_box_behavior_label(
                image=image,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                class_name=class_name,
                available_names=available_names,
                classifier=classifier,
                extract_hog_feature=extract_hog_feature,
                knn_confidence_threshold=knn_confidence_threshold,
            )

            if not final_label:
                continue

            matched_zone = _match_detection_zone(
                zone_candidates,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                frame_width=image.shape[1],
                frame_height=image.shape[0],
            )

            _append_track_observation(
                track_observations=track_observations,
                track_id=f"image-box-{box_index}",
                label=final_label,
                confidence=_combine_confidences(detection_confidence, classifier_confidence),
                offset_seconds=0.0,
                zone_name=matched_zone.name if matched_zone else None,
                zone_type=matched_zone.zone_type if matched_zone else None,
                zone_relation=matched_zone.relation if matched_zone else None,
            )

    notes = "真实 YOLO + KNN 推理结果" if classifier is not None else "真实 YOLO 推理结果"
    behavior_events = _build_behavior_events(payload, track_observations, notes=notes)
    return behavior_events, {
        "processed_frames": 1,
        "track_count": len(track_observations),
        "frame_stride": 1,
        "zone_candidate_count": len(zone_candidates),
        "zone_behavior_logic": _build_zone_logic_metadata(),
    }


def _analyze_realtime_stream_source(
    payload: InferenceRequest,
    model: Any,
    classifier: Any | None,
) -> tuple[list[BehaviorEventCandidate], dict[str, Any]]:
    _, extract_hog_feature, _ = _load_knn_tools() if classifier is not None else (None, None, None)
    zone_candidates = _extract_zone_candidates(payload)
    yolo_confidence = _resolve_yolo_confidence(payload)
    yolo_iou = _resolve_yolo_iou(payload)
    knn_confidence_threshold = _resolve_knn_confidence_threshold(payload)

    image = _capture_preview_frame(_resolve_media_source(payload))
    results = model.predict(
        source=image,
        conf=yolo_confidence,
        iou=yolo_iou,
        verbose=False,
    )
    result = results[0]

    track_observations: dict[str, TrackObservation] = {}
    boxes = getattr(result, "boxes", None)
    if boxes is not None:
        for box_index, box in enumerate(boxes, start=1):
            class_name = _extract_class_name(result, box)
            available_names = getattr(result, "names", {}) or {}
            if not _should_use_detection_box(class_name, available_names):
                continue

            x1, y1, x2, y2 = _clamp_box(*box.xyxy[0].tolist(), image.shape[1], image.shape[0])
            if x2 <= x1 or y2 <= y1:
                continue

            detection_confidence = (
                float(box.conf[0]) if getattr(box, "conf", None) is not None else 0.0
            )
            final_label, classifier_confidence = _resolve_box_behavior_label(
                image=image,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                class_name=class_name,
                available_names=available_names,
                classifier=classifier,
                extract_hog_feature=extract_hog_feature,
                knn_confidence_threshold=knn_confidence_threshold,
            )

            if not final_label:
                continue

            matched_zone = _match_detection_zone(
                zone_candidates,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                frame_width=image.shape[1],
                frame_height=image.shape[0],
            )

            _append_track_observation(
                track_observations=track_observations,
                track_id=f"realtime-box-{box_index}",
                label=final_label,
                confidence=_combine_confidences(detection_confidence, classifier_confidence),
                offset_seconds=0.0,
                zone_name=matched_zone.name if matched_zone else None,
                zone_type=matched_zone.zone_type if matched_zone else None,
                zone_relation=matched_zone.relation if matched_zone else None,
            )

    notes = (
        "实时单帧 YOLO + KNN 推理结果"
        if classifier is not None
        else "实时单帧 YOLO 推理结果"
    )
    behavior_events = _build_behavior_events(payload, track_observations, notes=notes)
    return behavior_events, {
        "processed_frames": 1,
        "track_count": len(track_observations),
        "frame_stride": 1,
        "analysis_profile": "realtime",
        "source_strategy": "single-frame-snapshot",
        "zone_candidate_count": len(zone_candidates),
        "zone_behavior_logic": _build_zone_logic_metadata(),
    }


def _analyze_video_source(
    payload: InferenceRequest,
    model: Any,
    classifier: Any | None,
) -> tuple[list[BehaviorEventCandidate], dict[str, Any]]:
    _, np, _ = _load_runtime_dependencies()
    _, extract_hog_feature, _ = _load_knn_tools() if classifier is not None else (None, None, None)

    source_ref = _resolve_media_source(payload)
    fps = _estimate_fps(source_ref)
    zone_candidates = _extract_zone_candidates(payload)
    yolo_confidence = _resolve_yolo_confidence(payload)
    yolo_iou = _resolve_yolo_iou(payload)
    knn_confidence_threshold = _resolve_knn_confidence_threshold(payload)
    max_video_frames = _resolve_max_video_frames(payload)
    frame_stride = _resolve_frame_stride(payload)
    observation_span_seconds = frame_stride / max(fps, 1.0)
    track_states: dict[str, TrackState] = {}
    track_observations: dict[str, TrackObservation] = {}

    frame_count = 0
    for frame_index, result in enumerate(
        model.track(
            source=str(source_ref),
            conf=yolo_confidence,
            iou=yolo_iou,
            stream=True,
            persist=True,
            verbose=False,
        ),
        start=1,
    ):
        if frame_index > max_video_frames:
            break

        if frame_index % max(frame_stride, 1) != 0:
            continue

        frame_count += 1
        _prune_track_states(track_states, frame_index=frame_index)
        frame = result.orig_img
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue

        available_names = getattr(result, "names", {}) or {}
        for box_index, box in enumerate(boxes, start=1):
            class_name = _extract_class_name(result, box)
            if not _should_use_detection_box(class_name, available_names):
                continue

            x1, y1, x2, y2 = _clamp_box(*box.xyxy[0].tolist(), frame.shape[1], frame.shape[0])
            if x2 <= x1 or y2 <= y1:
                continue

            track_id = _get_track_id(box) or f"frame-{frame_index}-box-{box_index}"
            offset_seconds = frame_index / max(fps, 1.0)
            detection_confidence = (
                float(box.conf[0]) if getattr(box, "conf", None) is not None else 0.0
            )
            final_label: str | None
            classifier_confidence: float | None

            if classifier is not None and extract_hog_feature is not None:
                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue

                feature = extract_hog_feature(crop, image_size=classifier.image_size)
                prediction = classifier.predict(feature)
                prediction_confidence = float(prediction.confidence)
                if prediction_confidence < knn_confidence_threshold:
                    final_label = _resolve_yolo_only_label(class_name, available_names)
                    classifier_confidence = None
                else:
                    center = _get_box_center(x1, y1, x2, y2)
                    track_state = _update_track_state(
                        track_states,
                        track_id,
                        center,
                        frame_index,
                    )
                    refined_label = _refine_behavior_label(
                        prediction.label_name,
                        track_state=track_state,
                        box_width=x2 - x1,
                        box_height=y2 - y1,
                        np=np,
                    )
                    final_label = _translate_behavior_label(refined_label) or refined_label
                    classifier_confidence = prediction_confidence
            else:
                final_label = _resolve_yolo_only_label(class_name, available_names)
                classifier_confidence = None

            if not final_label:
                continue

            matched_zone = _match_detection_zone(
                zone_candidates,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                frame_width=frame.shape[1],
                frame_height=frame.shape[0],
            )

            _append_track_observation(
                track_observations=track_observations,
                track_id=track_id,
                label=final_label,
                confidence=_combine_confidences(detection_confidence, classifier_confidence),
                offset_seconds=offset_seconds,
                zone_name=matched_zone.name if matched_zone else None,
                zone_type=matched_zone.zone_type if matched_zone else None,
                zone_relation=matched_zone.relation if matched_zone else None,
                observation_span_seconds=observation_span_seconds,
            )

    notes = "真实 YOLO + KNN 推理结果" if classifier is not None else "真实 YOLO 推理结果"
    behavior_events = _build_behavior_events(payload, track_observations, notes=notes)
    return behavior_events, {
        "processed_frames": frame_count,
        "track_count": len(track_observations),
        "frame_stride": frame_stride,
        "max_video_frames": max_video_frames,
        "estimated_fps": round(fps, 2),
        "zone_candidate_count": len(zone_candidates),
        "zone_behavior_logic": _build_zone_logic_metadata(),
    }


def _build_model_version(model_path: Path) -> str:
    stat = model_path.stat()
    modified_at = datetime.fromtimestamp(stat.st_mtime, UTC).strftime("%Y%m%d%H%M%S")
    return f"{model_path.name}@{modified_at}"


def _run_real_inference(payload: InferenceRequest) -> InferenceResponse:
    if payload.inference_mode not in SUPPORTED_INFERENCE_MODES:
        raise RuntimeError(f"不支持的推理模式：{payload.inference_mode}")

    model_path = _resolve_model_path(payload.yolo_model_key)
    if not model_path.exists():
        raise RuntimeError(f"未找到 YOLO 权重文件：{model_path}")

    classifier = None
    if payload.inference_mode == "yolo-knn":
        if not settings.knn_model_path.exists():
            raise RuntimeError(f"未找到 KNN 模型文件：{settings.knn_model_path}")
        classifier = _load_knn_classifier(str(settings.knn_model_path))

    model = _load_yolo_model(str(model_path))
    if payload.source_type in {"image", "edge-report"}:
        behavior_events, runtime_metadata = _analyze_image_source(
            payload,
            model=model,
            classifier=classifier,
        )
    elif str(payload.metadata.get("analysis_profile", "")).strip().lower() == "realtime":
        behavior_events, runtime_metadata = _analyze_realtime_stream_source(
            payload,
            model=model,
            classifier=classifier,
        )
    else:
        behavior_events, runtime_metadata = _analyze_video_source(
            payload,
            model=model,
            classifier=classifier,
        )

    inference_source = "real-yolo-knn" if classifier is not None else "real-yolo-only"
    model_name = (
        f"{model_path.stem} + KNN"
        if classifier is not None
        else f"{model_path.stem}（仅 YOLO）"
    )
    model_version = _build_model_version(model_path)
    resolved_yolo_confidence = _resolve_yolo_confidence(payload)
    resolved_yolo_iou = _resolve_yolo_iou(payload)
    resolved_knn_confidence_threshold = _resolve_knn_confidence_threshold(payload)

    return InferenceResponse(
        request_id=payload.request_id,
        service="cow-monitor-inference",
        model_name=model_name,
        model_version=model_version,
        inference_source=inference_source,
        processed_at=datetime.now(UTC),
        behavior_events=behavior_events,
        raw_metadata={
            "pipeline_mode": settings.pipeline_mode,
            "inference_mode": payload.inference_mode,
            "yolo_model_key": payload.yolo_model_key or _to_model_key(model_path),
            "yolo_model_path": str(model_path.resolve()),
            "yolo_confidence": resolved_yolo_confidence,
            "yolo_iou": resolved_yolo_iou,
            "knn_confidence_threshold": resolved_knn_confidence_threshold,
            "compute_device": _resolve_compute_device(),
            "knn_model_path": (
                str(settings.knn_model_path.resolve()) if classifier is not None else None
            ),
            "source_type": payload.source_type,
            **runtime_metadata,
        },
    )


def run_inference_request(payload: InferenceRequest) -> InferenceResponse:
    override_events = _build_events_from_overrides(payload)
    if override_events:
        return InferenceResponse(
            request_id=payload.request_id,
            service="cow-monitor-inference",
            model_name="manual-overrides",
            model_version="override",
            inference_source="manual-overrides",
            processed_at=datetime.now(UTC),
            behavior_events=override_events,
            raw_metadata={
                "pipeline_mode": settings.pipeline_mode,
                "inference_mode": payload.inference_mode,
                "override_count": len(override_events),
            },
        )

    if settings.pipeline_mode == "stub":
        return run_stub_inference(payload)

    if settings.pipeline_mode != "real":
        raise RuntimeError(f"未知的推理服务运行模式：{settings.pipeline_mode}")

    return _run_real_inference(payload)
