from __future__ import annotations

from pathlib import Path

from app.core.config import settings

PREVIEW_CACHE_KEY = "preview_cache_path"


def _preview_cache_dir() -> Path:
    directory = settings.generated_media_dir / "event-previews"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def build_event_preview_cache_path(request_id: str) -> Path:
    safe_request_id = "".join(
        character
        for character in request_id
        if character.isalnum() or character in {"-", "_"}
    ).strip()
    file_name = safe_request_id or "preview"
    return _preview_cache_dir() / f"{file_name}.jpg"


def write_event_preview_cache(request_id: str, payload: bytes) -> str:
    cache_path = build_event_preview_cache_path(request_id)
    cache_path.write_bytes(payload)
    return str(cache_path.resolve())


def resolve_event_preview_cache_path(raw_metadata: dict[str, object] | None) -> Path | None:
    if not isinstance(raw_metadata, dict):
        return None

    raw_path = raw_metadata.get(PREVIEW_CACHE_KEY)
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None

    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = settings.generated_media_dir / candidate

    try:
        candidate.resolve().relative_to(settings.generated_media_dir.resolve())
    except ValueError:
        return None

    return candidate if candidate.exists() else None
