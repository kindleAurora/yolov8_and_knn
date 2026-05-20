from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _detect_workspace_root() -> Path:
    current_file = Path(__file__).resolve()

    for parent in current_file.parents:
        if (parent / "code").exists() and (parent / "runs").exists():
            return parent

    workspace_root = Path("/workspace")
    if workspace_root.exists():
        return workspace_root

    return current_file.parents[2]


WORKSPACE_ROOT = _detect_workspace_root()
DEFAULT_YOLO_MODEL_PATH = (
    WORKSPACE_ROOT / "runs" / "detect" / "cow_120_on_basecommon" / "weights" / "best.pt"
)
DEFAULT_KNN_MODEL_PATH = WORKSPACE_ROOT / "code" / "knn" / "knn_behavior_model.npz"


class Settings(BaseSettings):
    app_name: str = Field(default="牛只智能监控平台 Inference Service", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    api_prefix: str = Field(default="/api/v1/inference", alias="API_PREFIX")
    pipeline_mode: str = Field(default="real", alias="PIPELINE_MODE")
    workspace_root: Path = Field(default=WORKSPACE_ROOT, alias="WORKSPACE_ROOT")
    inference_device: str = Field(default="auto", alias="INFERENCE_DEVICE")
    yolo_model_path: Path = Field(default=DEFAULT_YOLO_MODEL_PATH, alias="YOLO_MODEL_PATH")
    knn_model_path: Path = Field(default=DEFAULT_KNN_MODEL_PATH, alias="KNN_MODEL_PATH")
    yolo_confidence: float = Field(default=0.25, alias="YOLO_CONFIDENCE")
    yolo_iou: float = Field(default=0.45, alias="YOLO_IOU")
    knn_confidence_threshold: float = Field(default=0.0, alias="KNN_CONFIDENCE_THRESHOLD")
    max_video_frames: int = Field(default=120, alias="MAX_VIDEO_FRAMES")
    frame_stride: int = Field(default=3, alias="FRAME_STRIDE")
    realtime_max_video_frames: int = Field(default=12, alias="REALTIME_MAX_VIDEO_FRAMES")
    realtime_frame_stride: int = Field(default=2, alias="REALTIME_FRAME_STRIDE")
    track_max_age: int = Field(default=10, alias="TRACK_MAX_AGE")
    motion_window: int = Field(default=6, alias="MOTION_WINDOW")
    motion_low_threshold: float = Field(default=0.005, alias="MOTION_LOW_THRESHOLD")
    motion_high_threshold: float = Field(default=0.01, alias="MOTION_HIGH_THRESHOLD")
    zone_proximity_threshold: float = Field(default=0.04, alias="ZONE_PROXIMITY_THRESHOLD")
    zone_behavior_min_ratio: float = Field(default=0.6, alias="ZONE_BEHAVIOR_MIN_RATIO")
    zone_feeding_min_dwell_seconds: float = Field(
        default=8.0,
        alias="ZONE_FEEDING_MIN_DWELL_SECONDS",
    )
    zone_drinking_min_dwell_seconds: float = Field(
        default=6.0,
        alias="ZONE_DRINKING_MIN_DWELL_SECONDS",
    )
    zone_resting_min_dwell_seconds: float = Field(
        default=12.0,
        alias="ZONE_RESTING_MIN_DWELL_SECONDS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
