from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.core.config import settings

INFERENCE_PREDICT_PATH = "/api/v1/inference/predict"
INFERENCE_META_PATH = "/api/v1/inference/meta"
INFERENCE_PREVIEW_PATH = "/api/v1/inference/preview"
INFERENCE_MEDIA_PATH = "/api/v1/inference/media"


def _request_inference_service(
    *,
    path: str,
    method: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 8,
) -> dict[str, Any]:
    request = Request(
        f"{settings.inference_service_url}{path}",
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers={"Content-Type": "application/json"} if payload is not None else {},
        method=method,
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:  # pragma: no cover - integration branch
        response_text = exc.read().decode("utf-8", errors="ignore")
        error_message = response_text or "空响应"
        try:
            response_json = json.loads(response_text)
            if isinstance(response_json, dict):
                if isinstance(response_json.get("detail"), str):
                    error_message = response_json["detail"]
                elif isinstance(response_json.get("message"), str):
                    error_message = response_json["message"]
        except json.JSONDecodeError:
            pass
        raise RuntimeError(
            f"推理服务调用失败，状态码 {exc.code}，响应：{error_message}"
        ) from exc
    except URLError as exc:  # pragma: no cover - integration branch
        raise RuntimeError(f"无法连接推理服务：{exc.reason}") from exc
    except json.JSONDecodeError as exc:  # pragma: no cover - integration branch
        raise RuntimeError("推理服务返回了无法解析的 JSON 数据") from exc


def _request_inference_service_binary(
    *,
    path: str,
    query: dict[str, Any],
    timeout: int = 20,
) -> tuple[bytes, str, str | None]:
    encoded_query = urlencode(
        {
            key: value
            for key, value in query.items()
            if value is not None
        }
    )
    request = Request(
        f"{settings.inference_service_url}{path}?{encoded_query}",
        method="GET",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            return (
                response.read(),
                response.headers.get_content_type(),
                response.headers.get("Content-Disposition"),
            )
    except HTTPError as exc:  # pragma: no cover - integration branch
        response_text = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(
            f"推理服务调用失败，状态码 {exc.code}，响应：{response_text or '空响应'}"
        ) from exc
    except URLError as exc:  # pragma: no cover - integration branch
        raise RuntimeError(f"无法连接推理服务：{exc.reason}") from exc


def invoke_inference_service(payload: dict[str, Any], *, timeout: int = 8) -> dict[str, Any]:
    return _request_inference_service(
        path=INFERENCE_PREDICT_PATH,
        method="POST",
        payload=payload,
        timeout=timeout,
    )


def fetch_inference_service_meta() -> dict[str, Any]:
    return _request_inference_service(
        path=INFERENCE_META_PATH,
        method="GET",
    )


def fetch_inference_preview(query: dict[str, Any]) -> tuple[bytes, str, str | None]:
    return _request_inference_service_binary(
        path=INFERENCE_PREVIEW_PATH,
        query=query,
    )


def fetch_inference_media(query: dict[str, Any]) -> tuple[bytes, str, str | None]:
    return _request_inference_service_binary(
        path=INFERENCE_MEDIA_PATH,
        query=query,
    )
