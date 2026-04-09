#!/usr/bin/env bash

set -euo pipefail

VIDEO_DIR="${VIDEO_DIR:-/videos}"
VIDEO_GLOB="${VIDEO_GLOB:-*.mp4}"
PLAYLIST_PATH="${PLAYLIST_PATH:-/tmp/video-playlist.ffconcat}"
RTSP_OUTPUT_URL="${RTSP_OUTPUT_URL:-rtsp://mediamtx:8554/cow-monitor/demo}"

if [[ ! -d "${VIDEO_DIR}" ]]; then
  echo "Video directory does not exist: ${VIDEO_DIR}" >&2
  exit 1
fi

mapfile -t files < <(find "${VIDEO_DIR}" -maxdepth 1 -type f -name "${VIDEO_GLOB}" | sort -V)

if [[ "${#files[@]}" -eq 0 ]]; then
  echo "No matching video files were found in ${VIDEO_DIR} (${VIDEO_GLOB})." >&2
  exit 1
fi

{
  echo "ffconcat version 1.0"
  for file in "${files[@]}"; do
    printf "file '%s'\n" "${file//\'/\'\\\'\'}"
  done
} > "${PLAYLIST_PATH}"

echo "Prepared ${#files[@]} files for looping playback."
echo "Publishing RTSP stream to ${RTSP_OUTPUT_URL}"

exec ffmpeg \
  -hide_banner \
  -loglevel info \
  -re \
  -stream_loop -1 \
  -f concat \
  -safe 0 \
  -fflags +genpts \
  -i "${PLAYLIST_PATH}" \
  -an \
  -c:v libx264 \
  -preset veryfast \
  -tune zerolatency \
  -pix_fmt yuv420p \
  -g 50 \
  -keyint_min 50 \
  -sc_threshold 0 \
  -f rtsp \
  -rtsp_transport tcp \
  "${RTSP_OUTPUT_URL}"
