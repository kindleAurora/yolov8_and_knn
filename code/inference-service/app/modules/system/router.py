from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.core.config import settings
from app.pipelines.runtime import (
    get_inference_meta,
    get_media_preview_bytes,
    read_media_payload,
    run_inference_request,
)
from app.schemas.inference import InferenceMetaResponse, InferenceRequest, InferenceResponse

public_router = APIRouter(tags=["health"])
api_router = APIRouter(tags=["inference"])


@public_router.get("/health")
def health() -> dict[str, object]:
    return {
        "service": "cow-monitor-inference",
        "environment": settings.app_env,
        "version": settings.app_version,
        "phase": "stage-3",
        "pipeline_mode": settings.pipeline_mode,
    }


@api_router.get("/meta")
def meta() -> InferenceMetaResponse:
    return get_inference_meta()


@api_router.post("/predict", response_model=InferenceResponse)
def predict(payload: InferenceRequest) -> InferenceResponse:
    try:
        return run_inference_request(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.get("/preview")
def preview_media(
    source_type: str = Query(...),
    source_uri: str = Query(...),
    frame_uri: str | None = Query(default=None),
    prefer_frame: bool = Query(default=True),
    annotated: bool = Query(default=False),
    inference_mode: str = Query(default="yolo-only"),
    yolo_model_key: str | None = Query(default=None),
    yolo_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    yolo_iou: float | None = Query(default=None, ge=0.0, le=1.0),
    knn_confidence_threshold: float | None = Query(default=None, ge=0.0, le=1.0),
) -> Response:
    try:
        preview_bytes = get_media_preview_bytes(
            source_type=source_type,
            source_uri=source_uri,
            frame_uri=frame_uri,
            prefer_frame=prefer_frame,
            annotated=annotated,
            inference_mode=inference_mode,
            yolo_model_key=yolo_model_key,
            yolo_confidence=yolo_confidence,
            yolo_iou=yolo_iou,
            knn_confidence_threshold=knn_confidence_threshold,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Response(
        content=preview_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@api_router.get("/media")
def raw_media(
    source_type: str = Query(...),
    source_uri: str = Query(...),
    frame_uri: str | None = Query(default=None),
    prefer_frame: bool = Query(default=False),
) -> Response:
    try:
        payload, media_type, file_name = read_media_payload(
            source_type=source_type,
            source_uri=source_uri,
            frame_uri=frame_uri,
            prefer_frame=prefer_frame,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Response(
        content=payload,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="{file_name}"',
        },
    )
