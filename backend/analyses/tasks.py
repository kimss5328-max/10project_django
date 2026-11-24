"""비동기 분석 작업 — 6단계: 상태 흐름만 검증(가짜 처리), 7단계에서 FastAPI 호출로 교체"""
import logging
import time

from celery import shared_task
from django.utils import timezone

from .models import AnalysisJob

logger = logging.getLogger(__name__)


@shared_task(bind=True)
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
        time.sleep(3)                      # ← 7단계에서 FastAPI 호출로 교체
        job.result_message = "6단계 테스트: Worker 처리 완료 (아직 AI 추론 없음)"
        job.status = AnalysisJob.Status.COMPLETED
    except Exception as e:                 # 실패해도 반드시 상태를 남김
        logger.exception("job %s 실패", job_id)
        job.status = AnalysisJob.Status.FAILED
        job.error_message = f"{type(e).__name__}: {e}"[:1000]

    job.completed_at = timezone.now()
    job.processing_sec = round((job.completed_at - job.started_at).total_seconds(), 2)
    job.save(update_fields=["status", "result_message", "error_message", "completed_at", "processing_sec"])
    logger.info("job %s %s (%.2fs)", job_id, job.status, job.processing_sec)
    return {"job_id": job_id, "status": job.status}
