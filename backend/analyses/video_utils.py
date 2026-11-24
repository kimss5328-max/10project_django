"""수집 영상을 브라우저에서 재생되는 H.264 mp4로 변환 (실패하면 원본 유지)"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()     # 패키지에 들어 있는 ffmpeg (libx264 포함)
    except Exception as e:                          # 설치 안 됨 등 → 변환 생략
        logger.warning("ffmpeg 사용 불가: %s", e)
        return None


def to_h264(src: Path, fps: float | None = None, timeout: int = 120) -> Path:
    """src를 H.264로 변환한 새 파일 경로를 반환하고 src는 삭제.
    fps를 주면 실제 수집 속도로 재생 시간을 맞춤. 실패하면 src를 그대로 반환."""
    src = Path(src)
    exe = _ffmpeg()
    if exe is None:
        return src
    dst = src.with_name(src.stem + "_h264.mp4")
    cmd = [exe, "-y", "-loglevel", "error"]
    if fps and fps > 0:
        cmd += ["-r", f"{fps:.3f}"]                  # 입력 프레임 속도 지정 → 영상 길이 = 실제 수집 시간
    cmd += ["-i", str(src), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(dst)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)
    except Exception as e:
        stderr = getattr(e, "stderr", b"") or b""
        logger.warning("H.264 변환 실패, 원본 사용: %s %s", e, stderr.decode(errors="ignore")[-300:])
        dst.unlink(missing_ok=True)
        return src
    if not dst.exists() or dst.stat().st_size == 0:
        dst.unlink(missing_ok=True)
        return src
    src.unlink(missing_ok=True)
    logger.info("H.264 변환 완료 %s (%d bytes)", dst.name, dst.stat().st_size)
    return dst
