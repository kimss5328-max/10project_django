"""비동기 분석 작업 — 업로드 영상을 FastAPI로 보내고 결과를 Django ORM으로 저장"""
from __future__ import annotations

import logging
from pathlib import Path

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import AnalysisJob, PersonPrediction
from .services import AIServiceError, predict_video

logger = logging.getLogger(__name__)


def _finish(job: AnalysisJob, status: str, *, message: str = "", error: str = ""):
    job.status = status
    job.result_message = message[:200]
    job.error_message = error[:2000]
    job.completed_at = timezone.now()
    job.processing_sec = round((job.completed_at - job.started_at).total_seconds(), 2)
    job.save(update_fields=["status", "result_message", "error_message", "completed_at",
                            "processing_sec", "model_version"])
    logger.info("job %s %s (%.2fs) %s", job.pk, status, job.processing_sec, error or message)


@shared_task(bind=True, time_limit=900, soft_time_limit=840)
def run_analysis(self, job_id: int):
    job = AnalysisJob.objects.filter(pk=job_id).first()
    if job is None:
        logger.warning("job %s 없음 (삭제됨)", job_id)
        return {"job_id": job_id, "status": "MISSING"}

    job.status = AnalysisJob.Status.PROCESSING
    job.started_at = timezone.now()
    job.celery_task_id = self.request.id or job.celery_task_id
    job.save(update_fields=["status", "started_at", "celery_task_id"])
    logger.info("job %s PROCESSING (task %s)", job_id, self.request.id)

    try:
        if job.input_type != AnalysisJob.InputType.UPLOAD:
            raise AIServiceError("IP Webcam 분석은 아직 지원하지 않습니다(8단계).")
        if not job.video:
            raise AIServiceError("영상 파일이 없습니다.")

        with job.video.open("rb") as f:
            result = predict_video(f, Path(job.video.name).name)

        preds = result.get("predictions", [])
        job.model_version = (result.get("model") or {}).get("joblib_md5") or ""
        with transaction.atomic():
            job.predictions.all().delete()                 # 재실행되어도 중복 저장 안 되게
            PersonPrediction.objects.bulk_create([
                PersonPrediction(
                    job=job, track_id=p["track_id"], action_label=p["action_label"],
                    confidence=p["confidence"], uncertain=p.get("uncertain", False),
                    valid_frames=p.get("valid_frames", 0), window_count=p.get("window_count", 1),
                    first_frame=p.get("first_frame"), last_frame=p.get("last_frame"),
                ) for p in preds
            ])
            _finish(job, AnalysisJob.Status.COMPLETED, message=result.get("message", ""))
        return {"job_id": job_id, "status": job.status, "predictions": len(preds)}

    except AIServiceError as e:
        _finish(job, AnalysisJob.Status.FAILED, error=str(e))
    except Exception as e:                                  # 예상 못 한 오류도 반드시 FAILED로 남김
        logger.exception("job %s 예외", job_id)
        _finish(job, AnalysisJob.Status.FAILED, error=f"{type(e).__name__}: {e}")
    return {"job_id": job_id, "status": job.status}
