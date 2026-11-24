"""
[2단계] FastAPI AI 추론 서버
실행: uvicorn main:app --host 0.0.0.0 --port 8001   (ai_service 폴더에서)
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from routers import predictions
from services.model_loader import get_bundle, is_ready, load_model_bundle
from services.pose_pipeline import check_weights


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model_bundle()            # 서버 시작 시 1번만 로드 → 이후 요청에서 재사용
    yield


app = FastAPI(title="Vision Action AI Service", version="1.0", lifespan=lifespan)
app.include_router(predictions.router)


@app.get("/health", tags=["health"])
def health():
    weights = check_weights()
    ready = is_ready() and all(weights.values())
    body = {"status": "ok" if ready else "not_ready", "model_loaded": is_ready(), "weights": weights}
    if is_ready():
        b = get_bundle()
        body.update(classes=b.classes, feature_count=b.feature_count, sequence_steps=b.sequence_steps,
                    model_version=b.version)
    return body
