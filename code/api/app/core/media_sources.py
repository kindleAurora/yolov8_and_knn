from __future__ import annotations

from urllib.parse import ParseResult, urlparse, urlunparse

from app.core.config import settings

LOCAL_STREAM_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0"}
REWRITABLE_STREAM_PORTS = {8554, 8888}
REWRITABLE_STREAM_SCHEMES = {"rtsp", "rtsps", "rtmp", "rtmps", "http", "https"}


def _build_rewritten_netloc(parsed: ParseResult, target_host: str) -> str:
    auth = ""
    if parsed.username:
        auth = parsed.username
        if parsed.password:
            auth = f"{auth}:{parsed.password}"
        auth = f"{auth}@"

    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{auth}{target_host}{port}"


def resolve_inference_media_uri(uri: str | None) -> str | None:
    if not uri:
        return uri

    target_host = settings.media_stream_internal_host.strip()
    if not target_host:
        return uri

    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()

    if scheme not in REWRITABLE_STREAM_SCHEMES:
        return uri
    if hostname not in LOCAL_STREAM_HOSTS:
        return uri
    if parsed.port is not None and parsed.port not in REWRITABLE_STREAM_PORTS:
        return uri

    return urlunparse(parsed._replace(netloc=_build_rewritten_netloc(parsed, target_host)))
