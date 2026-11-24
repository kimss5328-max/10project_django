"""허용된 IP Webcam에서 정해진 시간만 프레임을 읽어 임시 mp4로 저장하고 종료"""
from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path

import cv2
from django.conf import settings

logger = logging.getLogger(__name__)


class CameraError(Exception):
    """사용자에게 보여 줄 수 있는 카메라 오류"""


def capture_clip(camera_name: str, seconds: float | None = None) -> tuple[Path, dict]:
    url = settings.ALLOWED_CAMERAS.get(camera_name)
    if not url:                                   # 사용자가 임의 URL을 넣을 수 없게 이름으로만 찾음
        raise CameraError(f"허용되지 않은 카메라입니다 ({camera_name}).")
    seconds = float(seconds or settings.CAMERA_CAPTURE_SECONDS)

    cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
    cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
    if not cap.isOpened():
        raise CameraError(f"카메라에 연결할 수 없습니다 ({camera_name}). 앱의 서버 실행·Wi-Fi를 확인하세요.")

    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if 1 <= fps <= 60 else 15.0
    out_path = Path(tempfile.mkstemp(suffix=".mp4", prefix=f"cam_{camera_name}_")[1])
    writer = None
    frames = 0
    start = last_ok = time.monotonic()
    try:
        while time.monotonic() - start < seconds:
            ok, frame = cap.read()
            now = time.monotonic()
            if not ok:
                if now - last_ok > settings.CAMERA_STALL_SECONDS:
                    raise CameraError(f"카메라 연결이 끊겼습니다 ({camera_name}, {frames}프레임 수집 후).")
                time.sleep(0.05)
                continue
            last_ok = now
            if writer is None:
                h, w = frame.shape[:2]
                writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
            writer.write(frame)
            frames += 1
    except Exception:
        out_path.unlink(missing_ok=True)
        raise
    finally:
        cap.release()
        if writer is not None:
            writer.release()

    elapsed = round(time.monotonic() - start, 2)
    if frames < settings.CAMERA_MIN_FRAMES:
        out_path.unlink(missing_ok=True)
        raise CameraError(f"수집된 프레임이 너무 적습니다 ({frames}개 < {settings.CAMERA_MIN_FRAMES}).")
    stats = {"camera": camera_name, "seconds": elapsed, "frames": frames, "fps": round(frames / elapsed, 1)}
    logger.info("camera %s captured %s", camera_name, stats)
    return out_path, stats
