"""
[2단계] POST /api/v1/predict/ — Celery Worker(지금은 Swagger)가 보낸 영상 1건을 분석

응답 규칙 (Celery와의 약속)
  - 400: 확장자 불가·빈 파일·영상 읽기 실패          → Worker는 FAILED 로 저장
  - 200 + status "ok"        : 1명 이상 예측
  - 200 + status "no_person" : 영상은 정상이나 예측할 사람이 없음 → Worker는 COMPLETED + 안내 메시지
"""
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from services.action_inference import CONFIDENCE_THRESHOLD, predict_tracks
from services.model_loader import get_bundle
from services.pose_pipeline import VideoReadError, extract_tracks

router = APIRouter(prefix="/api/v1", tags=["predict"])
ALLOWED_EXT = {".mp4", ".mov", ".avi", ".mkv"}


@router.post("/predict/")
def predict_video(file: UploadFile = File(..., description="분석할 영상(mp4/mov/avi)")):
    # def(동기) 함수 → FastAPI가 별도 스레드에서 실행하므로 무거운 추론이 서버 전체를 막지 않음
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"지원하지 않는 형식입니다: '{ext or '없음'}' (허용: {', '.join(sorted(ALLOWED_EXT))})")

    started = time.perf_counter()
    with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp.flush()
        if Path(tmp.name).stat().st_size == 0:
            raise HTTPException(400, "빈 파일입니다.")
        try:
            extracted = extract_tracks(tmp.name)
        except VideoReadError as e:
            raise HTTPException(400, str(e))

    bundle = get_bundle()
    predictions, skipped = predict_tracks(bundle, extracted["tracks"])
    if predictions:
        status, message = "ok", f"{len(predictions)}명의 동작을 예측했습니다."
    elif extracted["tracks"]:
        status, message = "no_person", "사람은 보였지만 동작을 판단할 만큼 관절이 충분히 잡히지 않았습니다."
    else:
        status, message = "no_person", "영상에서 사람을 찾지 못했습니다."

    return {
        "status": status,
        "message": message,
        "filename": file.filename,
        "video": extracted["video"],
        "pose": extracted["pose"],
        "model": {"classes": bundle.classes, "joblib_md5": bundle.version.get("joblib_md5"),
                  "pose_model": bundle.info.get("pose_model", "yolo"), "confidence_threshold": CONFIDENCE_THRESHOLD},
        "predictions": predictions,
        "skipped": skipped,
        "processing_sec": round(time.perf_counter() - started, 2),
    }
